"""Shared LangGraph state definitions."""

from __future__ import annotations

from typing import Annotated, List, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

UserRole = Literal["Invitado", "Soporte_Nivel_1", "Admin_Nivel_2"]
AgentName = Literal["agente_publico", "agente_soporte", "agente_admin"]


class AgentState(TypedDict, total=False):
    """State shared by the manager and specialist agents."""

    messages: Annotated[List[BaseMessage], add_messages]
    rol_usuario: UserRole
    agente_designado: AgentName
    motivo_designacion: str
