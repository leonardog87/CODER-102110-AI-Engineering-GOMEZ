"""LangGraph assembly con orquestador y especialistas."""

from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from agent_system.chatbot_agent import chatBot
from agent_system.code_editor_agent import codeEditor
from agent_system.constants import AGENT_CHATBOT, AGENT_CODE_EDITOR, AGENT_ORCHESTRATOR, AGENT_PROJECT_READER
from agent_system.orchestrator import orchestrator, route_next_agent
from agent_system.project_reader_agent import projectReader
from agent_system.state import AgentState

logging.basicConfig(level=logging.INFO)

builder = StateGraph(AgentState)

builder.add_node(AGENT_ORCHESTRATOR, orchestrator)
builder.add_node(AGENT_CHATBOT, chatBot)
builder.add_node(AGENT_PROJECT_READER, projectReader)
builder.add_node(AGENT_CODE_EDITOR, codeEditor)

builder.add_edge(START, AGENT_ORCHESTRATOR)
builder.add_conditional_edges(
    AGENT_ORCHESTRATOR,
    route_next_agent,
    {
        AGENT_CHATBOT: AGENT_CHATBOT,
        AGENT_PROJECT_READER: AGENT_PROJECT_READER,
        AGENT_CODE_EDITOR: AGENT_CODE_EDITOR,
    },
)
builder.add_edge(AGENT_CHATBOT, END)
builder.add_edge(AGENT_PROJECT_READER, END)
builder.add_edge(AGENT_CODE_EDITOR, END)

app_graph = builder.compile()

__all__ = ["app_graph", "route_next_agent"]
