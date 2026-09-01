"""Pruebas rápidas del contrato público de FastAPI."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from api import ChatRequest, _sources_from_traces, app, health


def main() -> None:
    schema = app.openapi()
    assert schema["info"]["version"] == "2.1.0"
    assert {"/health", "/api/chat", "/api/history"} <= set(schema["paths"])

    status = health()
    assert status.status == "ok"
    assert status.knowledge_source == "knowledge_base"

    request = ChatRequest(message="Hola")
    assert request.message == "Hola"
    assert request.conversation_history == []

    assert _sources_from_traces([]) == ["knowledge_base"]
    assert _sources_from_traces(
        [{"content": '{"source_type": "web_primary"}'}]
    ) == ["web"]
    assert _sources_from_traces(
        [{"tool_name": "web_search_allowed", "content": "{}"}]
    ) == ["web"]
    print("[OK] Contrato FastAPI, validaciones y fuentes verificados")


if __name__ == "__main__":
    main()
