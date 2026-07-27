"""Evaluación de respuestas y control del ciclo de LangGraph."""

from __future__ import annotations

import json
import logging
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent_system.state import AgentState

logger = logging.getLogger("agente_corporativo.agent_system.evaluator_agent")

MAX_AGENT_CYCLES = 2
GENERIC_RESPONSES = {
    "",
    "he procesado tu consulta.",
    "no se pudo recuperar una respuesta textual del grafo, pero la interacción fue procesada.",
}


def _last_ai_content(state: AgentState) -> str:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, AIMessage):
            return str(message.content or "").strip()
    return ""


def _has_retryable_tool_error(state: AgentState) -> bool:
    """Detecta errores técnicos; rechazos RBAC 4xx son respuestas definitivas."""
    for message in reversed(state.get("messages", [])):
        if not isinstance(message, ToolMessage):
            continue
        try:
            payload = json.loads(str(message.content))
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        status_code = payload.get("status_code")
        if isinstance(status_code, int) and status_code >= 500:
            return True
        if payload.get("error"):
            return True
    return False


def _employee_query_without_tool(state: AgentState) -> bool:
    """Impide finalizar consultas de empleados sin evidencia MCP del turno."""
    messages = state.get("messages", [])
    last_human_index = -1
    user_text = ""
    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], HumanMessage):
            last_human_index = index
            user_text = str(messages[index].content or "").lower()
            break
    if last_human_index < 0 or "empleado" not in user_text:
        return False

    role = state.get("rol_usuario")
    if role not in {"Empleado", "Administrador"}:
        return False
    return not any(
        isinstance(message, ToolMessage)
        for message in messages[last_human_index + 1 :]
    )


def evaluar_respuesta(state: AgentState) -> dict:
    """Decide si la respuesta finaliza o vuelve al manager para otro ciclo."""
    completed_cycles = int(state.get("cycle_count", 0)) + 1
    content = _last_ai_content(state)

    retry_reason = ""
    if content.lower() in GENERIC_RESPONSES:
        retry_reason = "La respuesta está vacía o es demasiado genérica."
    elif _employee_query_without_tool(state):
        retry_reason = (
            "La consulta de empleados finalizó sin ejecutar la herramienta MCP obligatoria."
        )
    elif _has_retryable_tool_error(state):
        retry_reason = "Una herramienta devolvió un error técnico recuperable."

    can_retry = bool(retry_reason) and completed_cycles < MAX_AGENT_CYCLES
    decision: Literal["retry", "end"] = "retry" if can_retry else "end"

    if not retry_reason:
        reason = "La respuesta contiene información suficiente para finalizar."
    elif can_retry:
        reason = f"{retry_reason} Se realizará un nuevo ciclo."
    else:
        reason = f"{retry_reason} Se alcanzó el límite de ciclos."

    logger.info(
        "Evaluación ciclo=%s decisión=%s motivo=%s",
        completed_cycles,
        decision,
        reason,
    )
    return {
        "cycle_count": completed_cycles,
        "evaluation_decision": decision,
        "evaluation_reason": reason,
    }


def enrutar_despues_evaluacion(
    state: AgentState,
) -> Literal["retry", "end"]:
    """Devuelve la rama calculada por el evaluador."""
    return state.get("evaluation_decision", "end")
