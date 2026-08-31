"""Agente especialista para el rol Administrador."""

from __future__ import annotations

import logging
from typing import Dict, List

from langchain_core.messages import BaseMessage

from agent_system.prompts import SYSTEM_PROMPT_ADMINISTRADOR
from agent_system.retrieval_policy import enabled_tools
from agent_system.runtime import invoke_specialist_agent
from agent_system.state import AgentState
from agent_system.tools import (
    combinar_politica_con_area_administrador,
    consultar_empleados_mcp_administrador,
    consultar_politica_aplicable,
    contar_empleados_mcp_administrador,
    distribucion_empleados_mcp_administrador,
    estadisticas_salariales_mcp_administrador,
    knowledge_retrieve_context,
    rag_retrieve_context,
    verificar_respuesta_con_fuentes,
)
from agent_system.web_tools import web_retrieve_allowed_url, web_search_allowed

logger = logging.getLogger("agente_corporativo.agent_system.administrador_agent")

ADMINISTRADOR_TOOLS = enabled_tools([
    rag_retrieve_context,
    knowledge_retrieve_context,
    consultar_empleados_mcp_administrador,
    contar_empleados_mcp_administrador,
    distribucion_empleados_mcp_administrador,
    estadisticas_salariales_mcp_administrador,
    consultar_politica_aplicable,
    combinar_politica_con_area_administrador,
    verificar_respuesta_con_fuentes,
    web_search_allowed,
    web_retrieve_allowed_url,
])

def agente_administrador(state: AgentState) -> Dict[str, List[BaseMessage]]:
    logger.info("Ejecutando agente_administrador")
    return invoke_specialist_agent(
        system_prompt=SYSTEM_PROMPT_ADMINISTRADOR,
        messages=state["messages"],
        tools=ADMINISTRADOR_TOOLS,
    )
