"""LangChain tools exposed to specialist agents."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from langchain_core.tools import tool

try:
    from rag_pipeline import retrieve_context
except Exception:  # pragma: no cover

    def retrieve_context(query: str, top_k: int = 3) -> str:
        return (
            "[FALLBACK RAG] No se pudo importar rag_pipeline.retrieve_context. "
            f"Consulta recibida: {query!r} | top_k={top_k}"
        )

try:
    from mcp_server import mcp_execute_query
except Exception:  # pragma: no cover

    def mcp_execute_query(tabla: str, filtros: dict, agente_rol: str) -> dict:
        return {
            "status_code": 500,
            "status": "error",
            "message": "No se pudo importar mcp_server.mcp_execute_query.",
            "data": [],
        }


def compact_filters(**kwargs: Any) -> Dict[str, Any]:
    filtros: Dict[str, Any] = {}
    for key, value in kwargs.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        filtros[key] = value
    return filtros


def safe_json(data: Any) -> str:
    try:
        return json.dumps(data, ensure_ascii=False, default=str)
    except Exception:
        return json.dumps({"error": "No se pudo serializar el resultado."}, ensure_ascii=False)


def truncar_resultado(resultado: Dict[str, Any], max_items: int = 3) -> Dict[str, Any]:
    """
    Trunca listas grandes en el resultado.
    Ahora trabaja con el nuevo formato de datos agregados.
    """
    if "data" in resultado and isinstance(resultado["data"], dict):
        data = resultado["data"]
        
        # Si tiene "sample", usarlo en lugar de "data"
        if "sample" in data and isinstance(data["sample"], list):
            total = data.get("total", len(data["sample"]))
            if total > max_items:
                data["sample"] = data["sample"][:max_items]
                data["message"] = f"Mostrando {max_items} de {total} registros (muestra)"
    
    return resultado


# ──────────────────────────────────────────────────────────────
# ✅ TOOL: RAG
# ──────────────────────────────────────────────────────────────
@tool("rag_retrieve_context")
def rag_retrieve_context(query: str, top_k: int = 3) -> str:
    """Recupera contexto relevante desde la base documental RAG."""
    return retrieve_context(query=query, top_k=top_k)


# ──────────────────────────────────────────────────────────────
# ✅ TOOL: Consultar clientes para Soporte
# ──────────────────────────────────────────────────────────────
@tool("consultar_clientes_mcp_soporte")
def consultar_clientes_mcp_soporte(
    cliente_id: str | None = None,
    nombre: str | None = None,
    estado: str | None = None,
    segmento: str | None = None,
) -> str:
    """Consulta segura de clientes para el rol Soporte_Nivel_1."""

    filtros = compact_filters(
        Cliente_ID=cliente_id,
        Nombre=nombre,
        Estado=estado,
        Segmento=segmento,
    )
    resultado = mcp_execute_query(
        tabla="clientes",
        filtros=filtros,
        agente_rol="Soporte_Nivel_1",
    )
    resultado = truncar_resultado(resultado, max_items=5)
    return safe_json(resultado)


# ──────────────────────────────────────────────────────────────
# ✅ TOOL: Consultar clientes para Admin
# ──────────────────────────────────────────────────────────────
@tool("consultar_clientes_mcp_admin")
def consultar_clientes_mcp_admin(
    cliente_id: str | None = None,
    nombre: str | None = None,
    estado: str | None = None,
    segmento: str | None = None,
) -> str:
    """Consulta completa de clientes para el rol Admin_Nivel_2."""

    filtros = compact_filters(
        Cliente_ID=cliente_id,
        Nombre=nombre,
        Estado=estado,
        Segmento=segmento,
    )
    resultado = mcp_execute_query(
        tabla="clientes",
        filtros=filtros,
        agente_rol="Admin_Nivel_2",
    )
    resultado = truncar_resultado(resultado, max_items=5)
    return safe_json(resultado)


# ──────────────────────────────────────────────────────────────
# ✅ TOOL: Consultar empleados para Admin (ÚNICA DEFINICIÓN)
# ──────────────────────────────────────────────────────────────
@tool("consultar_empleados_mcp_admin")
def consultar_empleados_mcp_admin(
    empleado_id: str | None = None,
    nombre: str | None = None,
    area: str | None = None,
    rol: str | None = None,
) -> str:
    """Consulta completa de empleados para el rol Admin_Nivel_2."""
    
    filtros = compact_filters(
        Empleado_ID=empleado_id,
        Nombre=nombre,
        Area=area,
        Rol=rol,
    )
    resultado = mcp_execute_query(
        tabla="empleados",
        filtros=filtros,
        agente_rol="Admin_Nivel_2",
    )
    
    resultado = truncar_resultado(resultado, max_items=3)
    return safe_json(resultado)