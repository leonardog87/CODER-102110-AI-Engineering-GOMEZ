"""Shared execution logic for specialist agents."""

from __future__ import annotations

import logging
import json
import re
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage

from agent_system.models import build_chat_model, fallback_chat_model
from agent_system.tools import safe_json


def _ensure_valid_response(
    messages: List[BaseMessage],
    fallback_content: str = "He procesado tu consulta."
) -> List[BaseMessage]:
    """
    Garantiza que el último mensaje sea un AIMessage con contenido válido.
    """
    logger.info("🔍 _ensure_valid_response - INICIO")
    logger.info(f"  Mensajes recibidos: {len(messages)}")
    
    if not messages:
        logger.info("  No hay mensajes, creando fallback")
        return [AIMessage(content=fallback_content)]
    
    # Buscar el último AIMessage con contenido válido
    last_valid_index = -1
    
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if isinstance(msg, AIMessage):
            content = getattr(msg, "content", "") or ""
            if content and not content.strip().startswith("{"):
                last_valid_index = i
                logger.info(f"  ✅ AIMessage válido en posición {i}: {content[:50]}...")
                break
    
    # Si encontramos un AIMessage válido, asegurarlo como último
    if last_valid_index != -1:
        if last_valid_index != len(messages) - 1:
            messages[-1] = messages[last_valid_index]
            logger.info(f"  🔄 Reemplazando último con AIMessage de posición {last_valid_index}")
        else:
            logger.info("  ✅ El último mensaje ya es válido")
        return messages
    
    # No hay AIMessage válido, crear fallback
    logger.info("  ⚠️ No hay AIMessage válido, creando fallback")
    messages.append(AIMessage(content=fallback_content))
    return messages


def _truncate_tool_result_if_needed(content: str, max_chars: int = 1500) -> str:
    """
    Trunca el resultado de una herramienta si es demasiado largo.
    """
    if not isinstance(content, str) or len(content) <= max_chars:
        return content
    
    try:
        data = json.loads(content)
        if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
            total = len(data["data"])
            if total > 3:
                data["data"] = data["data"][:3]
                data["total_items"] = total
                data["message"] = f"Mostrando 3 de {total} resultados (truncado)"
                return json.dumps(data, ensure_ascii=False, default=str)
    except (json.JSONDecodeError, TypeError):
        pass
    
    return content[:max_chars] + "... [RESULTADO TRUNCADO]"


logger = logging.getLogger("agente_corporativo.agent_system.runtime")


def _invoke_with_fallback(model: Any, messages: List[BaseMessage], tools: List[Any] | None = None):
    logger.info(f"🔍 _invoke_with_fallback - Invocando modelo con {len(messages)} mensajes")
    try:
        result = model.invoke(messages)
        logger.info(f"✅ Modelo invocado correctamente")
        return result
    except Exception as exc:
        logger.warning("Fallo la invocacion del modelo principal; usando fallback offline: %s", exc)
        fallback_model = fallback_chat_model()
        if tools:
            fallback_model = fallback_model.bind_tools(tools)
        return fallback_model.invoke(messages)


def _tool_calls_from_text(content: Any) -> List[Dict[str, Any]]:
    """
    Accept tool calls emitted as plain JSON by models without native tool mode.
    """
    if not isinstance(content, str) or not content.strip():
        return []

    pattern = r'<tools>\s*({.*?})\s*</tools>'
    matches = re.findall(pattern, content, re.DOTALL)
    
    for match in matches:
        try:
            payload = json.loads(match)
            if isinstance(payload, dict):
                name = payload.get("name")
                args = payload.get("arguments", {})
                if isinstance(name, str) and isinstance(args, dict):
                    return [{"name": name, "args": args, "id": "text_tool_call"}]
        except json.JSONDecodeError:
            continue
    
    json_pattern = r'\{[^{}]*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^{}]*\}\s*\}'
    json_matches = re.findall(json_pattern, content, re.DOTALL)
    
    for match in json_matches:
        try:
            payload = json.loads(match)
            if isinstance(payload, dict):
                name = payload.get("name")
                args = payload.get("arguments", {})
                if isinstance(name, str) and isinstance(args, dict):
                    return [{"name": name, "args": args, "id": "text_tool_call"}]
        except json.JSONDecodeError:
            continue
    
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return []

    if not isinstance(payload, dict):
        return []

    name = payload.get("name")
    args = payload.get("arguments", {})
    if not isinstance(name, str) or not isinstance(args, dict):
        return []

    return [{"name": name, "args": args, "id": "text_tool_call"}]


def _clean_tool_tags(content: str) -> str:
    """Elimina los bloques <tools> y el JSON de herramientas del contenido."""
    content = re.sub(r'<tools>.*?</tools>', '', content, flags=re.DOTALL)
    json_pattern = r'\{[^{}]*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^{}]*\}\s*\}'
    content = re.sub(json_pattern, '', content, flags=re.DOTALL)
    return content.strip()


def _looks_like_text_tool_call(content: Any) -> bool:
    return bool(_tool_calls_from_text(content))


def _format_tool_result_for_user(
    tool_messages: List[ToolMessage],
    user_text: str = "",
) -> str:
    """Formatea resultados agregados de forma legible (FALLBACK cuando el LLM falla)."""
    if not tool_messages:
        return ""

    payload = None
    for tool_message in reversed(tool_messages):
        try:
            candidate = json.loads(str(tool_message.content))
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            payload = candidate
            break

    if not isinstance(payload, dict):
        return ""

    status = payload.get("status")
    message = payload.get("message") or ""
    data = payload.get("data")

    if status != "ok":
        return message or "No se pudo completar la consulta solicitada."

    if isinstance(data, dict):
        total = data.get("total", 0)
        sample = data.get("sample", [])
        stats = data.get("stats", {})
        
        lines = []
        
        if total > 0:
            lines.append(f"📊 Total de registros encontrados: **{total}**")
        else:
            return "No se encontraron resultados para la consulta."
        
        if stats:
            if "total_sueldos" in stats:
                lines.append(f"💰 Suma total de sueldos: ${stats['total_sueldos']:,.0f} ARS")
                lines.append(f"📈 Promedio de sueldo: ${stats['promedio_sueldo']:,.0f} ARS")
            if "total_ingresos" in stats:
                lines.append(f"💰 Ingresos totales: ${stats['total_ingresos']:,.0f} ARS")
                lines.append(f"📈 Promedio de ingreso: ${stats['promedio_ingreso']:,.0f} ARS")
        
        if sample:
            lines.append(f"\n📋 **Muestra de {len(sample)} registros:**")
            
            normalized_user_text = _normalize_text(user_text)
            only_names = any(token in normalized_user_text for token in ("nombre", "nombres"))
            
            for row in sample:
                if isinstance(row, dict):
                    if only_names:
                        name_parts = [
                            str(row.get(key, "")).strip()
                            for key in ("Nombre", "Apellido", "Nombre_Responsable", "Apellido_Responsable")
                            if row.get(key)
                        ]
                        if name_parts:
                            lines.append("- " + " ".join(name_parts))
                            continue
                    
                    clean_items = [
                        f"{key}: {value}"
                        for key, value in row.items()
                        if value is not None and not str(key).startswith("Unnamed")
                    ]
                    lines.append("- " + " | ".join(clean_items[:5]))
                else:
                    lines.append(f"- {row}")
        
        if total > len(sample):
            lines.append(f"\n💡 ... y {total - len(sample)} registro(s) más.")
        
        return "\n".join(lines)

    return safe_json(data)


def _last_human_text(messages: List[BaseMessage]) -> str:
    for message in reversed(messages):
        if getattr(message, "type", None) == "human":
            return str(getattr(message, "content", "") or "")
    return ""


def _normalize_text(text: str) -> str:
    replacements = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")
    return text.translate(replacements).lower()


def _direct_tool_call_for_structured_query(
    messages: List[BaseMessage],
    tools: List[Any],
) -> Dict[str, Any] | None:
    """Route obvious MCP list queries without relying on model tool selection."""
    user_text = _normalize_text(_last_human_text(messages))
    tool_names = {tool_obj.name for tool_obj in tools}

    asks_for_list = any(
        token in user_text
        for token in ("listado", "lista", "listar", "todos", "todas", "mostrar", "dame")
    )

    if "empleado" in user_text:
        employee_tool = next(
            (
                name
                for name in (
                    "consultar_empleados_mcp_administrador",
                    "consultar_empleados_mcp_empleado",
                )
                if name in tool_names
            ),
            None,
        )
        if employee_tool:
            return {
                "name": employee_tool,
                "args": {},
                "id": "direct_empleados_query",
            }
        return {
            "name": "",
            "error": (
                "No tenes permisos para consultar empleados con el rol actual. "
                "Este rol no tiene acceso a la base de empleados."
            ),
        }

    if "cliente" in user_text and asks_for_list:
        return {
            "name": "",
            "error": "La base SQLite disponible contiene únicamente empleados.",
        }

    return None


def invoke_specialist_agent(
    *,
    system_prompt: str,
    messages: List[BaseMessage],
    tools: List[Any] | None = None,
) -> Dict[str, List[BaseMessage]]:
    """Run one specialist agent - EL LLM SIEMPRE TIENE LA ÚLTIMA PALABRA."""

    # ──────────────────────────────────────────────────────────
    # 1. PREPARAR EL MODELO
    # ──────────────────────────────────────────────────────────
    model = build_chat_model()
    prepared_messages: List[BaseMessage] = [SystemMessage(content=system_prompt)] + list(messages)

    bound_model = model
    if tools:
        try:
            bound_model = model.bind_tools(tools)
            logger.info(f"🔧 Herramientas bindeadas: {[t.name for t in tools]}")
        except Exception as exc:
            logger.warning("bind_tools no disponible: %s", exc)
            bound_model = model

    # ──────────────────────────────────────────────────────────
    # 2. PRIMERA INVOCACIÓN: LLM decide qué hacer
    # ──────────────────────────────────────────────────────────
    logger.info("🤖 LLM decide qué acción tomar...")
    first_ai = _invoke_with_fallback(bound_model, prepared_messages, tools)
    new_messages: List[BaseMessage] = [first_ai]

    # ──────────────────────────────────────────────────────────
    # 3. EXTRAER TOOL CALLS
    # ──────────────────────────────────────────────────────────
    tool_calls = getattr(first_ai, "tool_calls", None) or []
    
    if not tool_calls:
        content = getattr(first_ai, "content", "")
        tool_calls = _tool_calls_from_text(content)
        
        if tool_calls and isinstance(content, str):
            clean_content = _clean_tool_tags(content)
            if clean_content and clean_content != content:
                first_ai.content = clean_content
                new_messages[0] = first_ai

    # ──────────────────────────────────────────────────────────
    # 4. SI NO HAY TOOL CALLS: El LLM ya respondió directamente
    # ──────────────────────────────────────────────────────────
    if not tool_calls:
        logger.info("💬 LLM respondió directamente (sin herramientas)")
        return {"messages": new_messages}

    # ──────────────────────────────────────────────────────────
    # 5. EJECUTAR HERRAMIENTAS
    # ──────────────────────────────────────────────────────────
    logger.info(f"🔧 Ejecutando {len(tool_calls)} herramienta(s)...")
    
    tool_map = {tool_obj.name: tool_obj for tool_obj in tools}
    tool_messages: List[ToolMessage] = []

    for call in tool_calls:
        call_name = call.get("name") if isinstance(call, dict) else getattr(call, "name", "")
        call_args = call.get("args") if isinstance(call, dict) else getattr(call, "args", {})
        call_id = call.get("id") if isinstance(call, dict) else getattr(call, "id", None)

        tool_obj = tool_map.get(call_name)
        if tool_obj is None:
            tool_messages.append(
                ToolMessage(
                    content=safe_json({"error": f"Tool no permitida: {call_name}"}),
                    tool_call_id=str(call_id or "unknown"),
                )
            )
            continue

        try:
            logger.info(f"⚙️ Ejecutando: {call_name} con args: {call_args}")
            result = tool_obj.invoke(call_args or {})
        except Exception as exc:
            result = safe_json({"error": f"Error ejecutando tool {call_name}: {exc}"})

        result_content = result if isinstance(result, str) else safe_json(result)
        result_content = _truncate_tool_result_if_needed(result_content)

        tool_messages.append(
            ToolMessage(
                content=result_content,
                tool_call_id=str(call_id or "unknown"),
            )
        )

    # ──────────────────────────────────────────────────────────
    # 6. 🎯 SEGUNDA INVOCACIÓN: EL LLM GENERA LA RESPUESTA FINAL
    # ──────────────────────────────────────────────────────────
    if tool_messages:
        new_messages.extend(tool_messages)
        
        full_messages = prepared_messages + [first_ai] + tool_messages
        
        logger.info("🤖 LLM generando respuesta final con resultados...")
        
        final_ai = _invoke_with_fallback(bound_model, full_messages, tools)
        
        # ─── VERIFICAR SI EL LLM GENERÓ OTRO TOOL CALL ───
        final_content = getattr(final_ai, "content", "") or ""
        final_tool_calls = getattr(final_ai, "tool_calls", None) or []
        
        if final_tool_calls:
            logger.warning("⚠️ El LLM generó otro tool call nativo, forzando fallback")
            fallback_content = _format_tool_result_for_user(
                tool_messages,
                user_text=_last_human_text(messages),
            )
            final_ai = AIMessage(content=fallback_content)
        elif _looks_like_text_tool_call(final_content):
            logger.warning("⚠️ El LLM generó tool call en texto, forzando fallback")
            fallback_content = _format_tool_result_for_user(
                tool_messages,
                user_text=_last_human_text(messages),
            )
            final_ai = AIMessage(content=fallback_content)
        elif not final_content.strip():
            logger.warning("⚠️ El LLM no generó contenido, usando fallback")
            fallback_content = _format_tool_result_for_user(
                tool_messages,
                user_text=_last_human_text(messages),
            )
            final_ai = AIMessage(content=fallback_content)
        else:
            logger.info(f"✅ LLM generó respuesta válida: {final_content[:100]}...")
        
        new_messages.append(final_ai)
    
    # ──────────────────────────────────────────────────────────
    # 🛡️ GARANTIZAR RESPUESTA VÁLIDA
    # ──────────────────────────────────────────────────────────
    new_messages = _ensure_valid_response(
        new_messages,
        fallback_content="He procesado tu consulta."
    )

    # ──────────────────────────────────────────────────────────
    # ✅ LOG FINAL PARA DEPURACIÓN
    # ──────────────────────────────────────────────────────────
    if new_messages:
        last_msg = new_messages[-1]
        if isinstance(last_msg, AIMessage):
            content = getattr(last_msg, "content", "") or ""
            logger.info(f"📤 Mensaje final: {content[:200]}..." if len(content) > 200 else f"📤 Mensaje final: {content}")
        else:
            logger.warning(f"⚠️ El último mensaje no es AIMessage: {type(last_msg).__name__}")

    return {"messages": new_messages}
