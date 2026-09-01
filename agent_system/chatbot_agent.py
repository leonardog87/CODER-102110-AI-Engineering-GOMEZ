"""Agente conversacional del proyecto, ampliado para comprender archivos locales."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List

from langchain_core.messages import BaseMessage

from agent_system.project_index import _project_root as resolve_project_root
from agent_system.project_index import query_project_index
from agent_system.prompts import SYSTEM_PROMPT_CHATBOT
from agent_system.runtime import invoke_specialist_agent
from agent_system.state import AgentState

logger = logging.getLogger("chatBot.agent_system")


def _project_root() -> Path:
    return resolve_project_root()


def _last_human_message(state: AgentState) -> str:
    for message in reversed(state.get("messages", [])):
        if getattr(message, "type", None) == "human":
            return str(getattr(message, "content", "") or "")
    return ""


def _project_file_context(limit: int = 40) -> str:
    """Lee archivos del proyecto real desde repositorios y los resume para contexto."""
    root = _project_root()
    skip_dirs = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules", ".idea", ".vs"}
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        suffix = path.suffix.lower()
        if suffix not in {".py", ".md", ".yaml", ".yml", ".json", ".toml", ".txt", ".js", ".ts", ".tsx", ".cs", ".csproj", ".sln", ".aspx", ".aspx.cs", ".html", ".htm"}:
            continue
        files.append(path)
        if len(files) >= limit:
            break

    if not files:
        return "No se encontraron archivos relevantes dentro de repositorios para analizar el proyecto real."

    summaries: List[str] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        excerpt = "\n".join(text.splitlines()[:35])
        if excerpt.strip():
            summaries.append(f"Archivo: {path.relative_to(root)}\n{excerpt[:1200]}\n")
    return "\n\n".join(summaries)


def chatBot(state: AgentState) -> Dict[str, List[BaseMessage] | str]:
    """Responde usando el proyecto real del repositorio, sin depender de contenidos parametrizados."""
    logger.info("Ejecutando chatBot")
    question = _last_human_message(state)
    project_context = query_project_index(question, root=_project_root(), k=None) if question else _project_file_context()
    if not project_context.strip():
        project_context = _project_file_context()
    generated = invoke_specialist_agent(
        system_prompt=f"{SYSTEM_PROMPT_CHATBOT}\n\nCONTEXTO DEL REPOSITORIO:\n{project_context}",
        messages=state.get("messages", []),
    )["messages"]
    result = {
        "messages": generated,
        "agente_designado": "chatBot",
        "motivo_designacion": "Consulta general sobre el proyecto real y su estructura.",
        "project_context": project_context,
    }
    return result
