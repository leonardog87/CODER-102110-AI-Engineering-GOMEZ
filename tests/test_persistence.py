"""Prueba del historial persistente del agente único."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

test_db = Path(tempfile.gettempdir()) / "chatbot-history-test.sqlite3"
os.environ["CHATBOT_DB"] = str(test_db)

from data_access.database import close_connection  # noqa: E402
from data_access.query_history import load_query_history, save_query_record  # noqa: E402


def main() -> int:
    try:
        record_id = save_query_record(
            role="General",
            agent_name="chatBot",
            user_query="¿Cómo inicio sesión?",
            assistant_response="Respuesta documentada.",
            designation_reason="Agente único del proyecto.",
            tool_traces=[],
        )
        close_connection()
        rows = load_query_history("General")
        assert rows[-1]["id"] == record_id
        assert rows[-1]["agent_name"] == "chatBot"
        print("[OK] Historial único persistido y recuperado")
        return 0
    finally:
        close_connection()
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(f"{test_db}{suffix}")
            if candidate.exists():
                candidate.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
