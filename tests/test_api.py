"""Pruebas rápidas del contrato público de FastAPI."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from api import ChatRequest, app, health


def main() -> None:
    schema = app.openapi()
    assert schema["info"]["version"] == "3.0.0"
    assert {"/health", "/api/chat", "/api/history"} <= set(schema["paths"])
    assert "delete" in schema["paths"]["/api/history"]

    status = health()
    assert status.status == "ok"
    assert status.knowledge_source == "repositorios"
    assert status.repository_available

    request = ChatRequest(message="Hola")
    assert request.message == "Hola"
    assert request.conversation_history == []

    print("[OK] Contrato FastAPI, validaciones y fuentes repositorio verificados")


if __name__ == "__main__":
    main()
