"""Ejecución del agente único y sus herramientas documentales."""

from __future__ import annotations

import json
import html
import logging
import re
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage

from agent_system.models import build_chat_model, fallback_chat_model
from agent_system.tools import safe_json

logger = logging.getLogger("chatBot.agent_system.runtime")


def _invoke(model: Any, messages: List[BaseMessage], tools: List[Any]) -> AIMessage:
    try:
        return model.invoke(messages)
    except Exception as exc:
        logger.warning("Proveedor LLM no disponible; usando respaldo: %s", exc)
        fallback = fallback_chat_model().bind_tools(tools)
        return fallback.invoke(messages)


def _text_tool_calls(content: Any) -> List[Dict[str, Any]]:
    """Acepta llamadas JSON emitidas por modelos sin tool calling nativo."""
    if not isinstance(content, str) or not content.strip():
        return []
    decoded = html.unescape(content).strip()
    candidates = re.findall(
        r"<(?:tools|tool_call)>\s*({.*})\s*</(?:tools|tool_call)>",
        decoded,
        re.DOTALL,
    )
    candidates.append(decoded)
    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and isinstance(payload.get("name"), str):
            arguments = payload.get("arguments", {})
            if isinstance(arguments, dict):
                return [{
                    "name": payload["name"],
                    "args": arguments,
                    "id": "text_tool_call",
                }]
    return []


def _fallback_from_tools(tool_messages: List[ToolMessage]) -> str:
    contents = [str(message.content).strip() for message in tool_messages]
    contents = [content for content in contents if content]
    if not contents:
        return "No encontré información suficiente en las fuentes disponibles."
    return "\n\n".join(contents)


def _last_user_text(messages: List[BaseMessage]) -> str:
    for message in reversed(messages):
        if getattr(message, "type", None) == "human":
            return str(getattr(message, "content", "") or "").strip()
    return ""


def invoke_specialist_agent(
    *,
    system_prompt: str,
    messages: List[BaseMessage],
    tools: List[Any] | None = None,
) -> Dict[str, List[BaseMessage]]:
    """Ejecuta chatBot y procesa hasta tres rondas de herramientas."""
    enabled_tools = list(tools or [])
    model = build_chat_model()
    bound_model = model
    if enabled_tools:
        try:
            bound_model = model.bind_tools(enabled_tools)
        except Exception as exc:
            logger.warning("El modelo no admite bind_tools: %s", exc)

    tool_names = {tool.name for tool in enabled_tools}
    tool_map = {tool.name: tool for tool in enabled_tools}
    conversation: List[BaseMessage] = [SystemMessage(content=system_prompt), *messages]
    generated: List[BaseMessage] = []
    all_tool_messages: List[ToolMessage] = []

    for round_index in range(3):
        ai_message = _invoke(bound_model, conversation, enabled_tools)
        native_calls = list(getattr(ai_message, "tool_calls", None) or [])
        tool_calls = native_calls or _text_tool_calls(
            getattr(ai_message, "content", "")
        )
        required_retrieval_tool = next(
            (
                name
                for name in ("primary_retrieve_context", "knowledge_retrieve_context")
                if name in tool_names
            ),
            None,
        )
        if round_index == 0 and not tool_calls and required_retrieval_tool:
            user_text = _last_user_text(messages)
            if user_text:
                tool_calls = [{
                    "name": required_retrieval_tool,
                    "args": {"query": user_text, "top_k": 3},
                    "id": "required_business_context",
                }]

        if not tool_calls:
            content = str(getattr(ai_message, "content", "") or "").strip()
            if "<tool_call>" in html.unescape(content) or "<tools>" in html.unescape(content):
                ai_message = AIMessage(content=_fallback_from_tools(all_tool_messages))
            elif not content:
                ai_message = AIMessage(content=_fallback_from_tools(all_tool_messages))
            generated.append(ai_message)
            return {"messages": generated}

        # Las llamadas expresadas como texto se convierten al formato nativo
        # para que ToolMessage mantenga una secuencia válida.
        if not native_calls:
            ai_message = AIMessage(content="", tool_calls=tool_calls)
        generated.append(ai_message)
        conversation.append(ai_message)

        current_tool_messages: List[ToolMessage] = []
        for call in tool_calls:
            name = call.get("name", "")
            arguments = call.get("args", {})
            call_id = str(call.get("id") or f"tool_call_{round_index}")
            selected = tool_map.get(name)
            if selected is None:
                result = safe_json({"error": f"Herramienta no permitida: {name}"})
            else:
                try:
                    value = selected.invoke(arguments or {})
                    result = value if isinstance(value, str) else safe_json(value)
                except Exception as exc:
                    result = safe_json({"error": f"Falló {name}: {exc}"})
            current_tool_messages.append(
                ToolMessage(
                    content=result,
                    tool_call_id=call_id,
                    additional_kwargs={"tool_name": name},
                )
            )
        generated.extend(current_tool_messages)
        conversation.extend(current_tool_messages)
        all_tool_messages.extend(current_tool_messages)

    generated.append(AIMessage(content=_fallback_from_tools(all_tool_messages)))
    return {"messages": generated}
