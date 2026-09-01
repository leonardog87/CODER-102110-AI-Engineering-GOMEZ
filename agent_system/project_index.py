from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List

from dotenv import load_dotenv

APP_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(APP_ROOT / ".env")
logger = logging.getLogger("chatBot.agent_system.project_index")

DEFAULT_SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    ".idea",
    ".vs",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    "bin",
    "obj",
    "debug",
    "release",
    "packages",
    "__MACOSX",
}
DEFAULT_SKIP_DIRS_LOWER = {name.lower() for name in DEFAULT_SKIP_DIRS}

DEFAULT_TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".env",
    ".js",
    ".ts",
    ".tsx",
    ".cs",
    ".vb",
    ".aspx",
    ".ascx",
    ".asmx",
    ".cshtml",
    ".csproj",
    ".vbproj",
    ".sln",
    ".config",
    ".css",
    ".scss",
    ".html",
    ".htm",
    ".xml",
    ".sql",
    ".ps1",
    ".bat",
}


def _project_root(root: str | Path | None = None) -> Path:
    if root is not None:
        candidate = Path(root).expanduser().resolve()
        if candidate.exists():
            return candidate

    for key in (
        "AGENT_PROJECT_ROOT",
        "PROJECT_ROOT",
        "REPOSITORIES_ROOT",
        "WORKSPACE_REPOSITORIES_ROOT",
    ):
        value = os.getenv(key)
        if value:
            candidate = _configured_path(value)
            if candidate.exists():
                return candidate

    default_root = (APP_ROOT / "repositorios").resolve()
    if default_root.exists():
        return default_root
    return APP_ROOT


def _configured_path(value: str) -> Path:
    path = Path(value).expanduser()
    return (APP_ROOT / path).resolve() if not path.is_absolute() else path.resolve()


def _iter_project_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part.lower() in DEFAULT_SKIP_DIRS_LOWER for part in path.parts):
            continue
        if path.suffix.lower() not in DEFAULT_TEXT_SUFFIXES:
            continue
        yield path


def _chunk_text(text: str, chunk_size: int, overlap: int) -> List[str]:
    if not text.strip():
        return []
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start += chunk_size - overlap
    return chunks


def _score_chunk(question: str, question_tokens: set[str], text: str) -> float:
    lowered = text.lower()
    tokens = set(re.sub(r"[^\w\s]", " ", lowered).split())
    overlap = len(question_tokens & tokens)
    phrase_bonus = 1 if question_tokens and question_tokens.issubset(tokens) else 0
    return overlap * 2 + phrase_bonus + (1 if question.lower() in lowered else 0)


def _path_score(question: str, path: str) -> float:
    words = [word for word in re.findall(r"\w+", question.lower()) if len(word) >= 3]
    normalized_path = re.sub(r"[^a-z0-9áéíóúñ]", "", path.lower())
    score = sum(2 for word in words if word in normalized_path)
    for width in range(min(4, len(words)), 1, -1):
        if any("".join(words[start : start + width]) in normalized_path for start in range(len(words) - width + 1)):
            score += width * 5
            break
    return score


QUERY_ALIASES = {
    "email": {"mail", "correo"},
    "e-mail": {"mail", "correo"},
    "correo": {"mail", "email"},
    "cambio": {"cambiar", "modificar", "actualizar"},
    "cambiar": {"cambio", "modificar", "actualizar"},
    "modificar": {"cambio", "cambiar", "actualizar"},
    "guardar": {"grabar", "actualizar", "persistir"},
    "borrar": {"eliminar", "quitar"},
    "eliminar": {"borrar", "quitar"},
}


def _expanded_question_tokens(question: str) -> set[str]:
    normalized = re.sub(r"[^\w\s-]", " ", question.lower())
    tokens = {token for token in normalized.split() if token}
    expanded = set(tokens)
    for token in tokens:
        expanded.update(QUERY_ALIASES.get(token, set()))
    return expanded


def _live_query(question: str, root: Path, k: int) -> str:
    """Respaldo de memoria acotada para repositorios e índices grandes."""
    question_tokens = _expanded_question_tokens(question)
    best: List[tuple[float, str, str]] = []
    chunk_size = max(100, int(os.getenv("PROJECT_INDEX_CHUNK_SIZE", "1200")))
    overlap = max(0, int(os.getenv("PROJECT_INDEX_CHUNK_OVERLAP", "180")))
    stopwords = {"como", "cómo", "cual", "cuál", "donde", "dónde", "para", "por", "que", "qué", "del", "los", "las", "una", "uno", "este", "esta", "proceso", "explica", "explicá"}
    search_terms = sorted(
        (
            token for token in question_tokens
            if len(token) >= 3 and token not in stopwords and not token.startswith("explic")
        ),
        key=len,
        reverse=True,
    )[:12]
    candidates: Iterable[Path] = _iter_project_files(root)
    if search_terms:
        try:
            command = ["rg", "-l", "-i", "-m", "1", "--no-messages", "--glob", "!**/{.git,.vs,bin,obj,node_modules}/**"]
            for suffix in sorted(DEFAULT_TEXT_SUFFIXES):
                command.extend(["--glob", f"*{suffix}"])
            command.extend(["|".join(re.escape(term) for term in search_terms), str(root)])
            completed = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
            matched = [Path(line) for line in completed.stdout.splitlines() if line.strip()]
            if matched:
                candidates = matched
        except (OSError, subprocess.SubprocessError):
            logger.warning("ripgrep no disponible; se recorre el repositorio para la búsqueda textual")
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                text = path.read_text(encoding="latin-1")
            except Exception:
                continue
        except Exception:
            continue
        rel_path = path.relative_to(root).as_posix()
        for chunk in _chunk_text(text, chunk_size, overlap):
            score = _score_chunk(question, question_tokens, chunk) + _path_score(question, rel_path)
            if score <= 0:
                continue
            best.append((score, rel_path, chunk))
            best.sort(key=lambda item: item[0], reverse=True)
            del best[k * 4:]
    selected: List[tuple[float, str, str]] = []
    path_counts: Dict[str, int] = {}
    for item in best:
        path = item[1]
        if path_counts.get(path, 0) >= 2:
            continue
        selected.append(item)
        path_counts[path] = path_counts.get(path, 0) + 1
        if len(selected) >= k:
            break
    return "\n\n".join(
        f"Archivo: {path}\n{text[:1200]}\n" for _, path, text in selected
    )


def query_project_index(
    question: str,
    root: str | Path | None = None,
    k: int | None = None,
) -> str:
    """Busca directamente en el repositorio sin índices persistidos."""
    repo_root = _project_root(root)
    k = k or max(1, int(os.getenv("PROJECT_INDEX_TOP_K", "5")))
    return _live_query(question, repo_root, k=k)


def expand_related_context(
    question: str,
    initial_context: str,
    root: str | Path | None = None,
    max_symbols: int = 6,
    max_chars: int = 14000,
) -> str:
    """Sigue referencias de código recuperadas hacia sus implementaciones y usos."""
    repo_root = _project_root(root)
    # Los miembros calificados (Backend.Metodo) son las mejores pistas para
    # atravesar frontend -> endpoint -> servicio. Luego se consideran nombres
    # CamelCase largos relacionados con las palabras de la pregunta.
    qualified = re.findall(r"\b[A-Za-z_$][\w$]*\.([A-Za-z_$][\w$]{4,})\b", initial_context)
    camel = re.findall(r"\b[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚáéíóúÑñ0-9_]{6,}\b", initial_context)
    question_terms = {token for token in _expanded_question_tokens(question) if len(token) >= 4}
    candidates: List[tuple[int, int, str]] = []
    seen: set[str] = set()
    for symbol in [*qualified, *camel]:
        lowered = symbol.lower()
        if symbol in seen or lowered in {"archivo", "backend", "javascript", "function", "usuario"}:
            continue
        seen.add(symbol)
        relevance = sum(1 for term in question_terms if term in lowered or lowered in term)
        qualified_bonus = 2 if symbol in qualified else 0
        candidates.append((relevance, qualified_bonus, symbol))
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    ranked = [symbol for relevance, bonus, symbol in candidates if relevance or bonus][:max_symbols]
    if not ranked:
        return ""

    sections: List[str] = []
    remaining = max_chars
    for symbol in ranked:
        command = [
            "rg", "-n", "-C", "10", "-m", "3", "--no-messages",
            "--glob", "!**/{.git,.vs,bin,obj,node_modules}/**",
        ]
        for suffix in (".cs", ".js", ".ts", ".aspx", ".ascx", ".asmx", ".config", ".sql"):
            command.extend(["--glob", f"*{suffix}"])
        command.extend(["-F", symbol, str(repo_root)])
        try:
            completed = subprocess.run(
                command, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=12, check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        output = completed.stdout.strip()
        if not output:
            continue
        excerpt = output[:remaining]
        sections.append(f"Referencias relacionadas con {symbol}:\n{excerpt}")
        remaining -= len(excerpt)
        if remaining <= 0:
            break
    return "\n\n".join(sections)


def expand_structural_context(
    initial_context: str,
    root: str | Path | None = None,
    max_files: int = 10,
    max_chars: int = 14000,
) -> str:
    """Sigue enlaces de UI y agrega sus code-behind/JavaScript compañeros."""
    repo_root = _project_root(root)
    source_paths = re.findall(r"^Archivo:\s+(.+?)\s*$", initial_context, re.MULTILINE)
    references = re.findall(
        r"(?:href|src)\s*=\s*['\"]([^'\"?#]+\.(?:aspx|ascx|htm|html|js))",
        initial_context,
        re.IGNORECASE,
    )
    candidates: List[Path] = []
    source_dirs: List[Path] = []
    for raw_source in source_paths[:8]:
        source = (repo_root / raw_source.strip().replace("/", os.sep)).resolve()
        if source.is_file() and source.parent not in source_dirs:
            source_dirs.append(source.parent)
    for directory in source_dirs:
        for reference in references:
            raw_name = Path(reference.replace("\\", "/")).name
            direct = directory / raw_name
            matches = [direct] if direct.is_file() else [
                path for path in directory.iterdir()
                if path.is_file() and path.name.lower() == raw_name.lower()
            ]
            for match in matches:
                companions = [
                    match,
                    Path(f"{match}.cs"),
                    match.with_suffix(".js"),
                ]
                for companion in companions:
                    if companion.is_file() and companion not in candidates:
                        candidates.append(companion)
    if not candidates:
        return ""

    sections: List[str] = []
    inventory_dirs = sorted({path.parent for path in candidates})
    for directory in inventory_dirs[:3]:
        names = [
            path.name for path in sorted(directory.iterdir())
            if path.is_file() and path.suffix.lower() in DEFAULT_TEXT_SUFFIXES
        ]
        sections.append(
            f"Inventario del módulo {directory.relative_to(repo_root).as_posix()}:\n"
            + ", ".join(names[:80])
        )
    remaining = max_chars - sum(len(section) for section in sections)
    for path in candidates[:max_files]:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                text = path.read_text(encoding="latin-1")
            except Exception:
                continue
        except Exception:
            continue
        excerpt_size = min(2200, remaining)
        if excerpt_size <= 0:
            break
        sections.append(
            f"Archivo vinculado: {path.relative_to(repo_root).as_posix()}\n{text[:excerpt_size]}"
        )
        remaining -= excerpt_size
    return "\n\n".join(sections)


__all__ = [
    "query_project_index", "expand_related_context",
    "expand_structural_context", "_project_root",
]
