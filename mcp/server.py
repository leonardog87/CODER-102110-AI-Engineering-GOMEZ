"""Fachada pública del servidor MCP del Agente Corporativo IA.

La API publica se mantiene estable:
    mcp_execute_query(tabla, filtros, agente_rol)
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict

from mcp.config import (
    ALLOWED_TABLES,
    EMPLEADOS_CSV_PATH,
    SQLITE_DB_PATH,
    logger,
)
from mcp.database import get_connection, migrate_empleados_to_sqlite
from mcp.queries import get_aggregated_data, list_tables, preview_table
from mcp.security import response, sanitize_employee_output

__all__ = [
    "ALLOWED_TABLES",
    "EMPLEADOS_CSV_PATH",
    "SQLITE_DB_PATH",
    "get_connection",
    "list_tables",
    "mcp_execute_query",
    "migrate_empleados_to_sqlite",
    "preview_table",
]


def _run_role_query(
    *,
    tabla: str,
    filtros: Dict[str, Any],
    include_stats: bool,
    hide_salaries: bool,
) -> Dict[str, Any]:
    conn = get_connection()
    aggregated = get_aggregated_data(
        conn,
        tabla,
        filtros,
        include_stats=include_stats,
    )

    if hide_salaries:
        aggregated["sample"] = sanitize_employee_output(aggregated.get("sample", []))
        aggregated["stats"] = {}

    return response(
        status_code=200,
        status="ok",
        message=f"Consulta exitosa. {aggregated['message']}",
        data=aggregated,
    )


def mcp_execute_query(tabla: str, filtros: dict, agente_rol: str) -> dict:
    """Ejecuta una consulta segura con RBAC.

    Args:
        tabla: "empleados".
        filtros: Diccionario con filtros para la consulta.
        agente_rol: "Empleado" o "Administrador".
    """
    try:
        logger.info("[MCP] tabla=%s, filtros=%s, rol=%s", tabla, filtros, agente_rol)

        if tabla not in ALLOWED_TABLES:
            return response(
                status_code=400,
                status="bad_request",
                message=f"Tabla invalida. Solo se permiten {', '.join(ALLOWED_TABLES)}.",
                data=[],
            )

        filtros = filtros or {}
        role = str(agente_rol).strip()

        if role == "Empleado":
            if any(key.lower() == "sueldo_ars" for key in filtros):
                return response(
                    status_code=403,
                    status="forbidden",
                    message="Acceso denegado: el rol Empleado no puede consultar salarios.",
                    data=[],
                )
            return _run_role_query(
                tabla=tabla,
                filtros=filtros,
                include_stats=False,
                hide_salaries=True,
            )

        if role == "Administrador":
            return _run_role_query(
                tabla=tabla,
                filtros=filtros,
                include_stats=True,
                hide_salaries=False,
            )

        return response(
            status_code=403,
            status="forbidden",
            message="Rol no autorizado o no reconocido.",
            data=[],
        )
    except sqlite3.Error as exc:
        logger.exception("[MCP] Error interno de SQLite")
        return response(
            status_code=500,
            status="error",
            message=f"Error en la base de datos: {str(exc)}",
            data=[],
        )
    except ValueError as exc:
        logger.warning("[MCP] Consulta inválida: %s", exc)
        return response(
            status_code=400,
            status="bad_request",
            message=str(exc),
            data=[],
        )
    except Exception as exc:
        logger.exception("[MCP] Error inesperado")
        return response(
            status_code=500,
            status="error",
            message=f"Error inesperado: {str(exc)}",
            data=[],
        )


if __name__ == "__main__":
    demo_empleado = mcp_execute_query(
        tabla="empleados",
        filtros={"Area": "Infraestructura"},
        agente_rol="Empleado",
    )
    print("\n=== Empleado (sin salarios) ===")
    print(json.dumps(demo_empleado, ensure_ascii=False, indent=2))

    demo_administrador = mcp_execute_query(
        tabla="empleados",
        filtros={"Area": "Infraestructura"},
        agente_rol="Administrador",
    )
    print("\n=== Administrador (acceso completo) ===")
    print(json.dumps(demo_administrador, ensure_ascii=False, indent=2))
