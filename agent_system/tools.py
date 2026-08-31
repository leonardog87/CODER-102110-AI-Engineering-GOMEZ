"""Herramientas documentales disponibles para el agente único chatBot."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from rag.knowledge_pipeline import retrieve_knowledge_context


def safe_json(data: Any) -> str:
    """Serializa resultados de herramientas sin perder caracteres en español."""
    try:
        return json.dumps(data, ensure_ascii=False, default=str)
    except Exception:
        return json.dumps(
            {"error": "No se pudo serializar el resultado."},
            ensure_ascii=False,
        )


@tool("knowledge_retrieve_context")
def knowledge_retrieve_context(query: str, top_k: int = 3) -> str:
    """Recupera información general y guías desde knowledge_base."""
    return retrieve_knowledge_context(query=query, top_k=top_k)
