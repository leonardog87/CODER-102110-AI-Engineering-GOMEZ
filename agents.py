"""Compatibility facade for the modular agent system.

The implementation now lives in the agent_system package. This file keeps the
original import contract used by app.py and classroom examples:

    from agents import app_graph
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage

from agent_system import AgentState, app_graph
from agent_system.constants import DEFAULT_ROLE

__all__ = ["AgentState", "app_graph"]


if __name__ == "__main__":
    sample_state: AgentState = {
        "messages": [HumanMessage(content="Que servicios ofrecen?")],
        "rol_usuario": DEFAULT_ROLE,
    }
    result = app_graph.invoke(sample_state)
    print(result)
