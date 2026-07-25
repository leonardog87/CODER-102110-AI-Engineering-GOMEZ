"""Support level 1 specialist agent."""

from __future__ import annotations

import logging
from typing import Dict, List

from langchain_core.messages import BaseMessage

from agent_system.prompts import SYSTEM_PROMPT_SOPORTE
from agent_system.runtime import invoke_specialist_agent
from agent_system.state import AgentState
from agent_system.tools import consultar_clientes_mcp_soporte, rag_retrieve_context

logger = logging.getLogger("ciudad_analitica.agent_system.support_agent")

SUPPORT_TOOLS = [rag_retrieve_context, consultar_clientes_mcp_soporte]


def agente_soporte(state: AgentState) -> Dict[str, List[BaseMessage]]:
    logger.info("Ejecutando agente_soporte")
    return invoke_specialist_agent(
        system_prompt=SYSTEM_PROMPT_SOPORTE,
        messages=state["messages"],
        tools=SUPPORT_TOOLS,
    )
