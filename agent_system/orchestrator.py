"""Orquestador del sistema: decide entre lectura del proyecto y edición del código."""

from __future__ import annotations

import logging
import re
from typing import Dict, List

from langchain_core.messages import BaseMessage

from agent_system.constants import AGENT_CHATBOT, AGENT_CODE_EDITOR, AGENT_ORCHESTRATOR, AGENT_PROJECT_READER
from agent_system.state import AgentState

logger = logging.getLogger("chatBot.agent_system.orchestrator")


_EXPLANATION_REQUEST = re.compile(
    r"(?:^|[¿?]\s*)"
    r"(?:explic(?:a|ame|á|áme)|describ(?:e|ime|í|íme)|"
    r"(?:c[oó]mo|cu[aá]l(?:es)?|qu[eé])\s+(?:es|son|se\s+|puedo\s+)?|"
    r"(?:proceso|pasos|procedimiento|flujo)\s+(?:de|para))\b"
)


def _is_explanation_request(text: str) -> bool:
    """Distingue una consulta sobre una acción de una orden para ejecutarla."""
    return bool(_EXPLANATION_REQUEST.search(text))


def _last_user_text(messages: List[BaseMessage]) -> str:
    for message in reversed(messages):
        if getattr(message, "type", None) == "human":
            return str(getattr(message, "content", "") or "").strip()
    return ""


def route_next_agent(state: AgentState) -> str:
    """Direccionaliza la ejecución según la intención del usuario."""
    context = _last_user_text(state.get("messages", []))
    text = (context or "").lower()

    # "Cómo crear un usuario" menciona una acción, pero no solicita editar el
    # repositorio. Las consultas explicativas deben resolverse por lectura aun
    # cuando contengan verbos como crear, modificar o eliminar.
    if _is_explanation_request(text) and re.search(
        r"(modific|actualiz|cre(?:a|ar|á)|gener(?:a|ar|á)|implement|agreg|añad|elimin|borr|corrig|cambi|refactor|reemplaz)",
        text,
    ):
        logger.info("Orquestador seleccionó %s para consulta explicativa", AGENT_PROJECT_READER)
        return AGENT_PROJECT_READER

    if re.search(
        r"(modific|actualiz|cre(?:a|ar|á)|gener(?:a|ar|á)|implement|agreg|añad|elimin|borr|corrig|cambi|refactor|reemplaz)",
        text,
    ):
        logger.info("Orquestador seleccionó %s para edición", AGENT_CODE_EDITOR)
        return AGENT_CODE_EDITOR

    if re.search(
        r"(\.aspx|\.cs|\.js|\.html|\.htm|\.tsx|\.ts|\.py|principal\.aspx|que es .*\.aspx|qué es .*\.aspx|archivo .*\.aspx|archivo .*\.cs|pagina .*\.aspx|página .*\.aspx|arquitectura|estructura|proyecto|analiz|explica|resumen|documenta|proceso|flujo|carpeta|repositorio|readme|codigo|código|app.py|api.py|module|dependencia|service|backend|frontend)",
        text,
    ):
        logger.info("Orquestador seleccionó %s para análisis del proyecto", AGENT_PROJECT_READER)
        return AGENT_PROJECT_READER

    logger.info("Orquestador seleccionó %s para respuesta general", AGENT_CHATBOT)
    return AGENT_CHATBOT


def orchestrator(state: AgentState) -> Dict[str, List[BaseMessage] | str]:
    """Nodo central que decide el siguiente especialista."""
    decision = route_next_agent(state)
    if decision == AGENT_CODE_EDITOR:
        reason = "La solicitud requiere edición o creación de código."
    elif decision == AGENT_PROJECT_READER:
        reason = "La solicitud requiere analizar el proyecto, su arquitectura y sus procesos."
    else:
        reason = "La solicitud es una consulta general que debe responder el agente conversacional."
    logger.info("agente_designado=%s motivo=%s", AGENT_ORCHESTRATOR, reason)
    return {
        "messages": state.get("messages", []),
        "agente_designado": AGENT_ORCHESTRATOR,
        "motivo_designacion": reason,
        "selected_agent": decision,
    }
