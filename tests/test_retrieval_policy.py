"""Comprueba que la política predeterminada solo exponga fuentes locales."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent_system import retrieval_policy  # noqa: E402
from agent_system.web_tools import (  # noqa: E402
    primary_retrieve_context,
    web_retrieve_allowed_url,
    web_search_allowed,
)
from agent_system.chatbot_agent import CHATBOT_TOOLS  # noqa: E402
from agent_system.runtime import _text_tool_calls  # noqa: E402


def main() -> int:
    local_tool = SimpleNamespace(name="knowledge_retrieve_context")
    external_tool = SimpleNamespace(name="web_search")
    retrieval_policy.WEB_SEARCH_ENABLED = False
    selected = retrieval_policy.enabled_tools(
        [local_tool, external_tool]
    )

    assert [tool.name for tool in selected] == [
        "knowledge_retrieve_context",
    ]
    assert all(tool.name in retrieval_policy.LOCAL_TOOL_NAMES for tool in selected)
    assert not ({tool.name for tool in CHATBOT_TOOLS} & retrieval_policy.WEB_TOOL_NAMES)
    assert "knowledge_retrieve_context" in {tool.name for tool in CHATBOT_TOOLS}
    assert "verificar_respuesta_con_fuentes" not in {
        tool.name for tool in CHATBOT_TOOLS
    }
    parsed = _text_tool_calls(
        '<tool_call>{"name":"knowledge_retrieve_context",'
        '"arguments":{"query":"como me registro?","top_k":2}}</tool_call>'
    )
    assert parsed[0]["name"] == "knowledge_retrieve_context"

    assert "desactivada" in web_search_allowed.invoke({"query": "prueba"})
    assert "desactivada" in web_retrieve_allowed_url.invoke(
        {"url": "https://argentina.gob.ar/"}
    )

    retrieval_policy.WEB_SEARCH_ENABLED = True
    selected_when_enabled = retrieval_policy.enabled_tools(
        [
            local_tool,
            external_tool,
            primary_retrieve_context,
            web_search_allowed,
            web_retrieve_allowed_url,
        ]
    )
    assert [tool.name for tool in selected_when_enabled] == [
        "primary_retrieve_context",
        "web_search_allowed",
        "web_retrieve_allowed_url",
    ]
    retrieval_policy.WEB_SEARCH_ENABLED = False
    with patch("agent_system.web_tools._local_context", return_value="RAG local"):
        fallback = json.loads(
            primary_retrieve_context.invoke(
                {
                    "query": "¿Cómo recupero mi contraseña?",
                    "local_source": "knowledge",
                }
            )
        )
    assert fallback["source_type"] == "rag_fallback"
    assert "desactivada" in fallback["fallback_reason"]

    retrieval_policy.WEB_SEARCH_ENABLED = True
    with (
        patch("agent_system.web_tools._tavily_search") as search,
        patch("agent_system.web_tools._fetch_page") as fetch,
        patch("agent_system.web_tools._local_context", return_value="RAG local"),
        patch("agent_system.web_tools._sync_web_sources", return_value=True),
    ):
        search.return_value = {
            "results": [{"url": "https://argentina.gob.ar/novedad", "title": "Novedad"}]
        }
        fetch.return_value = {
            "url": "https://argentina.gob.ar/novedad",
            "content": "Información web vigente",
            "source_type": "web",
        }
        primary = json.loads(primary_retrieve_context.invoke({"query": "novedad"}))
        assert primary["source_type"] == "web_primary"
        assert primary["local_source_updated"] is True

    with (
        patch(
            "agent_system.web_tools._tavily_search",
            side_effect=RuntimeError("sin conexión"),
        ),
        patch("agent_system.web_tools._local_context", return_value="RAG local"),
    ):
        unavailable = json.loads(
            primary_retrieve_context.invoke({"query": "novedad"})
        )
        assert unavailable["source_type"] == "rag_fallback"
        assert unavailable["content"] == "RAG local"

    print("[OK] Búsqueda web desactivada y herramientas externas filtradas")
    print("[OK] Web primaria y fallback RAG verificados sin conexión real")
    retrieval_policy.WEB_SEARCH_ENABLED = False
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
