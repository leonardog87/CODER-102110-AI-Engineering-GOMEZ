"""Shared LangGraph state definitions."""

from __future__ import annotations

from typing import Annotated, List, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

AgentName = Literal["chatBot"]
EvaluationDecision = Literal["retry", "end"]


class AgentState(TypedDict, total=False):
    """Estado compartido por el único agente."""

    messages: Annotated[List[BaseMessage], add_messages]
    agente_designado: AgentName
    motivo_designacion: str
    cycle_count: int
    evaluation_decision: EvaluationDecision
    evaluation_reason: str
