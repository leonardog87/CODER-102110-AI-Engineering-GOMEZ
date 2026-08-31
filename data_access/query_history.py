"""Persistencia del historial único de chatBot."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from data_access.database import get_connection

HISTORY_SCOPE = "General"


def _validate_role(role: str) -> str:
    normalized = str(role).strip()
    if normalized != HISTORY_SCOPE:
        raise ValueError(f"Ámbito no autorizado para historial: {role!r}")
    return HISTORY_SCOPE


def _create_query_history_table(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS query_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            role TEXT NOT NULL DEFAULT 'General' CHECK (role = 'General'),
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


def ensure_query_history_table() -> None:
    """Crea o migra el historial anterior basado en roles."""
    conn = get_connection()
    table = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'query_history'"
    ).fetchone()
    if table is not None and "role = 'General'" not in str(table["sql"]):
        conn.execute("DROP INDEX IF EXISTS idx_query_history_role_id")
        conn.execute("ALTER TABLE query_history RENAME TO query_history_legacy")
        _create_query_history_table(conn)
        conn.execute(
            """
            INSERT INTO query_history (
                id, created_at, role, agent_name, user_query,
                assistant_response, designation_reason, tool_traces_json,
                cycle_count, evaluation_decision, evaluation_reason
            )
            SELECT
                id, created_at, 'General', 'chatBot', user_query,
                assistant_response, 'Registro migrado al agente único.',
                tool_traces_json, cycle_count, evaluation_decision,
                evaluation_reason
            FROM query_history_legacy
            """
        )
        conn.execute("DROP TABLE query_history_legacy")
    else:
        _create_query_history_table(conn)
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
    """Guarda una interacción en el historial único."""
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
    """Recupera las consultas del historial único."""
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
