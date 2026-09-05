"""LangChain tools exposed to specialist agents."""

from __future__ import annotations
import json
import re
from typing import Any, Dict, List
from langchain_core.tools import tool

try:
    from rag.pipeline import retrieve_context
except Exception:  # pragma: no cover
    def retrieve_context(query: str, top_k: int = 2) -> str:
        return (
            "[FALLBACK RAG] No se pudo importar rag.pipeline.retrieve_context. "
            f"Consulta recibida: {query!r} | top_k={top_k}"
        )

try:
    from rag.knowledge_pipeline import retrieve_knowledge_context
except Exception:  # pragma: no cover
    def retrieve_knowledge_context(query: str, top_k: int = 2) -> str:
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
def rag_retrieve_context(query: str, top_k: int = 2) -> str:
    """Recupera contexto relevante desde la base documental RAG."""
    return retrieve_context(query=query, top_k=top_k)


@tool("knowledge_retrieve_context")
def knowledge_retrieve_context(query: str, top_k: int = 2) -> str:
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


def _employee_filters(
    *,
    area: str | None = None,
    puesto: str | None = None,
) -> Dict[str, Any]:
    return compact_filters(area=area, puesto=puesto)


def _call_employee_analytics(
    *,
    role: str,
    tool_name: str,
    arguments: Dict[str, Any],
) -> str:
    return safe_json(
        call_mcp_tool(
            role=role,
            tool_name=tool_name,
            arguments=arguments,
        )
    )


@tool("contar_empleados_mcp_empleado")
def contar_empleados_mcp_empleado(
    area: str | None = None,
    puesto: str | None = None,
) -> str:
    """Cuenta empleados por área o puesto sin acceder a salarios."""
    return _call_employee_analytics(
        role="Empleado",
        tool_name="contar_empleados",
        arguments=_employee_filters(area=area, puesto=puesto),
    )


@tool("distribucion_empleados_mcp_empleado")
def distribucion_empleados_mcp_empleado(
    group_by: str = "area",
    area: str | None = None,
    puesto: str | None = None,
) -> str:
    """Agrupa empleados por área o puesto sin información salarial."""
    return _call_employee_analytics(
        role="Empleado",
        tool_name="distribucion_empleados",
        arguments={
            "group_by": group_by,
            **_employee_filters(area=area, puesto=puesto),
        },
    )


@tool("consultar_politica_aplicable")
def consultar_politica_aplicable(accion: str) -> str:
    """Recupera controles internos aplicables a una acción o escenario."""
    return retrieve_context(query=accion, top_k=2)


def _combine_policy_and_area(*, role: str, politica: str, area: str) -> str:
    policy = retrieve_context(query=politica, top_k=2)
    employees = call_mcp_tool(
        role=role,
        tool_name="consultar_empleados",
        arguments={"area": area, "limit": 10},
    )
    return safe_json(
        {
            "policy_context": policy,
            "employee_data": employees,
            "area": area,
        }
    )


@tool("combinar_politica_con_area_empleado")
def combinar_politica_con_area_empleado(politica: str, area: str) -> str:
    """Combina una política con datos no salariales de un área."""
    return _combine_policy_and_area(role="Empleado", politica=politica, area=area)


@tool("verificar_respuesta_con_fuentes")
def verificar_respuesta_con_fuentes(respuesta: str, contexto: str) -> str:
    """Mide cobertura léxica y señala términos sin respaldo documental."""
    ignored = {
        "para", "como", "esta", "este", "sobre", "entre", "desde", "hasta",
        "debe", "deben", "datos", "informacion", "respuesta",
    }
    answer_terms = {
        token
        for token in re.findall(r"[a-záéíóúñ0-9]+", respuesta.lower())
        if len(token) > 3 and token not in ignored
    }
    context_terms = set(re.findall(r"[a-záéíóúñ0-9]+", contexto.lower()))
    supported = answer_terms & context_terms
    unsupported = sorted(answer_terms - context_terms)
    coverage = (
        round(len(supported) / len(answer_terms), 3)
        if answer_terms
        else 1.0
    )
    return safe_json(
        {
            "supported": coverage >= 0.6,
            "coverage": coverage,
            "unsupported_terms": unsupported[:20],
        }
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


