"""Prueba persistencia documental, chats por rol y controles de acceso."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
TEST_DB = PROJECT_ROOT / "data" / f"test_persistence_{uuid4().hex}.sqlite3"

# Debe configurarse antes de importar data_access.config/database.
os.environ["AGENTE_CORPORATIVO_DB"] = str(TEST_DB)
os.environ["EMPLEADOS_CSV"] = str(PROJECT_ROOT / "raw_data" / "empleados.csv")
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"

from data_access.database import close_connection  # noqa: E402
from data_access.query_history import load_query_history, save_query_record  # noqa: E402
from data_access.service import (  # noqa: E402
    mcp_count_employees,
    mcp_employee_distribution,
    mcp_execute_query,
)
from agent_system.runtime import (  # noqa: E402
    _direct_tool_call_for_structured_query,
    _format_tool_result_for_user,
    _format_policy_infrastructure_result,
    _format_database_policy_result,
)
from agent_system.tools import (  # noqa: E402
    consultar_empleados_mcp_empleado,
    contar_empleados_mcp_empleado,
    distribucion_empleados_mcp_empleado,
    rag_retrieve_context,
    verificar_respuesta_con_fuentes,
)
from langchain_core.messages import HumanMessage, ToolMessage  # noqa: E402


def assert_chroma_persistence() -> None:
    """Comprueba que ambas colecciones Chroma existen y tienen fragmentos."""
    import chromadb

    expected = (
        ("manuales_simples_chroma_db", "manuales_simples"),
        ("manuales_complejos_chroma_db", "manuales_complejos"),
    )
    for directory, collection_name in expected:
        path = PROJECT_ROOT / directory
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
    employee_payload = json.dumps(employee_result, ensure_ascii=False)
    assert "Sueldo_ARS" not in employee_payload
    assert "promedio_sueldo" not in employee_payload

    developer_result = mcp_execute_query(
        "empleados",
        {"Puesto": "desarrolladores"},
        "Empleado",
    )
    assert developer_result["data"]["total"] == 4, developer_result

    developer_area_result = mcp_execute_query("empleados", {"Area": "desarrolladores"}, "Empleado")
    assert developer_area_result["data"]["total"] == 4, developer_area_result

    assert mcp_count_employees(
        {"Puesto": "desarrolladores"},
        "Empleado",
    )["data"]["total"] == 4
    distribution = mcp_employee_distribution("area", {}, "Empleado")
    assert distribution["data"]["total"] == 20
    assert all("Sueldo_ARS" not in group for group in distribution["data"]["groups"])
    direct_call = _direct_tool_call_for_structured_query(
        [HumanMessage(content="dime cuantos empleados son desarrolladores")],
        [consultar_empleados_mcp_empleado],
    )
    assert direct_call is not None
    assert direct_call["args"] == {"puesto": "Developer"}

    direct_count_call = _direct_tool_call_for_structured_query(
        [HumanMessage(content="dime cuantos empleados son desarrolladores")],
        [contar_empleados_mcp_empleado],
    )
    assert direct_count_call["name"] == "contar_empleados_mcp_empleado"
    assert direct_count_call["args"] == {"puesto": "Developer"}

    direct_distribution_call = _direct_tool_call_for_structured_query(
        [HumanMessage(content="distribución porcentual por área")],
        [distribucion_empleados_mcp_empleado],
    )
    assert direct_distribution_call["args"] == {"group_by": "area"}

    formatted = _format_tool_result_for_user(
        [
            ToolMessage(
                content=json.dumps(developer_result, ensure_ascii=False),
                tool_call_id="direct_empleados_query",
            )
        ],
        user_text="dime cuantos empleados son desarrolladores",
    )
    assert formatted == "Hay **4 empleados desarrolladores**."

    composite_calls = _direct_tool_call_for_structured_query(
        [
            HumanMessage(
                content=(
                    "Combiná la política de acceso a bases de datos con la "
                    "información del área de Infraestructura"
                )
            )
        ],
        [rag_retrieve_context, consultar_empleados_mcp_empleado],
    )
    assert isinstance(composite_calls, list)
    assert [call["id"] for call in composite_calls] == [
        "direct_rag_policy",
        "direct_infra_employees",
    ]

    infrastructure_result = mcp_execute_query(
        "empleados",
        {"Area": "Infraestructura"},
        "Empleado",
    )
    composite_response = _format_policy_infrastructure_result(
        [
            ToolMessage(
                content="- Toda consulta debe limitarse al mínimo necesario.",
                tool_call_id="direct_rag_policy",
            ),
            ToolMessage(
                content=json.dumps(infrastructure_result, ensure_ascii=False),
                tool_call_id="direct_infra_employees",
            ),
        ]
    )
    assert "Infraestructura hay 3 empleados" in composite_response
    assert "mínimo necesario" in composite_response
    assert "normativa_acceso_bases_datos.md" in composite_response

    policy_calls = _direct_tool_call_for_structured_query(
        [
            HumanMessage(
                content=(
                    "¿Qué indica la normativa sobre el acceso seguro a "
                    "bases de datos?"
                )
            )
        ],
        [rag_retrieve_context],
    )
    assert isinstance(policy_calls, dict)
    assert policy_calls["id"] == "direct_rag_policy"

    policy_response = _format_database_policy_result(
        [
            ToolMessage(
                content=(
                    "# Contexto recuperado\n"
                    "Fuente: normativa_acceso_bases_datos\n"
                    "- El acceso requiere autorización explícita.\n"
                    "- Toda consulta debe limitarse al mínimo necesario."
                ),
                tool_call_id="direct_rag_policy",
            )
        ]
    )
    assert "autorización explícita" in policy_response
    assert "mínimo necesario" in policy_response

    evidence = json.loads(
        verificar_respuesta_con_fuentes.invoke(
            {
                "respuesta": "El acceso requiere autorización explícita.",
                "contexto": "La política exige autorización explícita para el acceso.",
            }
        )
    )
    assert evidence["supported"] is True

    expected_queries = {
        "Invitado": "¿Cómo recupero mi contraseña?",
        "Empleado": "Lista de empleados de Infraestructura",
    }
    expected_responses = {
        "Invitado": "Consulta al manual simple.",
        "Empleado": employee_payload,
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
        for role in ("Invitado", "Empleado")
    }
    for role, rows in histories.items():
        assert len(rows) == 1, f"Historial inesperado para {role}: {rows}"
        assert rows[0]["role"] == role
        assert rows[0]["user_query"] == expected_queries[role]
        assert rows[0]["assistant_response"] == expected_responses[role]

    assert "Sueldo_ARS" not in json.dumps(histories["Empleado"], ensure_ascii=False)
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
        print("[OK] Historial aislado para Invitado y Empleado")
        print("[OK] Empleado sin salarios")
        print("[OK] Roles desconocidos rechazados")
        return 0
    finally:
        cleanup_test_database()


if __name__ == "__main__":
    raise SystemExit(main())
