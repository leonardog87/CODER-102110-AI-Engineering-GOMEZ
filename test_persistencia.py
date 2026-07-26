"""Prueba persistencia documental, chats por rol y controles salariales."""

from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4


WORKSPACE = Path(__file__).resolve().parent
TEST_DB = WORKSPACE / "data" / f"test_persistencia_{uuid4().hex}.sqlite3"

# Debe configurarse antes de importar mcp.config/mcp.database.
os.environ["AGENTE_CORPORATIVO_DB"] = str(TEST_DB)
os.environ["EMPLEADOS_CSV"] = str(WORKSPACE / "raw_data" / "empleados.csv")
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"

from mcp.database import close_connection  # noqa: E402
from mcp.query_history import load_query_history, save_query_record  # noqa: E402
from mcp.server import mcp_execute_query  # noqa: E402


def assert_chroma_persistence() -> None:
    """Comprueba que ambas colecciones Chroma existen y tienen fragmentos."""
    import chromadb

    expected = (
        ("manuales_simples_chroma_db", "manuales_simples"),
        ("manuales_complejos_chroma_db", "manuales_complejos"),
    )
    for directory, collection_name in expected:
        path = WORKSPACE / directory
        assert path.is_dir(), f"No existe el directorio Chroma: {path}"
        client = chromadb.PersistentClient(path=str(path))
        collection = client.get_collection(collection_name)
        assert collection.count() > 0, f"La colección {collection_name} está vacía"


def assert_role_chat_persistence() -> None:
    """Guarda, reinicia y recupera chats sin mezclarlos entre roles."""
    employee_result = mcp_execute_query(
        "empleados",
        {"Area": "Infraestructura"},
        "Empleado",
    )
    administrator_result = mcp_execute_query(
        "empleados",
        {"Area": "Infraestructura"},
        "Administrador",
    )

    employee_payload = json.dumps(employee_result, ensure_ascii=False)
    administrator_payload = json.dumps(administrator_result, ensure_ascii=False)
    assert "Sueldo_ARS" not in employee_payload
    assert "promedio_sueldo" not in employee_payload
    assert "Sueldo_ARS" in administrator_payload
    assert "promedio_sueldo" in administrator_payload

    expected_queries = {
        "Invitado": "¿Cómo recupero mi contraseña?",
        "Empleado": "Lista de empleados de Infraestructura",
        "Administrador": "Lista de empleados con salarios",
    }
    expected_responses = {
        "Invitado": "Consulta al manual simple.",
        "Empleado": employee_payload,
        "Administrador": administrator_payload,
    }

    for role in expected_queries:
        save_query_record(
            role=role,
            agent_name=f"agente_{role.lower()}",
            user_query=expected_queries[role],
            assistant_response=expected_responses[role],
            designation_reason="Prueba automatizada",
            tool_traces=[],
        )

    # Simula el cierre/reinicio del proceso antes de volver a consultar.
    close_connection()

    histories = {
        role: load_query_history(role)
        for role in ("Invitado", "Empleado", "Administrador")
    }
    for role, rows in histories.items():
        assert len(rows) == 1, f"Historial inesperado para {role}: {rows}"
        assert rows[0]["role"] == role
        assert rows[0]["user_query"] == expected_queries[role]
        assert rows[0]["assistant_response"] == expected_responses[role]

    assert "Sueldo_ARS" not in json.dumps(histories["Empleado"], ensure_ascii=False)
    assert "Sueldo_ARS" in json.dumps(
        histories["Administrador"],
        ensure_ascii=False,
    )

    try:
        load_query_history("RolNoAutorizado")
    except ValueError:
        pass
    else:
        raise AssertionError("Un rol no autorizado pudo consultar el historial")


def cleanup_test_database() -> None:
    close_connection()
    for suffix in ("", "-wal", "-shm"):
        path = Path(f"{TEST_DB}{suffix}")
        if path.exists():
            path.unlink()


def main() -> int:
    print("=" * 68)
    print("PRUEBA DE PERSISTENCIA POR ROL")
    print("=" * 68)
    try:
        assert_chroma_persistence()
        print("[OK] Persistencia de manuales simples y complejos")

        assert_role_chat_persistence()
        print("[OK] Chats recuperados después de reiniciar la conexión")
        print("[OK] Historial aislado para Invitado, Empleado y Administrador")
        print("[OK] Empleado sin salarios; Administrador con acceso completo")
        print("[OK] Roles desconocidos rechazados")
        return 0
    finally:
        cleanup_test_database()


if __name__ == "__main__":
    raise SystemExit(main())
