#!/usr/bin/env python3
"""Muestra el contenido de la base SQLite generada desde los archivos CSV.

Ejemplos:
    python ver_base_datos_sqlite.py
    python ver_base_datos_sqlite.py --tabla empleados
    python ver_base_datos_sqlite.py --tabla empleados --limite 20
    python ver_base_datos_sqlite.py --sin-limite
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Any, Sequence

from data_access.config import SQLITE_DB_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Consulta, sin modificar, la base SQLite migrada desde CSV."
    )
    parser.add_argument(
        "--tabla",
        help="Nombre de la tabla que se desea mostrar. Por defecto muestra todas.",
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=100,
        help="Cantidad máxima de filas por tabla (predeterminado: 100).",
    )
    parser.add_argument(
        "--sin-limite",
        action="store_true",
        help="Muestra todas las filas de las tablas seleccionadas.",
    )
    return parser.parse_args()


def get_table_names(conn: sqlite3.Connection) -> list[str]:
    cursor = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    )
    return [str(row[0]) for row in cursor.fetchall()]


def format_value(value: Any) -> str:
    if value is None:
        return "NULL"
    return str(value).replace("\n", " ")


def print_rows(columns: Sequence[str], rows: Sequence[sqlite3.Row]) -> None:
    values = [[format_value(row[column]) for column in columns] for row in rows]
    widths = [
        max(len(column), *(len(row[index]) for row in values))
        for index, column in enumerate(columns)
    ]
    separator = "-+-".join("-" * width for width in widths)

    print(" | ".join(column.ljust(widths[index]) for index, column in enumerate(columns)))
    print(separator)
    for row in values:
        print(" | ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def print_table(
    conn: sqlite3.Connection,
    table_name: str,
    limit: int | None,
) -> None:
    # El nombre proviene de sqlite_master, no de una entrada arbitraria.
    quoted_name = table_name.replace('"', '""')
    total = conn.execute(
        f'SELECT COUNT(*) FROM "{quoted_name}"'
    ).fetchone()[0]

    query = f'SELECT * FROM "{quoted_name}"'
    parameters: tuple[int, ...] = ()
    if limit is not None:
        query += " LIMIT ?"
        parameters = (limit,)

    cursor = conn.execute(query, parameters)
    rows = cursor.fetchall()
    columns = [description[0] for description in cursor.description or []]

    print(f"\nTabla: {table_name} ({total} filas)")
    if not rows:
        print("(sin registros)")
        return

    print_rows(columns, rows)
    if limit is not None and total > limit:
        print(f"\nSe muestran {limit} de {total} filas.")


def main() -> int:
    args = parse_args()
    db_path = Path(SQLITE_DB_PATH)

    if args.limite < 1:
        raise SystemExit("El valor de --limite debe ser mayor que cero.")
    if not db_path.is_file():
        raise SystemExit(
            f"No se encontró la base de datos: {db_path}\n"
            "Creala ejecutando: python migrar_csv_a_sqlite.py"
        )

    # mode=ro garantiza que este visor no pueda modificar la base.
    db_uri = f"{db_path.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(db_uri, uri=True) as conn:
        conn.row_factory = sqlite3.Row
        tables = get_table_names(conn)

        if not tables:
            raise SystemExit("La base de datos no contiene tablas.")
        if args.tabla and args.tabla not in tables:
            available = ", ".join(tables)
            raise SystemExit(
                f"La tabla '{args.tabla}' no existe. Tablas disponibles: {available}"
            )

        selected_tables = [args.tabla] if args.tabla else tables
        limit = None if args.sin_limite else args.limite

        print(f"Base de datos: {db_path.resolve()}")
        print(f"Tablas disponibles: {', '.join(tables)}")
        for table_name in selected_tables:
            print_table(conn, table_name, limit)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
