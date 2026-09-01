"""Edición segura de archivos guiada por contexto real del repositorio."""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage

from agent_system.models import build_chat_model
from agent_system.project_index import (
    _project_root, expand_related_context, query_project_index,
)
from agent_system.prompts import SYSTEM_PROMPT_CODE_EDITOR
from agent_system.state import AgentState

logger = logging.getLogger("chatBot.agent_system.code_editor")
ALLOWED_SUFFIXES = {
    ".asax", ".ascx", ".aspx", ".bat", ".config", ".cs", ".cshtml",
    ".csproj", ".css", ".htm", ".html", ".ini", ".js", ".json", ".md",
    ".ps1", ".py", ".scss", ".sln", ".sql", ".ts", ".tsx", ".txt",
    ".vb", ".vbproj", ".xml", ".yaml", ".yml",
}


def _last_user(messages: List[BaseMessage]) -> str:
    for message in reversed(messages):
        if getattr(message, "type", None) == "human":
            return str(message.content or "").strip()
    return ""


def _decode_plan(content: Any) -> Dict[str, Any]:
    text = str(content or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("el modelo no devolvió JSON válido") from exc
    if not isinstance(value, dict) or not isinstance(value.get("operations", []), list):
        raise ValueError("el plan de edición tiene un formato inválido")
    return value


def _safe_target(root: Path, relative: str) -> Path:
    raw = Path(str(relative).replace("\\", "/"))
    if raw.is_absolute() or ".." in raw.parts or not raw.name:
        raise ValueError(f"ruta no permitida: {relative}")
    target = (root / raw).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"ruta fuera del repositorio: {relative}") from exc
    if target.suffix.lower() not in ALLOWED_SUFFIXES:
        raise ValueError(f"tipo de archivo no permitido: {relative}")
    return target


def _atomic_write(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
        os.replace(temporary, target)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _prepare_operation(root: Path, operation: Dict[str, Any]) -> tuple[Path, str, bool]:
    target = _safe_target(root, str(operation.get("path", "")))
    action = str(operation.get("action", "")).lower()
    if action == "create":
        if target.exists():
            raise ValueError(f"no se puede crear un archivo que ya existe: {operation.get('path')}")
        content = operation.get("content")
        if not isinstance(content, str):
            raise ValueError("una creación no contiene content válido")
        return target, content, False
    if action == "replace":
        if not target.is_file():
            raise ValueError(f"no se puede modificar un archivo inexistente: {operation.get('path')}")
        old_text, new_text = operation.get("old_text"), operation.get("new_text")
        if not isinstance(old_text, str) or not old_text or not isinstance(new_text, str):
            raise ValueError("un reemplazo no contiene old_text y new_text válidos")
        try:
            current = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            current = target.read_text(encoding="latin-1")
        occurrences = current.count(old_text)
        if occurrences != 1:
            raise ValueError(
                f"el texto a reemplazar debe aparecer exactamente una vez en {operation.get('path')} (aparece {occurrences})"
            )
        return target, current.replace(old_text, new_text, 1), True
    raise ValueError(f"acción de edición no permitida: {action or '(vacía)'}")


def codeEditor(state: AgentState) -> Dict[str, Any]:
    messages = state.get("messages", [])
    request = _last_user(messages)
    root = _project_root()
    context = query_project_index(
        request, root=root, k=max(8, int(os.getenv("PROJECT_EDIT_TOP_K", "12")))
    )
    related = expand_related_context(request, context, root=root, max_symbols=8, max_chars=18000)
    if related:
        context = f"{context}\n\nREFERENCIAS RELACIONADAS:\n{related}"
    prompt = f"{SYSTEM_PROMPT_CODE_EDITOR}\n\nRAÍZ LÓGICA: {root.name}\n\nCONTEXTO:\n{context}"
    modifications: List[Dict[str, Any]] = []
    try:
        response = build_chat_model().invoke([SystemMessage(content=prompt), *messages])
        plan = _decode_plan(response.content)
        prepared = []
        for operation in plan.get("operations", []):
            if not isinstance(operation, dict):
                raise ValueError("una operación no es un objeto válido")
            prepared.append(_prepare_operation(root, operation))
        # Primero se valida todo el plan; recién después se escribe.
        for target, content, existed in prepared:
            _atomic_write(target, content)
            modifications.append({
                "status": "modified" if existed else "created",
                "path": target.relative_to(root).as_posix(),
                "bytes": len(content.encode("utf-8")),
            })
        summary = str(plan.get("summary") or "Edición completada.")
        details = "\n".join(f"- {item['status']}: `{item['path']}`" for item in modifications)
        answer = f"{summary}\n\n{details}" if details else summary
    except Exception as exc:
        logger.exception("No se pudo aplicar la edición")
        answer = f"No realicé cambios porque no pude obtener un plan de edición seguro: {exc}."

    return {
        "messages": [AIMessage(content=answer)],
        "agente_designado": "codeEditor",
        "motivo_designacion": "Se requiere crear o modificar archivos del proyecto.",
        "project_context": context,
        "project_files": [item["path"] for item in modifications],
        "modifications": modifications,
    }
