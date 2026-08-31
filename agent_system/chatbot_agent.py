"""Único agente conversacional del proyecto."""

from __future__ import annotations

import logging
from typing import Dict, List

from langchain_core.messages import BaseMessage

from agent_system.prompts import SYSTEM_PROMPT_CHATBOT
from agent_system.retrieval_policy import enabled_tools
from agent_system.runtime import invoke_specialist_agent
from agent_system.state import AgentState
from agent_system.tools import (
    knowledge_retrieve_context,
)
from agent_system.web_tools import (
    primary_retrieve_context,
    web_retrieve_allowed_url,
    web_search_allowed,
)

logger = logging.getLogger("chatBot.agent_system")

CHATBOT_TOOLS = enabled_tools([
    knowledge_retrieve_context,
    primary_retrieve_context,
    web_search_allowed,
    web_retrieve_allowed_url,
])


def chatBot(state: AgentState) -> Dict[str, List[BaseMessage] | str]:
    """Responde usando exclusivamente knowledge_base."""
    logger.info("Ejecutando chatBot")
    result = invoke_specialist_agent(
        system_prompt=SYSTEM_PROMPT_CHATBOT,
        messages=state["messages"],
        tools=CHATBOT_TOOLS,
    )
    return {
        **result,
        "agente_designado": "chatBot",
        "motivo_designacion": "Agente único del proyecto.",
    }
