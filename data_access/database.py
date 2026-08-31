"""Conexión SQLite usada exclusivamente por el historial de chatBot."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from data_access.config import SQLITE_DB_PATH, logger

_CONN: Optional[sqlite3.Connection] = None


def open_sqlite_connection(db_path: Path = SQLITE_DB_PATH) -> sqlite3.Connection:
    """Abre la base persistente y crea su directorio cuando es necesario."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def get_connection() -> sqlite3.Connection:
    """Devuelve la conexión compartida, inicializándola bajo demanda."""
    global _CONN
    if _CONN is None:
        _CONN = open_sqlite_connection()
        logger.info("Historial SQLite listo en %s.", SQLITE_DB_PATH)
    return _CONN


def close_connection() -> None:
    """Cierra la conexión compartida."""
    global _CONN
    if _CONN is not None:
        _CONN.close()
        _CONN = None
