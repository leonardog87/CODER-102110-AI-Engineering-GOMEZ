"""Política central de fuentes disponibles para chatBot."""

from __future__ import annotations

import os
from typing import Iterable, List, TypeVar

from dotenv import load_dotenv

load_dotenv()

T = TypeVar("T")


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "si", "sí"}


WEB_SEARCH_ENABLED = _env_flag("WEB_SEARCH_ENABLED", False)
WEB_SEARCH_PROVIDER = os.getenv("WEB_SEARCH_PROVIDER", "").strip()
WEB_SEARCH_API_KEY = os.getenv("WEB_SEARCH_API_KEY", "").strip()
WEB_SEARCH_ALLOWED_DOMAINS = tuple(
    domain.strip().lower().lstrip(".")
    for domain in os.getenv("WEB_SEARCH_ALLOWED_DOMAINS", "").split(",")
    if domain.strip()
)

WEB_TOOL_NAMES = frozenset(
    {"primary_retrieve_context", "web_search_allowed", "web_retrieve_allowed_url"}
)
DOCUMENT_RAG_TOOL_NAMES = frozenset(
    {"knowledge_retrieve_context"}
)

# Fuentes locales no parametrizadas disponibles para el único agente.
LOCAL_TOOL_NAMES = frozenset(
    {
        "knowledge_retrieve_context",
    }
)


def enabled_tools(tools: Iterable[T]) -> List[T]:
    """Impide exponer herramientas externas salvo habilitación explícita."""
    candidates = list(tools)
    allowed_names = set(LOCAL_TOOL_NAMES)
    if WEB_SEARCH_ENABLED:
        # La herramienta compuesta conserva internamente el fallback RAG, pero
        # evita que el modelo saltee por accidente la prioridad web.
        allowed_names.difference_update(DOCUMENT_RAG_TOOL_NAMES)
        allowed_names.update(WEB_TOOL_NAMES)
    return [
        tool
        for tool in candidates
        if str(getattr(tool, "name", "")) in allowed_names
    ]


LOCAL_ONLY_PROMPT = """

🔒 **POLÍTICA DE FUENTES:**
- La búsqueda web externa está desactivada.
- Usá únicamente `knowledge_base` mediante la herramienta RAG autorizada.
- Nunca consultes Internet, buscadores, sitios externos ni conocimiento recuperado fuera de esas fuentes.
- Si las fuentes locales no contienen la respuesta, indicá esa limitación con claridad; no completes la respuesta con información externa.
""".strip()


WEB_OPTIONAL_PROMPT = """

🌐 **POLÍTICA DE FUENTES:**
- Para consultas documentales, usá primero `primary_retrieve_context`: la Web es la fuente principal y RAG local es el respaldo automático si Tavily no está disponible, falla la conexión o no devuelve resultados.
- No uses primero las herramientas RAG documentales cuando la búsqueda web esté habilitada.
- `primary_retrieve_context` compara el resultado web con el contexto local y sincroniza en una fuente no parametrizada separada las versiones web nuevas o modificadas.
- `web_search_allowed` y `web_retrieve_allowed_url` quedan disponibles para consultas complementarias y están limitadas a los dominios autorizados.
- Usá exclusivamente los dominios incluidos en WEB_SEARCH_ALLOWED_DOMAINS. No intentes eludir esa restricción ni seguir enlaces hacia otros dominios.
- Indicá claramente si la respuesta provino de Web o del respaldo RAG local.
""".strip()


RETRIEVAL_POLICY_PROMPT = (
    WEB_OPTIONAL_PROMPT if WEB_SEARCH_ENABLED else LOCAL_ONLY_PROMPT
)
