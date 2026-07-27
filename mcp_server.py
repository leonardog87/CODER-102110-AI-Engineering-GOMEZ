#!/usr/bin/env python3
"""Servidor MCP estándar para consultar datos según un rol fijo."""

from __future__ import annotations

import argparse
import os
from typing import Any, Dict, Literal

from mcp.server.fastmcp import FastMCP

from data_access.service import mcp_execute_query

McpRole = Literal["Invitado", "Empleado", "Administrador"]
ALLOWED_MCP_ROLES = {"Invitado", "Empleado", "Administrador"}


def normalize_role(role: str) -> McpRole:
    aliases = {
        "invitado": "Invitado",
        "empleado": "Empleado",
        "administrador": "Administrador",
        "admin": "Administrador",
    }
    normalized = aliases.get(str(role).strip().lower())
    if normalized not in ALLOWED_MCP_ROLES:
        raise ValueError(
            "Rol MCP inválido. Use Invitado, Empleado o Administrador."
        )
    return normalized  # type: ignore[return-value]


def create_mcp_server(
    role: str,
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> FastMCP:
    """Crea un servidor cuya superficie de herramientas queda fijada por rol."""
    authorized_role = normalize_role(role)
    server = FastMCP(
        name=f"agente-corporativo-{authorized_role.lower()}",
        instructions=(
            f"Servidor de datos del Agente Corporativo IA. "
            f"Rol autorizado de esta instancia: {authorized_role}. "
            "El rol se fija al iniciar y no se acepta como argumento del cliente."
        ),
        host=host,
        port=port,
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
    )

    @server.tool(
        name="consultar_permisos",
        description="Informa el rol fijo y los datos permitidos por esta instancia.",
        structured_output=True,
    )
    def consultar_permisos() -> Dict[str, Any]:
        if authorized_role == "Invitado":
            access = "Sin acceso a la base SQLite de empleados."
        elif authorized_role == "Empleado":
            access = "Empleados sin Sueldo_ARS ni estadísticas salariales."
        else:
            access = "Acceso completo a empleados, salarios y estadísticas."
        return {"role": authorized_role, "sqlite_access": access}

    @server.resource(
        "schema://empleados",
        name="esquema_empleados",
        description="Esquema visible de empleados para el rol de la instancia.",
        mime_type="application/json",
    )
    def esquema_empleados() -> Dict[str, Any]:
        base_fields = ["DNI", "Apellido", "Nombre", "Area", "Puesto"]
        fields = (
            [*base_fields, "Sueldo_ARS"]
            if authorized_role == "Administrador"
            else base_fields
        )
        return {
            "role": authorized_role,
            "accessible": authorized_role != "Invitado",
            "fields": fields if authorized_role != "Invitado" else [],
        }

    if authorized_role in {"Empleado", "Administrador"}:

        @server.tool(
            name="consultar_empleados",
            description=(
                "Consulta empleados por campos autorizados. "
                "El rol Empleado nunca recibe salarios; Administrador sí."
            ),
            structured_output=True,
        )
        def consultar_empleados(
            dni: str | None = None,
            nombre: str | None = None,
            apellido: str | None = None,
            area: str | None = None,
            puesto: str | None = None,
            limit: int = 10,
        ) -> Dict[str, Any]:
            filtros = {
                key: value
                for key, value in {
                    "DNI": dni,
                    "Nombre": nombre,
                    "Apellido": apellido,
                    "Area": area,
                    "Puesto": puesto,
                }.items()
                if value is not None and str(value).strip()
            }
            return mcp_execute_query(
                tabla="empleados",
                filtros=filtros,
                agente_rol=authorized_role,
                limit=limit,
            )

    return server


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Servidor MCP interoperable del Agente Corporativo IA."
    )
    parser.add_argument(
        "--role",
        default=os.getenv("AGENT_MCP_ROLE", "Invitado"),
        help="Rol fijo de la instancia: Invitado, Empleado o Administrador.",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "sse", "streamable-http"),
        default=os.getenv("AGENT_MCP_TRANSPORT", "stdio"),
    )
    parser.add_argument("--host", default=os.getenv("AGENT_MCP_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("AGENT_MCP_PORT", "8000")),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server = create_mcp_server(args.role, host=args.host, port=args.port)
    server.run(transport=args.transport)


if __name__ == "__main__":
    main()
