"""API HTTP del chatBot genérico."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Annotated, Any, Dict, List, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from pydantic import BaseModel, Field

from agent_system import app_graph
from data_access.database import close_connection
from data_access.query_history import clear_query_history, load_query_history, save_query_record
from agent_system.project_index import _project_root


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)
    conversation_history: List[ChatMessage] = Field(default_factory=list, max_length=20)


class ChatResponse(BaseModel):
    answer: str
    sources: List[str]
    audit: Dict[str, Any]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    agent: str
    knowledge_source: Literal["repositorios"]
    repository_available: bool


class ClearHistoryResponse(BaseModel):
    deleted: int
    message: str


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
                    "tool_name": message.additional_kwargs.get("tool_name"),
                    "content": message.content,
                }
            )
    return traces


def _allowed_origins() -> List[str]:
    value = os.getenv("API_CORS_ORIGINS", "http://localhost:3000;http://localhost:5173")
    return [origin.strip() for origin in value.replace(",", ";").split(";") if origin.strip()]


def _sources_from_result(result: Dict[str, Any]) -> List[str]:
    """Informa la fuente efectiva del sistema en repositorios."""
    files = [str(path) for path in result.get("project_files", []) if str(path).strip()]
    return files or ["repositorios"]


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Libera la conexión SQLite compartida al apagar el servidor."""
    yield
    close_connection()


app = FastAPI(
    title="chatBot API",
    description="API para consultar y modificar el proyecto real dentro de repositorios.",
    version="3.0.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "system", "description": "Estado del servicio."},
        {"name": "chat", "description": "Conversación e historial."},
    ],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        agent="chatBot",
        knowledge_source="repositorios",
        repository_available=_project_root().is_dir(),
    )


@app.post("/api/chat", response_model=ChatResponse, tags=["chat"])
def chat(request: ChatRequest) -> ChatResponse:
    try:
        result = app_graph.invoke({"messages": _messages_for_graph(request)})
    except Exception as exc:
        raise HTTPException(status_code=503, detail="El agente no está disponible.") from exc

    messages = result.get("messages", [])
    answer = _last_answer(messages)
    traces = _tool_traces(messages)
    audit = {
        "agent": result.get("agente_designado"),
        "designation_reason": result.get("motivo_designacion"),
        "cycle_count": 1,
        "evaluation_decision": "end",
        "evaluation_reason": "Ejecución directa del agente único.",
        "tool_traces": traces,
    }

    try:
        record_id = save_query_record(
            role="General",
            agent_name=audit["agent"] or "chatBot",
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

    return ChatResponse(
        answer=answer,
        sources=_sources_from_result(result),
        audit=audit,
    )


@app.get("/api/history", tags=["chat"])
def history(
    limit: Annotated[int, Query(ge=1, le=500, description="Cantidad de registros.")] = 100,
) -> List[Dict[str, Any]]:
    try:
        return load_query_history("General", limit=limit)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="No se pudo recuperar el historial.",
        ) from exc


@app.delete("/api/history", response_model=ClearHistoryResponse, tags=["chat"])
def clear_history() -> ClearHistoryResponse:
    """Elimina explícitamente todas las preguntas, respuestas y auditorías."""
    try:
        deleted = clear_query_history("General")
        return ClearHistoryResponse(
            deleted=deleted,
            message="Historial eliminado correctamente.",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail="No se pudo limpiar el historial.") from exc
