"""Prueba de integración cliente-servidor usando el protocolo MCP oficial."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


async def check_role(role: str) -> None:
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[
            str(PROJECT_ROOT / "mcp_server.py"),
            "--role",
            role,
            "--transport",
            "stdio",
        ],
        cwd=PROJECT_ROOT,
        env={
            **os.environ,
            "LANGCHAIN_TRACING_V2": "false",
            "LANGSMITH_TRACING": "false",
        },
    )
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = {
                tool.name: tool for tool in (await session.list_tools()).tools
            }
            assert "consultar_permisos" in tools

            if role == "Invitado":
                assert "consultar_empleados" not in tools
                assert "contar_empleados" not in tools
                assert "distribucion_empleados" not in tools
                assert "estadisticas_salariales" not in tools
                return

            assert "consultar_empleados" in tools
            assert "contar_empleados" in tools
            assert "distribucion_empleados" in tools
            if role == "Administrador":
                assert "estadisticas_salariales" in tools
            else:
                assert "estadisticas_salariales" not in tools
            result = await session.call_tool(
                "consultar_empleados",
                {"area": "Infraestructura", "limit": 20},
            )
            assert not result.isError
            payload = json.dumps(result.structuredContent, ensure_ascii=False)
            if role == "Empleado":
                assert "Sueldo_ARS" not in payload
                assert "promedio_sueldo" not in payload
            else:
                assert "Sueldo_ARS" in payload
                assert "promedio_sueldo" in payload

            count_result = await session.call_tool(
                "contar_empleados",
                {"puesto": "desarrolladores"},
            )
            assert count_result.structuredContent["result"]["data"]["total"] == 4

            distribution_result = await session.call_tool(
                "distribucion_empleados",
                {"group_by": "area"},
            )
            distribution = distribution_result.structuredContent["result"]["data"]
            assert distribution["total"] == 20
            assert sum(group["cantidad"] for group in distribution["groups"]) == 20

            if role == "Administrador":
                salary_result = await session.call_tool(
                    "estadisticas_salariales",
                    {"area": "Infraestructura"},
                )
                salary = salary_result.structuredContent["result"]["data"]
                assert salary["total"] == 3
                assert salary["mediana"] == 4100000


async def main() -> None:
    for role in ("Invitado", "Empleado", "Administrador"):
        await check_role(role)
    print("[OK] Negociación y descubrimiento MCP")
    print("[OK] Invitado sin herramienta SQLite")
    print("[OK] Empleado sin información salarial")
    print("[OK] Administrador con acceso completo")


if __name__ == "__main__":
    asyncio.run(main())
