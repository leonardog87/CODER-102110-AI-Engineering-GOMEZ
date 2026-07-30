"""Consultas SQL y agregaciones para MCP."""

from __future__ import annotations

import sqlite3
from statistics import median
from typing import Any, Dict, Iterable, List

from data_access.config import ALLOWED_TABLES, logger
from data_access.database import get_connection


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
    sample_limit: int = 10,
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

    safe_limit = max(1, min(int(sample_limit), 100))
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
            LIMIT ?
        """
    else:
        sample_sql = f"SELECT * FROM {tabla}{query_where} LIMIT 10"

    cursor = conn.execute(sample_sql, [*params, safe_limit])
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


def get_salary_statistics(
    conn: sqlite3.Connection,
    filtros: Dict[str, Any],
) -> Dict[str, Any]:
    """Calcula estadísticas salariales sobre todas las filas filtradas."""
    query_where, params = build_where_clause(conn, "empleados", filtros)
    rows = conn.execute(
        f"SELECT Sueldo_ARS FROM empleados{query_where} ORDER BY Sueldo_ARS",
        params,
    ).fetchall()
    salaries = [float(row["Sueldo_ARS"]) for row in rows]
    if not salaries:
        return {
            "total": 0,
            "promedio": None,
            "mediana": None,
            "minimo": None,
            "maximo": None,
            "suma": 0,
        }
    return {
        "total": len(salaries),
        "promedio": round(sum(salaries) / len(salaries), 2),
        "mediana": round(float(median(salaries)), 2),
        "minimo": min(salaries),
        "maximo": max(salaries),
        "suma": sum(salaries),
    }


def get_employee_count(
    conn: sqlite3.Connection,
    filtros: Dict[str, Any],
) -> int:
    """Cuenta empleados sin materializar muestras ni calcular salarios."""
    query_where, params = build_where_clause(conn, "empleados", filtros)
    row = conn.execute(
        f"SELECT COUNT(*) AS total FROM empleados{query_where}",
        params,
    ).fetchone()
    return int(row["total"]) if row else 0


def get_employee_distribution(
    conn: sqlite3.Connection,
    group_by: str,
    filtros: Dict[str, Any],
) -> Dict[str, Any]:
    """Agrupa empleados por Área o Puesto con cantidades y porcentajes."""
    columns = {"area": "Area", "puesto": "Puesto"}
    column = columns.get(str(group_by).strip().lower())
    if column is None:
        raise ValueError("group_by debe ser 'area' o 'puesto'.")

    query_where, params = build_where_clause(conn, "empleados", filtros)
    rows = conn.execute(
        f"""
        SELECT {column} AS categoria, COUNT(*) AS cantidad
        FROM empleados{query_where}
        GROUP BY {column}
        ORDER BY cantidad DESC, categoria ASC
        """,
        params,
    ).fetchall()
    total = sum(int(row["cantidad"]) for row in rows)
    groups = [
        {
            "categoria": row["categoria"],
            "cantidad": int(row["cantidad"]),
            "porcentaje": round((int(row["cantidad"]) / total) * 100, 2),
        }
        for row in rows
    ] if total else []
    return {"group_by": column, "total": total, "groups": groups}


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
