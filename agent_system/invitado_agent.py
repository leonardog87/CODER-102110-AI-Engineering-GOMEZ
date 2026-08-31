"""Agente especialista para el rol Invitado."""

from __future__ import annotations

import logging
from typing import Dict, List

from langchain_core.messages import BaseMessage

from agent_system.prompts import SYSTEM_PROMPT_INVITADO
from agent_system.retrieval_policy import enabled_tools
from agent_system.runtime import invoke_specialist_agent
from agent_system.state import AgentState
from agent_system.tools import (
    knowledge_retrieve_context,
    verificar_respuesta_con_fuentes,
)
from agent_system.web_tools import web_retrieve_allowed_url, web_search_allowed

logger = logging.getLogger("agente_corporativo.agent_system.invitado_agent")

INVITADO_TOOLS = enabled_tools([
    knowledge_retrieve_context,
    verificar_respuesta_con_fuentes,
    web_search_allowed,
    web_retrieve_allowed_url,
])


def agente_invitado(state: AgentState) -> Dict[str, List[BaseMessage]]:
    logger.info("Ejecutando agente_invitado")
    return invoke_specialist_agent(
        system_prompt=SYSTEM_PROMPT_INVITADO,
        messages=state["messages"],
        tools=INVITADO_TOOLS,
    )
