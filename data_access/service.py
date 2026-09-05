"""Servicio interno de consultas seguras del Agente Corporativo IA.

La API publica se mantiene estable:
    mcp_execute_query(tabla, filtros, agente_rol)
"""

from __future__ import annotations

import sqlite3
import unicodedata
from typing import Any, Dict

from data_access.config import (
    ALLOWED_TABLES,
    EMPLEADOS_CSV_PATH,
    SQLITE_DB_PATH,
    logger,
)
from data_access.database import get_connection, migrate_empleados_to_sqlite
from data_access.queries import (
    get_aggregated_data,
    get_employee_count,
    get_employee_distribution,
    get_salary_statistics,
    list_tables,
    preview_table,
)
from data_access.security import response, sanitize_employee_output

__all__ = [
    "ALLOWED_TABLES",
    "EMPLEADOS_CSV_PATH",
    "SQLITE_DB_PATH",
    "get_connection",
    "list_tables",
    "mcp_execute_query",
    "migrate_empleados_to_sqlite",
    "mcp_count_employees",
    "mcp_employee_distribution",
    "preview_table",
]


def _run_role_query(
    *,
    tabla: str,
    filtros: Dict[str, Any],
    include_stats: bool,
    hide_salaries: bool,
    limit: int,
) -> Dict[str, Any]:
    conn = get_connection()
    aggregated = get_aggregated_data(
        conn,
        tabla,
        filtros,
        include_stats=include_stats,
        sample_limit=limit,
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


def _normalize_filter_term(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value).strip().lower())
    return "".join(char for char in text if not unicodedata.combining(char))


def _normalize_employee_filters(filtros: Dict[str, Any]) -> Dict[str, Any]:
    """Traduce categorías usuales del usuario a valores reales del catálogo."""
    normalized = dict(filtros)
    for key, value in list(normalized.items()):
        term = _normalize_filter_term(value)
        if key.lower() == "puesto" and term in {
            "desarrollador",
            "desarrolladora",
            "desarrolladores",
            "desarrolladoras",
            "developer",
            "developers",
        }:
            normalized[key] = "Developer"
        elif key.lower() == "area" and term in {
            "desarrollador",
            "desarrolladora",
            "desarrolladores",
            "desarrolladoras",
        }:
            normalized[key] = "Desarrollo"
    return normalized


def mcp_execute_query(
    tabla: str,
    filtros: dict,
    agente_rol: str,
    limit: int = 10,
) -> dict:
    """Ejecuta una consulta segura con RBAC.

    Args:
        tabla: "empleados".
        filtros: Diccionario con filtros para la consulta.
        agente_rol: "Empleado".
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

        filtros = _normalize_employee_filters(filtros or {})
        role = str(agente_rol).strip()
        safe_limit = max(1, min(int(limit), 100))

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
                limit=safe_limit,
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


def mcp_count_employees(filtros: dict, agente_rol: str) -> dict:
    """Cuenta empleados usando todos los registros, no una muestra."""
    if str(agente_rol).strip() != "Empleado":
        return response(403, "forbidden", [], "Rol no autorizado.")
    try:
        safe_filters = _normalize_employee_filters(filtros or {})
        total = get_employee_count(get_connection(), safe_filters)
        return response(
            status_code=200,
            status="ok",
            message=f"Conteo completado: {total} empleado(s).",
            data={"total": total, "filters": safe_filters},
        )
    except (sqlite3.Error, ValueError) as exc:
        return response(400, "bad_request", [], str(exc))


def mcp_employee_distribution(
    group_by: str,
    filtros: dict,
    agente_rol: str,
) -> dict:
    """Distribuye empleados por área o puesto sin exponer salarios."""
    if str(agente_rol).strip() != "Empleado":
        return response(403, "forbidden", [], "Rol no autorizado.")
    try:
        safe_filters = _normalize_employee_filters(filtros or {})
        data = get_employee_distribution(get_connection(), group_by, safe_filters)
        return response(200, "ok", data, "Distribución calculada.")
    except (sqlite3.Error, ValueError) as exc:
        return response(400, "bad_request", [], str(exc))
