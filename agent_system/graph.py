"""LangGraph assembly."""

from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from agent_system.constants import AGENT_ADMIN, AGENT_MANAGER, AGENT_PUBLIC, AGENT_SUPPORT
from agent_system.admin_agent import agente_admin
from agent_system.manager_agent import agente_encargado, enrutar_por_designacion
from agent_system.public_agent import agente_publico
from agent_system.state import AgentState
from agent_system.support_agent import agente_soporte

logging.basicConfig(level=logging.INFO)

builder = StateGraph(AgentState)

builder.add_node(AGENT_MANAGER, agente_encargado)
builder.add_node(AGENT_PUBLIC, agente_publico)
builder.add_node(AGENT_SUPPORT, agente_soporte)
builder.add_node(AGENT_ADMIN, agente_admin)

builder.add_edge(START, AGENT_MANAGER)
builder.add_conditional_edges(
    AGENT_MANAGER,
    enrutar_por_designacion,
    {
        AGENT_PUBLIC: AGENT_PUBLIC,
        AGENT_SUPPORT: AGENT_SUPPORT,
        AGENT_ADMIN: AGENT_ADMIN,
    },
)

builder.add_edge(AGENT_PUBLIC, END)
builder.add_edge(AGENT_SUPPORT, END)
builder.add_edge(AGENT_ADMIN, END)

app_graph = builder.compile()
