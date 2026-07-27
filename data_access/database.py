"""Conexion SQLite y migracion desde CSV."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd

from data_access.config import (
    ALLOWED_TABLES,
    EMPLEADOS_CSV_PATH,
    SQLITE_DB_PATH,
    logger,
)
from data_access.csv_loader import (
    EMPLEADO_COLUMNS,
    normalize_dataframe,
    read_empleados_csv,
)

_CONN: Optional[sqlite3.Connection] = None


def df_to_sqlite(conn: sqlite3.Connection, table_name: str, df: pd.DataFrame) -> None:
    """Reemplaza una tabla SQLite con el contenido de un DataFrame."""
    normalized = normalize_dataframe(df)
    normalized.to_sql(table_name, conn, if_exists="replace", index=False)


def open_sqlite_connection(db_path: Path = SQLITE_DB_PATH) -> sqlite3.Connection:
    """Abre la conexion SQLite persistente y crea el directorio si hace falta."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def migrate_empleados_to_sqlite(db_path: Path = SQLITE_DB_PATH) -> Path:
    """Valida empleados.csv y reemplaza la tabla empleados en SQLite."""
    conn = open_sqlite_connection(db_path)
    try:
        empleados_df = read_empleados_csv(EMPLEADOS_CSV_PATH)

        df_to_sqlite(conn, "empleados", empleados_df)
        conn.execute("DROP TABLE IF EXISTS clientes")
        conn.commit()
        logger.info("Migracion de empleados.csv -> SQLite completada en %s.", db_path)
        return db_path
    finally:
        conn.close()


def database_has_required_tables(conn: sqlite3.Connection) -> bool:
    cursor = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        """
    )
    existing_tables = {row["name"] for row in cursor.fetchall()}
    if not ALLOWED_TABLES.issubset(existing_tables):
        return False

    columns = conn.execute("PRAGMA table_info(empleados)").fetchall()
    return tuple(row["name"] for row in columns) == EMPLEADO_COLUMNS


def initialize_database() -> sqlite3.Connection:
    """Abre la base y garantiza que solo contenga los datos de empleados.csv."""
    conn = open_sqlite_connection()
    if not database_has_required_tables(conn):
        conn.close()
        migrate_empleados_to_sqlite(SQLITE_DB_PATH)
        conn = open_sqlite_connection()

    logger.info("Base de datos SQLite persistente lista en %s.", SQLITE_DB_PATH)
    return conn


def get_connection() -> sqlite3.Connection:
    """Devuelve la conexion global, inicializandola bajo demanda."""
    global _CONN
    if _CONN is None:
        _CONN = initialize_database()
    return _CONN


def close_connection() -> None:
    """Cierra la conexión global para apagado limpio o pruebas de reinicio."""
    global _CONN
    if _CONN is not None:
        _CONN.close()
        _CONN = None
