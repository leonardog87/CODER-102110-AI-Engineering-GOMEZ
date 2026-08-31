"""LangGraph assembly."""

from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from agent_system.chatbot_agent import chatBot
from agent_system.constants import AGENT_CHATBOT
from agent_system.state import AgentState

logging.basicConfig(level=logging.INFO)

builder = StateGraph(AgentState)

builder.add_node(AGENT_CHATBOT, chatBot)
builder.add_edge(START, AGENT_CHATBOT)
builder.add_edge(AGENT_CHATBOT, END)

app_graph = builder.compile()
