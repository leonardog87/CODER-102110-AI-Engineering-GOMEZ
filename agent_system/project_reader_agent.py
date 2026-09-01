"""Agente especialista en lectura del proyecto y comprensión de procesos."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Dict, List

from langchain_core.messages import BaseMessage

from agent_system.project_index import _project_root as resolve_project_root
from agent_system.project_index import (
    expand_related_context, expand_structural_context, query_project_index,
)
from agent_system.prompts import SYSTEM_PROMPT_PROJECT_READER
from agent_system.runtime import invoke_specialist_agent
from agent_system.state import AgentState

logger = logging.getLogger("chatBot.agent_system.project_reader")


def _bounded_context(primary: str, related: str) -> str:
    """Distribuye el presupuesto entre evidencia inicial y referencias cruzadas."""
    budget = max(6000, int(os.getenv("PROJECT_READER_MAX_CONTEXT_CHARS", "20000")))
    if not related:
        return primary[:budget]
    primary_budget = min(len(primary), int(budget * 0.55))
    related_budget = budget - primary_budget
    return (
        f"{primary[:primary_budget]}\n\n"
        "CONTEXTO RELACIONADO (usos e implementaciones):\n"
        f"{related[:related_budget]}"
    )


def _project_root() -> Path:
    return resolve_project_root()


def _collect_project_overview() -> str:
    root = _project_root()
    skip_dirs = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules", ".idea", ".vs"}
    files: List[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.suffix.lower() in {".py", ".cs", ".aspx", ".aspx.cs", ".js", ".html", ".htm", ".md", ".yaml", ".yml", ".json", ".toml", ".txt"}:
            files.append(path)

    overview: List[str] = []
    for path in files[:120]:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        excerpt = "\n".join(text.splitlines()[:40])
        if excerpt.strip():
            overview.append(f"Archivo: {path.relative_to(root)}\n{excerpt[:1500]}\n")
    return "\n\n".join(overview)


def _extract_requested_file_name(user_text: str) -> str | None:
    cleaned = (user_text or "").strip()
    if not cleaned:
        return None
    # Prioriza nombres explícitos de archivo, incluso si vienen dentro de frases naturales.
    match = re.search(r"\b([A-Za-z0-9_\-]+\.aspx)\b", cleaned, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r"\b([A-Za-z0-9_\-]+\.cs)\b", cleaned, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r"\b([A-Za-z0-9_\-]+\.js)\b", cleaned, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r"(?:archivo|file|pagina|página|page)\s*[:\-]?\s*([A-Za-z0-9_./\\-]+)", cleaned, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def projectReader(state: AgentState) -> Dict[str, List[BaseMessage] | str]:
    """Analiza el proyecto y devuelve contexto real del repositorio, incluyendo archivos concretos pedidos por el usuario."""
    messages = state.get("messages", [])
    user_text = ""
    for message in reversed(messages):
        if getattr(message, "type", None) == "human":
            user_text = str(getattr(message, "content", "") or "")
            break

    requested_file = _extract_requested_file_name(user_text)
    root = _project_root()
    overview = query_project_index(user_text, root=root, k=None) if user_text else ""
    if not overview.strip():
        overview = _collect_project_overview()
    if requested_file:
        normalized = requested_file.replace("\\", "/")
        matches = [
            path for path in sorted(root.rglob("*"))
            if path.is_file() and path.name.lower() == Path(normalized).name.lower()
        ]
        if matches:
            selected: List[str] = []
            for path in matches[:10]:
                try:
                    text = path.read_text(encoding="utf-8")
                except Exception:
                    continue
                excerpt = "\n".join(text.splitlines()[:80])
                if excerpt.strip():
                    selected.append(f"Archivo: {path.relative_to(root)}\n{excerpt[:3000]}\n")
            if selected:
                overview = "\n\n".join(selected)

    structural = expand_structural_context(overview, root=root)
    primary = f"{overview}\n\nARCHIVOS VINCULADOS DEL MÓDULO:\n{structural}" if structural else overview
    related = expand_related_context(user_text, primary, root=root)
    overview = _bounded_context(primary, related)

    logger.info("Ejecutando projectReader sobre archivos del repositorio")
    prompt = f"{SYSTEM_PROMPT_PROJECT_READER}\n\nCONTEXTO RECUPERADO DEL REPOSITORIO:\n{overview}"
    generated = invoke_specialist_agent(system_prompt=prompt, messages=messages)["messages"]
    return {
        "messages": generated,
        "agente_designado": "projectReader",
        "motivo_designacion": "Se requiere analizar la estructura, archivos y procesos del proyecto real.",
        "project_context": overview,
        "project_files": [line.split("Archivo: ", 1)[1].split("\n", 1)[0] for line in overview.splitlines() if line.startswith("Archivo: ")],
    }
