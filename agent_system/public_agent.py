"""Public specialist agent."""

from __future__ import annotations

import logging
from typing import Dict, List

from langchain_core.messages import BaseMessage

from agent_system.prompts import SYSTEM_PROMPT_PUBLICO
from agent_system.runtime import invoke_specialist_agent
from agent_system.state import AgentState

logger = logging.getLogger("ciudad_analitica.agent_system.public_agent")

PUBLIC_TOOLS = []


def agente_publico(state: AgentState) -> Dict[str, List[BaseMessage]]:
    logger.info("Ejecutando agente_publico")
    return invoke_specialist_agent(
        system_prompt=SYSTEM_PROMPT_PUBLICO,
        messages=state["messages"],
        tools=PUBLIC_TOOLS,
    )
