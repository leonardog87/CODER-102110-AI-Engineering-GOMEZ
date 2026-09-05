#!/usr/bin/env python3
"""Ejecuta las analíticas deterministas de empleados desde la terminal."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from data_access.service import (
    mcp_count_employees,
    mcp_employee_distribution,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation",
        choices=("count", "distribution"),
    )
    parser.add_argument("--role", choices=("Empleado",), default="Empleado")
    parser.add_argument("--area")
    parser.add_argument("--puesto")
    parser.add_argument("--group-by", choices=("area", "puesto"), default="area")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    filters = {
        key: value
        for key, value in {"Area": args.area, "Puesto": args.puesto}.items()
        if value
    }
    if args.operation == "count":
        result = mcp_count_employees(filters, args.role)
    elif args.operation == "distribution":
        result = mcp_employee_distribution(args.group_by, filters, args.role)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
