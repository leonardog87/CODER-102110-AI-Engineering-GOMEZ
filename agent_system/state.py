"""Shared LangGraph state definitions."""

from __future__ import annotations

from typing import Annotated, List, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

UserRole = Literal["Invitado", "Empleado", "Administrador"]
AgentName = Literal["agente_invitado", "agente_empleado", "agente_administrador"]
EvaluationDecision = Literal["retry", "end"]


class AgentState(TypedDict, total=False):
    """State shared by the manager and specialist agents."""

    messages: Annotated[List[BaseMessage], add_messages]
    rol_usuario: UserRole
    agente_designado: AgentName
    motivo_designacion: str
    cycle_count: int
    evaluation_decision: EvaluationDecision
    evaluation_reason: str
