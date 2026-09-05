"""LangGraph assembly."""

from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from agent_system.constants import (
    AGENT_EMPLEADO,
    AGENT_INVITADO,
    AGENT_MANAGER,
)
from agent_system.empleado_agent import agente_empleado
from agent_system.evaluator_agent import (
    enrutar_despues_evaluacion,
    evaluar_respuesta,
)
from agent_system.invitado_agent import agente_invitado
from agent_system.manager_agent import agente_encargado, enrutar_por_designacion
from agent_system.state import AgentState

logging.basicConfig(level=logging.INFO)

builder = StateGraph(AgentState)

builder.add_node(AGENT_MANAGER, agente_encargado)
builder.add_node(AGENT_INVITADO, agente_invitado)
builder.add_node(AGENT_EMPLEADO, agente_empleado)
builder.add_node("evaluador_respuesta", evaluar_respuesta)

builder.add_edge(START, AGENT_MANAGER)
builder.add_conditional_edges(
    AGENT_MANAGER,
    enrutar_por_designacion,
    {
        AGENT_INVITADO: AGENT_INVITADO,
        AGENT_EMPLEADO: AGENT_EMPLEADO,
    },
)

builder.add_edge(AGENT_INVITADO, "evaluador_respuesta")
builder.add_edge(AGENT_EMPLEADO, "evaluador_respuesta")
builder.add_conditional_edges(
    "evaluador_respuesta",
    enrutar_despues_evaluacion,
    {
        "retry": AGENT_MANAGER,
        "end": END,
    },
)

app_graph = builder.compile()
