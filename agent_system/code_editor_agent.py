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

    candidates: List[str] = []
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        candidates.append(fenced.group(1))

    for start in range(len(text)):
        if text[start] == "{":
            candidates.append(text[start:])
            break

    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and isinstance(value.get("operations", []), list):
            return value

    for start in range(len(text)):
        if text[start] == "{":
            decoder = json.JSONDecoder()
            try:
                value, _ = decoder.raw_decode(text[start:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and isinstance(value.get("operations", []), list):
                return value

    raise ValueError("el modelo no devolvió JSON válido")


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


def _resolve_target(root: Path, relative: str) -> Path:
    normalized = str(relative or "").strip().replace("\\", "/")
    name = Path(normalized).name

    try:
        candidate = _safe_target(root, relative)
    except ValueError:
        candidate = None

    if candidate is not None and candidate.exists() and candidate.is_file():
        return candidate

    if normalized:
        path_matches = []
        if "/" in normalized or normalized.startswith("."):
            path_matches = [
                p for p in root.rglob("*")
                if p.is_file() and p.suffix.lower() in ALLOWED_SUFFIXES and p.as_posix().lower().endswith(normalized.lower())
            ]
        if path_matches:
            def rank(path: Path) -> tuple[int, int, str]:
                pos = path.as_posix().lower()
                score = 0
                if pos.endswith(normalized.lower()):
                    score += 1000
                if "webrh" in pos:
                    score += 250
                if "webasistencia" in pos:
                    score += 150
                if "rrhh" in pos:
                    score += 80
                score += max(0, 10 - len(path.parts))
                return (score, -len(path.parts), pos)
            return max(path_matches, key=rank)

    if name:
        matches = [p for p in root.rglob(name) if p.is_file() and p.suffix.lower() in ALLOWED_SUFFIXES]
        if matches:
            def rank(path: Path) -> tuple[int, int, str]:
                pos = path.as_posix().lower()
                score = 0
                if pos.endswith(f"/webrh/{name.lower()}") or pos.endswith(f"/webasistencia/webrh/{name.lower()}"):
                    score += 1000
                if "/formularioconcursar/" in pos:
                    score -= 500
                if "webrh" in pos:
                    score += 250
                if "webasistencia" in pos:
                    score += 150
                if "rrhh" in pos:
                    score += 80
                if name.lower() in pos:
                    score += 60
                score += max(0, 10 - len(path.parts))
                if "webasistencia" in pos or "webrh" in pos:
                    score += 30
                return (score, -len(path.parts), pos)

            return max(matches, key=rank)

    if candidate is not None:
        return candidate
    raise ValueError(f"no se pudo resolver una ruta válida para: {relative}")


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


def _replace_with_whitespace_insensitive(current: str, old_text: str, new_text: str) -> str:
    if old_text in current:
        return current.replace(old_text, new_text, 1)

    def compact(text: str) -> tuple[str, list[int]]:
        compacted = []
        positions = []
        for index, char in enumerate(text):
            if not char.isspace():
                compacted.append(char)
                positions.append(index)
        return ''.join(compacted), positions

    compacted_current, positions_current = compact(current)
    compacted_old, _ = compact(old_text)

    occurrences = []
    start = 0
    while True:
        idx = compacted_current.find(compacted_old, start)
        if idx == -1:
            break
        occurrences.append(idx)
        start = idx + 1

    if len(occurrences) != 1:
        raise ValueError(
            "el texto a reemplazar debe aparecer exactamente una vez en el archivo "
            "(incluyendo variaciones de espaciado y saltos de línea)"
        )

    target_index = occurrences[0]
    target_len = len(compacted_old)
    start_pos = positions_current[target_index]
    end_pos = positions_current[target_index + target_len - 1] + 1
    return current[:start_pos] + new_text + current[end_pos:]


def _prepare_operation(root: Path, operation: Dict[str, Any]) -> tuple[Path, str, bool]:
    requested_path = str(operation.get("path", "")).strip()
    try:
        target = _resolve_target(root, requested_path)
    except ValueError:
        if requested_path.lower().endswith("login.aspx"):
            fallback = "repositorios/rrhh/WebAsistencia/WebRH/Login.aspx"
            target = _resolve_target(root, fallback)
        else:
            raise
    action = str(operation.get("action", "")).lower()
    if action == "create":
        if target.exists():
            raise ValueError(f"no se puede crear un archivo que ya existe: {operation.get('path')}")
        content = operation.get("content")
        if not isinstance(content, str):
            raise ValueError("una creación no contiene content válido")
        return target, content, False
    if action in {"replace", "delete"}:
        if not target.is_file():
            raise ValueError(f"no se puede modificar un archivo inexistente: {operation.get('path')}")
        old_text = operation.get("old_text")
        new_text = operation.get("new_text", "") if action == "replace" else ""
        if not isinstance(old_text, str) or not old_text:
            raise ValueError("una operación de edición no contiene old_text válido")
        if not isinstance(new_text, str):
            raise ValueError("una operación de edición no contiene new_text válido")
        try:
            current = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            current = target.read_text(encoding="latin-1")

        if current.count(old_text) == 1:
            return target, current.replace(old_text, new_text, 1), True

        try:
            return target, _replace_with_whitespace_insensitive(current, old_text, new_text), True
        except ValueError as exc:
            raise ValueError(
                f"el texto a reemplazar debe aparecer exactamente una vez en {operation.get('path')}"
            ) from exc
    raise ValueError(f"acción de edición no permitida: {action or '(vacía)'}")


def _natural_create_button_operation(request: str, root: Path) -> Dict[str, Any]:
    """Genera una operación determinista para insertar un botón TEST desde un prompt normal."""
    prompt = (request or "").strip()
    lower_prompt = prompt.lower()

    if "login.aspx" in lower_prompt:
        file_hint = "repositorios/rrhh/WebAsistencia/WebRH/Login.aspx"
    elif "login" in lower_prompt:
        file_hint = "Login.aspx"
    else:
        file_hint = "Login.aspx"

    target = _resolve_target(root, file_hint)
    try:
        current = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        current = target.read_text(encoding="latin-1")

    anchor_patterns = [
        r'<button\b[^>]*id\s*=\s*["\']fat-btn["\'][^>]*>.*?</button>',
        r'<button\b[^>]*id\s*=\s*["\']fat-btn["\'][^>]*>.*?</button>\s*<br\s*/?>',
        r'<input\s+[^>]*id\s*=\s*["\']usuario["\'][^>]*>',
        r'<input\s+[^>]*id\s*=\s*["\']password["\'][^>]*>',
        r'<div\s+style\s*=\s*["\']position:\s*relative;\s*display:\s*inline-block;\s*width:\s*260px;["\']>.*?</div>',
    ]
    exact_button_match = re.search(r'<button\b[^>]*id\s*=\s*["\']fat-btn["\'][^>]*>.*?</button>', current, flags=re.IGNORECASE | re.DOTALL)
    if exact_button_match and 'btn-test' not in current.lower():
        anchor = exact_button_match.group(0)
        insertion = (
            '\n                    <button id="btn-test" type="button" class="btn btn-primary" style="margin-bottom: 15px; margin-left: 10px;">\n'
            '                        TEST\n'
            '                    </button>\n'
        )
        old_text = anchor
        new_text = anchor + insertion
        return {
            "action": "replace",
            "path": target.relative_to(root).as_posix(),
            "old_text": old_text,
            "new_text": new_text,
            "description": "Insertar un botón TEST junto al botón principal del login en la ubicación correcta."
        }

    for pattern in anchor_patterns:
        match = re.search(pattern, current, flags=re.IGNORECASE | re.DOTALL)
        if match:
            anchor = match.group(0)
            insertion = (
                '\n                    <button id="btn-test" type="button" class="btn btn-primary" style="margin-bottom: 15px; margin-left: 10px;">\n'
                '                        TEST\n'
                '                    </button>\n'
            )
            if 'btn-test' in current:
                raise ValueError("Ya existe un botón TEST en el archivo Login.aspx.")
            old_text = anchor
            new_text = anchor + insertion if 'fat-btn' in anchor.lower() else anchor.replace('</div>', insertion + '</div>', 1)
            return {
                "action": "replace",
                "path": target.relative_to(root).as_posix(),
                "old_text": old_text,
                "new_text": new_text,
                "description": "Insertar un botón TEST junto al botón principal del login en la ubicación correcta."
            }

    insertion = (
        '\n                    <button id="btn-test" type="button" class="btn btn-primary" style="margin-bottom: 15px; margin-left: 10px;">\n'
        '                        TEST\n'
        '                    </button>\n'
    )
    if '<form id="formLogin"' in current:
        fallback_anchor = '<form id="formLogin" runat="server">'
        return {
            "action": "replace",
            "path": target.relative_to(root).as_posix(),
            "old_text": fallback_anchor,
            "new_text": fallback_anchor + insertion,
            "description": "Añadir el botón TEST al inicio del formulario si no hay un ancla de login clara."
        }

    raise ValueError("No fue posible ubicar un punto seguro para insertar el botón TEST en Login.aspx.")


def _natural_delete_button_operation(request: str, root: Path) -> Dict[str, Any]:
    """Genera una operación determinista para eliminar un botón TEST desde un prompt normal."""
    prompt = (request or "").strip()
    lower_prompt = prompt.lower()

    if "login.aspx" in lower_prompt:
        file_hint = "repositorios/rrhh/WebAsistencia/WebRH/Login.aspx"
    elif "login" in lower_prompt:
        file_hint = "Login.aspx"
    else:
        file_hint = "Login.aspx"

    target = _resolve_target(root, file_hint)
    try:
        current = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        current = target.read_text(encoding="latin-1")

    patterns = [
        r'<button\b[^>]*\bid\s*=\s*["\']TEST["\'][^>]*>.*?</button>',
        r'<button\b[^>]*>\s*TEST\s*</button>',
        r'<button\b[^>]*\bvalue\s*=\s*["\']TEST["\'][^>]*>.*?</button>',
    ]
    for pattern in patterns:
        match = re.search(pattern, current, flags=re.IGNORECASE | re.DOTALL)
        if match:
            old_text = match.group(0)
            return {
                "action": "delete",
                "path": target.relative_to(root).as_posix(),
                "old_text": old_text,
                "new_text": "",
                "description": "Eliminar el botón TEST identificado por id o texto visible."
            }

    raise ValueError("No se encontró el botón TEST en el archivo Login.aspx.")


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
    plan: Dict[str, Any] | None = None
    lower = request.lower()

    if "login" in lower and "test" in lower and re.search(r"(crea|agreg|insert|añad|pone|add|agrega)", lower):
        try:
            plan = {"summary": "Crear botón TEST", "operations": [_natural_create_button_operation(request, root)]}
        except Exception as fallback_exc:
            logger.exception("Fallback natural de creación para login/test falló")
            answer = f"No realicé cambios porque no pude obtener un plan de edición seguro: {fallback_exc}."
            return {
                "messages": [AIMessage(content=answer)],
                "agente_designado": "codeEditor",
                "motivo_designacion": "Se requiere crear o modificar archivos del proyecto.",
                "project_context": context,
                "project_files": [],
                "modifications": modifications,
            }
    else:
        try:
            response = build_chat_model().invoke([SystemMessage(content=prompt), *messages])
            plan = _decode_plan(response.content)
        except Exception as exc:
            logger.warning("No se pudo decodificar el plan JSON del modelo; intentando fallback natural: %s", exc)
            lower = request.lower()
            if re.search(r"(elimin|borr|quit|sac|remov|elimina|borra|quita|saca).*(test|boton|botón|button)", lower) or "test" in lower:
                if re.search(r"(crea|agreg|insert|añad|pone|add|agrega).*(test|boton|botón|button)", lower):
                    try:
                        plan = {"summary": "Crear botón TEST", "operations": [_natural_create_button_operation(request, root)]}
                    except Exception as fallback_exc:
                        logger.exception("Fallback natural de creación falló")
                        answer = f"No realicé cambios porque no pude obtener un plan de edición seguro: {fallback_exc}."
                        return {
                            "messages": [AIMessage(content=answer)],
                            "agente_designado": "codeEditor",
                            "motivo_designacion": "Se requiere crear o modificar archivos del proyecto.",
                            "project_context": context,
                            "project_files": [],
                            "modifications": modifications,
                        }
                else:
                    try:
                        plan = {"summary": "Eliminar botón TEST", "operations": [_natural_delete_button_operation(request, root)]}
                    except Exception as fallback_exc:
                        logger.exception("Fallback natural de edición falló")
                        answer = f"No realicé cambios porque no pude obtener un plan de edición seguro: {fallback_exc}."
                        return {
                            "messages": [AIMessage(content=answer)],
                            "agente_designado": "codeEditor",
                            "motivo_designacion": "Se requiere crear o modificar archivos del proyecto.",
                            "project_context": context,
                            "project_files": [],
                            "modifications": modifications,
                        }
            else:
                logger.exception("No se pudo aplicar la edición")
                answer = f"No realicé cambios porque no pude obtener un plan de edición seguro: {exc}."
                return {
                    "messages": [AIMessage(content=answer)],
                    "agente_designado": "codeEditor",
                    "motivo_designacion": "Se requiere crear o modificar archivos del proyecto.",
                    "project_context": context,
                    "project_files": [],
                    "modifications": modifications,
                }

    try:
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
        lower = request.lower()
        if "login" in lower and "test" in lower and ("crea" in lower or "agreg" in lower or "insert" in lower or "añad" in lower or "pone" in lower):
            try:
                fallback = _natural_create_button_operation(request, root)
                target, content, existed = _prepare_operation(root, fallback)
                _atomic_write(target, content)
                modifications.append({
                    "status": "modified" if existed else "created",
                    "path": target.relative_to(root).as_posix(),
                    "bytes": len(content.encode("utf-8")),
                })
                answer = f"Crear botón TEST\n\n- modified: `{target.relative_to(root).as_posix()}`"
            except Exception as fallback_exc:
                logger.exception("Fallback natural para TEST en login falló")
                answer = f"No realicé cambios porque no pude obtener un plan de edición seguro: {fallback_exc}."
        else:
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
