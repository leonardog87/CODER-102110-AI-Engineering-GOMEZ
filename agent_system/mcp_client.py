"""Adaptador cliente para consumir el servidor MCP estándar."""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _role_url(role: str) -> str:
    role_key = str(role).upper()
    return os.getenv(f"AGENT_MCP_{role_key}_URL", "").strip()


def _unwrap_structured_content(content: Any) -> Dict[str, Any]:
    if not isinstance(content, dict):
        raise RuntimeError("El servidor MCP no devolvió contenido estructurado.")
    result = content.get("result", content)
    if not isinstance(result, dict):
        raise RuntimeError("La respuesta estructurada MCP no contiene un objeto.")
    return result


async def _call_over_session(
    session: ClientSession,
    tool_name: str,
    arguments: Dict[str, Any],
) -> Dict[str, Any]:
    await session.initialize()
    available = {tool.name for tool in (await session.list_tools()).tools}
    if tool_name not in available:
        raise PermissionError(
            f"La herramienta MCP '{tool_name}' no está disponible para esta instancia."
        )
    response = await session.call_tool(tool_name, arguments)
    if response.isError:
        raise RuntimeError(f"El servidor MCP rechazó la llamada: {response.content}")
    return _unwrap_structured_content(response.structuredContent)


async def call_mcp_tool_async(
    *,
    role: str,
    tool_name: str,
    arguments: Dict[str, Any],
) -> Dict[str, Any]:
    """Consume una herramienta por HTTP si hay URL; de lo contrario usa stdio."""
    url = _role_url(role)
    if url:
        async with streamable_http_client(url) as (read, write, _session_id):
            async with ClientSession(
                read,
                write,
                read_timeout_seconds=timedelta(seconds=30),
            ) as session:
                return await _call_over_session(
                    session,
                    tool_name,
                    arguments,
                )

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
    )
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(
            read,
            write,
            read_timeout_seconds=timedelta(seconds=30),
        ) as session:
            return await _call_over_session(
                session,
                tool_name,
                arguments,
            )


def call_mcp_tool(
    *,
    role: str,
    tool_name: str,
    arguments: Dict[str, Any],
) -> Dict[str, Any]:
    """Puente síncrono utilizado por las herramientas de LangChain."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            call_mcp_tool_async(
                role=role,
                tool_name=tool_name,
                arguments=arguments,
            )
        )
    raise RuntimeError(
        "call_mcp_tool no puede ejecutarse dentro de un event loop activo; "
        "use call_mcp_tool_async."
    )
