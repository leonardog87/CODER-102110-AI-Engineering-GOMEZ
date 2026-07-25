"""Administration level 2 specialist agent."""

from __future__ import annotations

import logging
from typing import Dict, List

from langchain_core.messages import BaseMessage

from agent_system.prompts import SYSTEM_PROMPT_ADMIN
from agent_system.runtime import invoke_specialist_agent
from agent_system.state import AgentState
from agent_system.tools import (
    consultar_clientes_mcp_admin,
    consultar_empleados_mcp_admin,
    rag_retrieve_context,
)

logger = logging.getLogger("ciudad_analitica.agent_system.admin_agent")

ADMIN_TOOLS = [
    rag_retrieve_context,
    consultar_clientes_mcp_admin,
    consultar_empleados_mcp_admin,
]


def agente_admin(state: AgentState) -> Dict[str, List[BaseMessage]]:
    logger.info("Ejecutando agente_admin")
    return invoke_specialist_agent(
        system_prompt=SYSTEM_PROMPT_ADMIN,
        messages=state["messages"],
        tools=ADMIN_TOOLS,
    )
