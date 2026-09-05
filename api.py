"""HTTP API for the corporate agent, intended for C# and JavaScript clients."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, Field

from agent_system import app_graph
from data_access.query_history import load_query_history, save_query_record


UserRole = Literal["Invitado", "Empleado"]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)
    role: UserRole = "Invitado"
    conversation_history: List[ChatMessage] = Field(default_factory=list, max_length=20)


class ChatResponse(BaseModel):
    answer: str
    role: UserRole
    audit: Dict[str, Any]


def _messages_for_graph(request: ChatRequest) -> List[BaseMessage]:
    messages: List[BaseMessage] = []
    for item in request.conversation_history:
        message_type = HumanMessage if item.role == "user" else AIMessage
        messages.append(message_type(content=item.content))
    messages.append(HumanMessage(content=request.message))
    return messages


def _last_answer(messages: List[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage) and str(message.content).strip():
            return str(message.content)
    return "No se pudo recuperar una respuesta textual del agente."


def _tool_traces(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
    traces: List[Dict[str, Any]] = []
    for message in messages:
        if isinstance(message, ToolMessage):
            traces.append(
                {
                    "tool_call_id": getattr(message, "tool_call_id", None),
                    "content": message.content,
                }
            )
    return traces


def _allowed_origins() -> List[str]:
    value = os.getenv("API_CORS_ORIGINS", "http://localhost:3000;http://localhost:5173")
    return [origin.strip() for origin in value.replace(",", ";").split(";") if origin.strip()]


app = FastAPI(
    title="Agente Corporativo IA API",
    version="1.1.0",
    description="API HTTP del agente corporativo para clientes web y de escritorio.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health", tags=["health"])
@app.get("/health/live", tags=["health"])
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
async def readiness() -> Dict[str, str]:
    try:
        await run_in_threadpool(load_query_history, "Invitado", 1)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Persistencia no disponible.") from exc
    return {"status": "ready"}


@app.post("/api/chat", response_model=ChatResponse, tags=["chat"])
async def chat(request: ChatRequest) -> ChatResponse:
    try:
        result = await run_in_threadpool(
            app_graph.invoke,
            {"messages": _messages_for_graph(request), "rol_usuario": request.role},
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="El agente no está disponible.") from exc

    messages = result.get("messages", [])
    answer = _last_answer(messages)
    traces = _tool_traces(messages)
    audit = {
        "agent": result.get("agente_designado"),
        "designation_reason": result.get("motivo_designacion"),
        "cycle_count": result.get("cycle_count", 1),
        "evaluation_decision": result.get("evaluation_decision", "end"),
        "evaluation_reason": result.get("evaluation_reason"),
        "tool_traces": traces,
    }

    try:
        record_id = await run_in_threadpool(
            save_query_record,
            role=request.role,
            agent_name=audit["agent"] or "agente_invitado",
            user_query=request.message,
            assistant_response=answer,
            designation_reason=audit["designation_reason"] or "No informado.",
            tool_traces=traces,
            cycle_count=audit["cycle_count"],
            evaluation_decision=audit["evaluation_decision"],
            evaluation_reason=audit["evaluation_reason"] or "",
        )
        audit["record_id"] = record_id
    except Exception as exc:
        raise HTTPException(status_code=500, detail="No se pudo guardar la auditoría.") from exc

    return ChatResponse(answer=answer, role=request.role, audit=audit)


@app.get("/api/history/{role}", tags=["history"])
async def history(
    role: UserRole,
    limit: int = Query(default=100, ge=1, le=500),
) -> List[Dict[str, Any]]:
    return await run_in_threadpool(load_query_history, role, limit)
