"""Helpers de seguridad y respuestas para MCP."""

from __future__ import annotations

from typing import Any, Dict, List

def response(
    status_code: int,
    status: str,
    data: Any = None,
    message: str = "",
) -> Dict[str, Any]:
    return {
        "status_code": status_code,
        "status": status,
        "message": message,
        "data": data,
    }
def sanitize_employee_output(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Elimina toda información salarial para el rol Empleado."""
    return [
        {
            key: value
            for key, value in row.items()
            if key.lower() != "sueldo_ars"
        }
        for row in rows
    ]
