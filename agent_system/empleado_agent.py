"""Agente especialista para el rol Empleado."""

from __future__ import annotations

import logging
from typing import Dict, List

from langchain_core.messages import BaseMessage

from agent_system.prompts import SYSTEM_PROMPT_EMPLEADO
from agent_system.retrieval_policy import enabled_tools
from agent_system.runtime import invoke_specialist_agent
from agent_system.state import AgentState
from agent_system.tools import (
    rag_retrieve_context,
    verificar_respuesta_con_fuentes,
)

logger = logging.getLogger("agente_corporativo.agent_system.empleado_agent")

EMPLEADO_TOOLS = enabled_tools([
    rag_retrieve_context,
    verificar_respuesta_con_fuentes,
])


def agente_empleado(state: AgentState) -> Dict[str, List[BaseMessage]]:
    logger.info("Ejecutando agente_empleado")
    return invoke_specialist_agent(
        system_prompt=SYSTEM_PROMPT_EMPLEADO,
        messages=state["messages"],
        tools=EMPLEADO_TOOLS,
    )
