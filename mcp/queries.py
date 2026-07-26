"""Consultas SQL y agregaciones para MCP."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, Iterable, List

from mcp.config import ALLOWED_TABLES, logger
from mcp.database import get_connection


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> List[Dict[str, Any]]:
    """Convierte filas SQLite a diccionarios nativos."""
    return [dict(row) for row in rows]


def build_where_clause(
    conn: sqlite3.Connection,
    tabla: str,
    filtros: Dict[str, Any],
) -> tuple[str, List[Any]]:
    """Construye un WHERE dinamico contra columnas reales de la tabla."""
    if not filtros:
        return "", []

    cursor = conn.execute(f"PRAGMA table_info({tabla})")
    real_columns = {row["name"].lower(): row["name"] for row in cursor.fetchall()}

    clauses: List[str] = []
    params: List[Any] = []
    for key, value in filtros.items():
        column = real_columns.get(key.lower())
        if not column:
            available = ", ".join(real_columns.values())
            raise ValueError(
                f"El filtro '{key}' no corresponde al esquema de {tabla}. "
                f"Campos disponibles: {available}."
            )

        if isinstance(value, str):
            clauses.append(f"{column} LIKE ?")
            params.append(f"%{value}%")
        else:
            clauses.append(f"{column} = ?")
            params.append(value)

    if not clauses:
        return "", []

    return " WHERE " + " AND ".join(clauses), params


def get_aggregated_data(
    conn: sqlite3.Connection,
    tabla: str,
    filtros: Dict[str, Any],
    include_stats: bool = False,
) -> Dict[str, Any]:
    """Devuelve total, muestra y estadisticas opcionales para una tabla."""
    logger.info(
        "_get_aggregated_data: tabla=%s, filtros=%s, include_stats=%s",
        tabla,
        filtros,
        include_stats,
    )

    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (tabla,),
    )
    if not cursor.fetchone():
        raise ValueError(f"La tabla '{tabla}' no existe en la base de datos")

    query_where, params = build_where_clause(conn, tabla, filtros)
    cursor = conn.execute(f"SELECT COUNT(*) as total FROM {tabla}{query_where}", params)
    row = cursor.fetchone()
    total = row["total"] if row else 0

    if total == 0:
        return {
            "total": 0,
            "sample": [],
            "stats": {},
            "message": "No se encontraron registros.",
        }

    if tabla == "empleados":
        sample_sql = f"""
            SELECT
                DNI,
                Apellido,
                Nombre,
                Area,
                Puesto,
                Sueldo_ARS
            FROM {tabla}{query_where}
            LIMIT 10
        """
    else:
        sample_sql = f"SELECT * FROM {tabla}{query_where} LIMIT 10"

    cursor = conn.execute(sample_sql, params)
    sample = rows_to_dicts(cursor.fetchall())
    stats = get_table_stats(conn, tabla, query_where, params) if include_stats else {}

    return {
        "total": total,
        "sample": sample,
        "stats": stats,
        "message": f"Se encontraron {total} registros. Mostrando muestra de {len(sample)}.",
    }


def get_table_stats(
    conn: sqlite3.Connection,
    tabla: str,
    query_where: str,
    params: List[Any],
) -> Dict[str, Any]:
    """Calcula estadisticas financieras/salariales segun tabla."""
    try:
        if tabla != "empleados":
            return {}
        stats_sql = f"""
            SELECT
                SUM(Sueldo_ARS) as total_sueldos,
                AVG(Sueldo_ARS) as promedio_sueldo
            FROM {tabla}{query_where}
        """

        cursor = conn.execute(stats_sql, params)
        stats = dict(cursor.fetchone() or {})
        return {
            key: round(float(value), 2) if value is not None else value
            for key, value in stats.items()
        }
    except Exception as exc:
        logger.warning("No se pudieron calcular estadisticas: %s", exc)
        return {}


def list_tables() -> List[str]:
    """Devuelve las tablas disponibles en la base persistente."""
    conn = get_connection()
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
    )
    return [row["name"] for row in cursor.fetchall()]


def preview_table(table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Vista rapida para depuracion local."""
    if table_name not in ALLOWED_TABLES:
        raise ValueError("Tabla invalida para preview.")

    conn = get_connection()
    cursor = conn.execute(f"SELECT * FROM {table_name} LIMIT ?", (int(limit),))
    return rows_to_dicts(cursor.fetchall())
