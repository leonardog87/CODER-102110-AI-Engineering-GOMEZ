"""Pruebas mínimas del contrato HTTP sin invocar proveedores externos."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from api import app


def main() -> int:
    with TestClient(app) as client:
        live = client.get("/health/live")
        assert live.status_code == 200
        assert live.json() == {"status": "ok"}

        invalid_limit = client.get("/api/history/Invitado", params={"limit": 0})
        assert invalid_limit.status_code == 422

        openapi = client.get("/openapi.json")
        assert openapi.status_code == 200
        paths = openapi.json()["paths"]
        assert "/api/chat" in paths
        assert "/api/history/{role}" in paths
        assert "/health/live" in paths
        assert "/health/ready" in paths

    print("[OK] Contrato y salud de FastAPI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
