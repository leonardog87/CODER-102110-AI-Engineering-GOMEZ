"""Persistencia de consultas y auditoría aislada por rol."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from data_access.database import get_connection

ALLOWED_HISTORY_ROLES = {"Invitado", "Empleado"}


def _validate_role(role: str) -> str:
    normalized = str(role).strip()
    if normalized not in ALLOWED_HISTORY_ROLES:
        raise ValueError(f"Rol no autorizado para historial: {role!r}")
    return normalized


def ensure_query_history_table() -> None:
    """Crea la tabla persistente sin alterar la tabla de empleados."""
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS query_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            role TEXT NOT NULL CHECK (
                role IN ('Invitado', 'Empleado')
            ),
            agent_name TEXT NOT NULL,
            user_query TEXT NOT NULL,
            assistant_response TEXT NOT NULL,
            designation_reason TEXT NOT NULL,
            tool_traces_json TEXT NOT NULL DEFAULT '[]',
            cycle_count INTEGER NOT NULL DEFAULT 1,
            evaluation_decision TEXT NOT NULL DEFAULT 'end',
            evaluation_reason TEXT NOT NULL DEFAULT ''
        )
        """
    )
    existing_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(query_history)")
    }
    migrations = {
        "cycle_count": "INTEGER NOT NULL DEFAULT 1",
        "evaluation_decision": "TEXT NOT NULL DEFAULT 'end'",
        "evaluation_reason": "TEXT NOT NULL DEFAULT ''",
    }
    for column_name, definition in migrations.items():
        if column_name not in existing_columns:
            conn.execute(
                f"ALTER TABLE query_history ADD COLUMN {column_name} {definition}"
            )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_query_history_role_id
        ON query_history(role, id)
        """
    )
    conn.commit()


def save_query_record(
    *,
    role: str,
    agent_name: str,
    user_query: str,
    assistant_response: str,
    designation_reason: str,
    tool_traces: List[Dict[str, Any]],
    cycle_count: int = 1,
    evaluation_decision: str = "end",
    evaluation_reason: str = "",
) -> int:
    """Guarda una interacción asociada exclusivamente a su rol."""
    authorized_role = _validate_role(role)
    ensure_query_history_table()
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO query_history (
            role,
            agent_name,
            user_query,
            assistant_response,
            designation_reason,
            tool_traces_json,
            cycle_count,
            evaluation_decision,
            evaluation_reason
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            authorized_role,
            str(agent_name),
            str(user_query),
            str(assistant_response),
            str(designation_reason),
            json.dumps(tool_traces, ensure_ascii=False, default=str),
            max(1, int(cycle_count)),
            str(evaluation_decision),
            str(evaluation_reason),
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def load_query_history(role: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Recupera solamente las consultas pertenecientes al rol solicitado."""
    authorized_role = _validate_role(role)
    safe_limit = max(1, min(int(limit), 500))
    ensure_query_history_table()
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT *
        FROM (
            SELECT
                id,
                created_at,
                role,
                agent_name,
                user_query,
                assistant_response,
                designation_reason,
                tool_traces_json,
                cycle_count,
                evaluation_decision,
                evaluation_reason
            FROM query_history
            WHERE role = ?
            ORDER BY id DESC
            LIMIT ?
        )
        ORDER BY id ASC
        """,
        (authorized_role, safe_limit),
    ).fetchall()

    records: List[Dict[str, Any]] = []
    for row in rows:
        record = dict(row)
        try:
            record["tool_traces"] = json.loads(record.pop("tool_traces_json"))
        except (TypeError, json.JSONDecodeError):
            record["tool_traces"] = []
            record.pop("tool_traces_json", None)
        records.append(record)
    return records
