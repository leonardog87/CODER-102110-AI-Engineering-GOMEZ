"""
Migra empleados.csv de raw_data a la base SQLite del proyecto.

Uso:
    python migrar_csv_a_sqlite.py
"""

from __future__ import annotations

import json

from mcp.server import SQLITE_DB_PATH, get_connection, migrate_empleados_to_sqlite


def main() -> None:
    db_path = migrate_empleados_to_sqlite(SQLITE_DB_PATH)
    conn = get_connection()
    summary = {}

    for table_name in ("empleados",):
        cursor = conn.execute(f"SELECT COUNT(*) AS total FROM {table_name}")
        summary[table_name] = cursor.fetchone()["total"]

    print(
        json.dumps(
            {
                "sqlite_db": str(db_path),
                "tablas": summary,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
