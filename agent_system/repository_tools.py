"""Herramientas acotadas para comprender código y editar interfaces con evidencia real."""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List

from langchain_core.tools import tool

from agent_system.project_index import DEFAULT_TEXT_SUFFIXES, _iter_project_files, _project_root


def _safe_file(path: str) -> Path:
    root = _project_root().resolve()
    raw = Path(str(path).replace("\\", "/"))
    if raw.is_absolute():
        candidate = raw.resolve()
    else:
        candidate = (root / raw).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("La ruta está fuera del repositorio.") from exc
    if not candidate.is_file() or candidate.suffix.lower() not in DEFAULT_TEXT_SUFFIXES:
        raise ValueError(f"Archivo de texto inexistente o no permitido: {path}")
    return candidate


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def _numbered_excerpt(text: str, start: int, end: int) -> str:
    lines = text.splitlines()
    start = max(1, start)
    end = min(len(lines), max(start, end))
    return "\n".join(f"{index:>6}: {lines[index - 1]}" for index in range(start, end + 1))


@tool
def list_project_files(pattern: str = "", limit: int = 100) -> Dict[str, Any]:
    """Lista archivos reales del proyecto. pattern filtra por nombre o ruta, por ejemplo Login.aspx o Formularios."""
    root = _project_root()
    needle = pattern.lower().replace("\\", "/").strip()
    matches = [p.relative_to(root).as_posix() for p in _iter_project_files(root)
               if not needle or needle in p.relative_to(root).as_posix().lower()]
    return {"files": matches[:max(1, min(limit, 300))], "total_matches": len(matches)}


@tool
def read_project_file(path: str, start_line: int = 1, end_line: int = 240) -> Dict[str, Any]:
    """Lee un rango exacto de un archivo con números de línea. Úsala antes de explicar o editar."""
    target = _safe_file(path)
    root = _project_root()
    text = _read(target)
    total = len(text.splitlines())
    start, end = max(1, start_line), min(total, max(start_line, end_line, 1))
    return {"path": target.relative_to(root).as_posix(), "start_line": start,
            "end_line": end, "total_lines": total, "content": _numbered_excerpt(text, start, end)}


@tool
def search_code(query: str, path_filter: str = "", limit: int = 40) -> Dict[str, Any]:
    """Busca texto o una expresión regular y devuelve coincidencias con archivo, línea y contexto."""
    if not query.strip():
        raise ValueError("query no puede estar vacío")
    root = _project_root()
    try:
        regex = re.compile(query, re.IGNORECASE)
    except re.error:
        regex = re.compile(re.escape(query), re.IGNORECASE)
    results: List[Dict[str, Any]] = []
    needle = path_filter.lower().replace("\\", "/").strip()
    for file in _iter_project_files(root):
        relative = file.relative_to(root).as_posix()
        if needle and needle not in relative.lower():
            continue
        try:
            lines = _read(file).splitlines()
        except Exception:
            continue
        for index, line in enumerate(lines, 1):
            if regex.search(line):
                results.append({"path": relative, "line": index, "text": line.strip()[:500]})
                if len(results) >= max(1, min(limit, 200)):
                    return {"matches": results, "truncated": True}
    return {"matches": results, "truncated": False}


@tool
def inspect_symbol(symbol: str, limit: int = 60) -> Dict[str, Any]:
    """Localiza definiciones, llamadas y referencias de una función, método, clase, control o endpoint."""
    if not re.fullmatch(r"[A-Za-z_$][\w$.:/-]{1,150}", symbol.strip()):
        raise ValueError("Símbolo inválido")
    result = search_code.invoke({"query": rf"\b{re.escape(symbol.strip())}\b", "limit": limit})
    matches = result["matches"]
    definition_words = re.compile(r"\b(class|def|function|sub|interface|enum|void|public|private|protected|static)\b", re.I)
    for match in matches:
        match["kind"] = "definition_or_declaration" if definition_words.search(match["text"]) else "reference_or_call"
    return {"symbol": symbol, "occurrences": matches, "truncated": result["truncated"]}


class _DOMInventory(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: List[str] = []
        self.elements: List[Dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs: List[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        selector = tag
        if values.get("id"):
            selector += f"#{values['id']}"
        elif values.get("class"):
            selector += "." + ".".join(values["class"].split()[:3])
        self.elements.append({"tag": tag, "selector": selector, "line": self.getpos()[0],
                              "parent": self.stack[-1] if self.stack else None,
                              "id": values.get("id"), "class": values.get("class"),
                              "name": values.get("name"), "runat": values.get("runat")})
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(selector)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index].split("#", 1)[0].split(".", 1)[0] == tag:
                del self.stack[index:]
                break


@tool
def inspect_dom(path: str, selector_or_text: str = "") -> Dict[str, Any]:
    """Construye un inventario del DOM/ASPX con selectores, padres y líneas para ubicar una edición precisa."""
    target = _safe_file(path)
    text = _read(target)
    parser = _DOMInventory()
    parser.feed(re.sub(r"<%@.*?%>|<%.*?%>", "", text, flags=re.DOTALL))
    needle = selector_or_text.lower().strip()
    elements = parser.elements
    if needle:
        elements = [item for item in elements if needle in " ".join(str(v or "") for v in item.values()).lower()]
    root = _project_root()
    return {"path": target.relative_to(root).as_posix(), "elements": elements[:300],
            "total_elements": len(parser.elements), "matching_elements": len(elements)}


@tool
def inspect_file_relationships(path: str) -> Dict[str, Any]:
    """Descubre code-behind, scripts, estilos, includes, master pages y referencias locales de un archivo."""
    target = _safe_file(path)
    root = _project_root()
    text = _read(target)
    refs = re.findall(r"(?:src|href|CodeFile|CodeBehind|MasterPageFile)\s*=\s*['\"]([^'\"?#]+)", text, re.I)
    candidates = [Path(f"{target}.cs"), target.with_suffix(".js"), target.with_suffix(".css")]
    for ref in refs:
        cleaned = ref.replace("~/", "").replace("\\", "/")
        candidates.extend([(target.parent / cleaned), (root / cleaned)])
    related: List[str] = []
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            resolved.relative_to(root.resolve())
        except ValueError:
            continue
        if resolved.is_file():
            relative = resolved.relative_to(root).as_posix()
            if relative not in related:
                related.append(relative)
    return {"path": target.relative_to(root).as_posix(), "related_files": related, "references": refs}


REPOSITORY_TOOLS = [list_project_files, read_project_file, search_code, inspect_symbol, inspect_dom, inspect_file_relationships]

__all__ = ["REPOSITORY_TOOLS", "list_project_files", "read_project_file", "search_code",
           "inspect_symbol", "inspect_dom", "inspect_file_relationships"]
