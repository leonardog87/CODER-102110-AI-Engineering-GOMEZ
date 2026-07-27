"""LangChain tools exposed to specialist agents."""

from __future__ import annotations
import json
from typing import Any, Dict, List
from langchain_core.tools import tool

try:
    from rag.pipeline import retrieve_context
except Exception:  # pragma: no cover
    def retrieve_context(query: str, top_k: int = 3) -> str:
        return (
            "[FALLBACK RAG] No se pudo importar rag.pipeline.retrieve_context. "
            f"Consulta recibida: {query!r} | top_k={top_k}"
        )

try:
    from rag.knowledge_pipeline import retrieve_knowledge_context
except Exception:  # pragma: no cover
    def retrieve_knowledge_context(query: str, top_k: int = 3) -> str:
        return (
            "[FALLBACK KNOWLEDGE] No se pudo importar "
            "rag.knowledge_pipeline.retrieve_knowledge_context. "
            f"Consulta recibida: {query!r} | top_k={top_k}"
        )

from agent_system.mcp_client import call_mcp_tool


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


@tool("knowledge_retrieve_context")
def knowledge_retrieve_context(query: str, top_k: int = 3) -> str:
    """Consulta manuales y PDF de la base de conocimiento no parametrizado."""
    return retrieve_knowledge_context(query=query, top_k=top_k)


def _consultar_empleados(
    *,
    agente_rol: str,
    dni: str | None,
    nombre: str | None,
    apellido: str | None,
    area: str | None,
    puesto: str | None,
) -> str:
    # ✅ Límite fijo interno (el usuario no necesita especificarlo)
    LIMIT = 10
    
    arguments = compact_filters(
        dni=dni,
        nombre=nombre,
        apellido=apellido,
        area=area,
        puesto=puesto,
        limit=LIMIT,
    )
    resultado = call_mcp_tool(
        role=agente_rol,
        tool_name="consultar_empleados",
        arguments=arguments,
    )
    return safe_json(
        truncar_resultado(
            resultado,
            max_items=LIMIT,
        )
    )


@tool("consultar_empleados_mcp_empleado")
def consultar_empleados_mcp_empleado(
    dni: str | None = None,
    nombre: str | None = None,
    apellido: str | None = None,
    area: str | None = None,
    puesto: str | None = None,
) -> str:
    """Consulta empleados sin exponer salarios ni estadísticas salariales.
    
    Args:
        dni: Filtrar por DNI (opcional)
        nombre: Filtrar por nombre (opcional)
        apellido: Filtrar por apellido (opcional)
        area: Filtrar por área (opcional)
        puesto: Filtrar por puesto (opcional)
    """
    return _consultar_empleados(
        agente_rol="Empleado",
        dni=dni,
        nombre=nombre,
        apellido=apellido,
        area=area,
        puesto=puesto,
    )


@tool("consultar_empleados_mcp_administrador")
def consultar_empleados_mcp_administrador(
    dni: str | None = None,
    nombre: str | None = None,
    apellido: str | None = None,
    area: str | None = None,
    puesto: str | None = None,
) -> str:
    """Consulta completa de empleados, incluidos salarios y estadísticas.
    
    Args:
        dni: Filtrar por DNI (opcional)
        nombre: Filtrar por nombre (opcional)
        apellido: Filtrar por apellido (opcional)
        area: Filtrar por área (opcional)
        puesto: Filtrar por puesto (opcional)
    """
    return _consultar_empleados(
        agente_rol="Administrador",
        dni=dni,
        nombre=nombre,
        apellido=apellido,
        area=area,
        puesto=puesto,
    )