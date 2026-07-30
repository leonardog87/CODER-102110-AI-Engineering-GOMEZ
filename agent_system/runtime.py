"""Shared execution logic for specialist agents."""

from __future__ import annotations

import logging
import json
import re
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage

from agent_system.models import build_chat_model, fallback_chat_model
from agent_system.tools import safe_json


def _ensure_valid_response(
    messages: List[BaseMessage],
    fallback_content: str = "He procesado tu consulta."
) -> List[BaseMessage]:
    """
    Garantiza que el último mensaje sea un AIMessage con contenido válido.
    """
    logger.info("🔍 _ensure_valid_response - INICIO")
    logger.info(f"  Mensajes recibidos: {len(messages)}")
    
    if not messages:
        logger.info("  No hay mensajes, creando fallback")
        return [AIMessage(content=fallback_content)]
    
    # Buscar el último AIMessage con contenido válido
    last_valid_index = -1
    
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if isinstance(msg, AIMessage):
            content = getattr(msg, "content", "") or ""
            if content and not content.strip().startswith("{"):
                last_valid_index = i
                logger.info(f"  ✅ AIMessage válido en posición {i}: {content[:50]}...")
                break
    
    # Si encontramos un AIMessage válido, asegurarlo como último
    if last_valid_index != -1:
        if last_valid_index != len(messages) - 1:
            messages[-1] = messages[last_valid_index]
            logger.info(f"  🔄 Reemplazando último con AIMessage de posición {last_valid_index}")
        else:
            logger.info("  ✅ El último mensaje ya es válido")
        return messages
    
    # No hay AIMessage válido, crear fallback
    logger.info("  ⚠️ No hay AIMessage válido, creando fallback")
    messages.append(AIMessage(content=fallback_content))
    return messages


def _truncate_tool_result_if_needed(content: str, max_chars: int = 1500) -> str:
    """Reduce muestras grandes sin romper el JSON ni perder total/estadísticas."""
    if not isinstance(content, str) or len(content) <= max_chars:
        return content

    try:
        payload = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return content[:max_chars] + "... [RESULTADO TRUNCADO]"

    if not isinstance(payload, dict):
        return content[:max_chars] + "... [RESULTADO TRUNCADO]"

    aggregated = payload.get("data")
    if isinstance(aggregated, dict) and isinstance(aggregated.get("sample"), list):
        sample = list(aggregated["sample"])
        original_sample_size = len(sample)
        while sample:
            aggregated["sample"] = sample
            serialized = json.dumps(payload, ensure_ascii=False, default=str)
            if len(serialized) <= max_chars:
                if len(sample) < original_sample_size:
                    aggregated["message"] = (
                        f"Total: {aggregated.get('total', 0)}. "
                        f"Muestra reducida a {len(sample)} registros para el modelo."
                    )
                return json.dumps(payload, ensure_ascii=False, default=str)
            sample.pop()

        aggregated["sample"] = []
        aggregated["message"] = (
            f"Total: {aggregated.get('total', 0)}. "
            "La muestra se omitió por tamaño; total y estadísticas se conservaron."
        )
        return json.dumps(payload, ensure_ascii=False, default=str)

    return content[:max_chars] + "... [RESULTADO TRUNCADO]"


logger = logging.getLogger("agente_corporativo.agent_system.runtime")


def _invoke_with_fallback(model: Any, messages: List[BaseMessage], tools: List[Any] | None = None):
    logger.info(f"🔍 _invoke_with_fallback - Invocando modelo con {len(messages)} mensajes")
    try:
        result = model.invoke(messages)
        logger.info(f"✅ Modelo invocado correctamente")
        return result
    except Exception as exc:
        logger.warning("Fallo la invocacion del modelo principal; usando fallback offline: %s", exc)
        fallback_model = fallback_chat_model()
        if tools:
            fallback_model = fallback_model.bind_tools(tools)
        return fallback_model.invoke(messages)


def _tool_calls_from_text(content: Any) -> List[Dict[str, Any]]:
    """
    Accept tool calls emitted as plain JSON by models without native tool mode.
    """
    if not isinstance(content, str) or not content.strip():
        return []

    pattern = r'<tools>\s*({.*?})\s*</tools>'
    matches = re.findall(pattern, content, re.DOTALL)
    
    for match in matches:
        try:
            payload = json.loads(match)
            if isinstance(payload, dict):
                name = payload.get("name")
                args = payload.get("arguments", {})
                if isinstance(name, str) and isinstance(args, dict):
                    return [{"name": name, "args": args, "id": "text_tool_call"}]
        except json.JSONDecodeError:
            continue
    
    json_pattern = r'\{[^{}]*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^{}]*\}\s*\}'
    json_matches = re.findall(json_pattern, content, re.DOTALL)
    
    for match in json_matches:
        try:
            payload = json.loads(match)
            if isinstance(payload, dict):
                name = payload.get("name")
                args = payload.get("arguments", {})
                if isinstance(name, str) and isinstance(args, dict):
                    return [{"name": name, "args": args, "id": "text_tool_call"}]
        except json.JSONDecodeError:
            continue
    
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return []

    if not isinstance(payload, dict):
        return []

    name = payload.get("name")
    args = payload.get("arguments", {})
    if not isinstance(name, str) or not isinstance(args, dict):
        return []

    return [{"name": name, "args": args, "id": "text_tool_call"}]


def _clean_tool_tags(content: str) -> str:
    """Elimina los bloques <tools> y el JSON de herramientas del contenido."""
    content = re.sub(r'<tools>.*?</tools>', '', content, flags=re.DOTALL)
    json_pattern = r'\{[^{}]*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^{}]*\}\s*\}'
    content = re.sub(json_pattern, '', content, flags=re.DOTALL)
    return content.strip()


def _looks_like_text_tool_call(content: Any) -> bool:
    return bool(_tool_calls_from_text(content))


def _is_count_query(text: str) -> bool:
    normalized = _normalize_text(text)
    return any(
        expression in normalized
        for expression in (
            "cantidad de empleado",
            "cuantos empleado",
            "cuantas empleado",
            "total de empleado",
            "numero de empleado",
        )
    )


def _format_tool_result_for_user(
    tool_messages: List[ToolMessage],
    user_text: str = "",
) -> str:
    """Formatea resultados agregados de forma legible (FALLBACK cuando el LLM falla)."""
    if not tool_messages:
        return ""

    payload = None
    for tool_message in reversed(tool_messages):
        try:
            candidate = json.loads(str(tool_message.content))
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            payload = candidate
            break

    if not isinstance(payload, dict):
        return ""

    status = payload.get("status")
    message = payload.get("message") or ""
    data = payload.get("data")

    if status != "ok":
        return message or "No se pudo completar la consulta solicitada."

    if isinstance(data, dict):
        total = data.get("total", 0)
        sample = data.get("sample", [])
        stats = data.get("stats", {})

        if "groups" in data:
            groups = data.get("groups", [])
            lines = [
                f"Distribución de **{total} empleados** por {data.get('group_by', 'categoría')}:"
            ]
            lines.extend(
                f"- {group.get('categoria')}: {group.get('cantidad')} "
                f"({group.get('porcentaje')}%)"
                for group in groups
                if isinstance(group, dict)
            )
            return "\n".join(lines)

        if "mediana" in data:
            if not total:
                return "No se encontraron empleados para calcular estadísticas salariales."
            return "\n".join(
                [
                    f"Estadísticas salariales sobre **{total} empleados**:",
                    f"- Promedio: ${data.get('promedio', 0):,.2f}",
                    f"- Mediana: ${data.get('mediana', 0):,.2f}",
                    f"- Mínimo: ${data.get('minimo', 0):,.2f}",
                    f"- Máximo: ${data.get('maximo', 0):,.2f}",
                    f"- Suma: ${data.get('suma', 0):,.2f}",
                ]
            )
        
        lines = []
        
        if total > 0:
            lines.append(f"📊 Total de registros encontrados: **{total}**")
        else:
            return "No se encontraron resultados para la consulta."

        if _is_count_query(user_text):
            normalized_user_text = _normalize_text(user_text)
            if "desarrollador" in normalized_user_text:
                return f"Hay **{total} empleados desarrolladores**."
            return f"Hay **{total} empleados** registrados en total."
        
        if stats:
            if "total_sueldos" in stats:
                lines.append(f"💰 Suma total de sueldos: ${stats['total_sueldos']:,.0f} ARS")
                lines.append(f"📈 Promedio de sueldo: ${stats['promedio_sueldo']:,.0f} ARS")
            if "total_ingresos" in stats:
                lines.append(f"💰 Ingresos totales: ${stats['total_ingresos']:,.0f} ARS")
                lines.append(f"📈 Promedio de ingreso: ${stats['promedio_ingreso']:,.0f} ARS")
        
        if sample:
            lines.append(f"\n📋 **Muestra de {len(sample)} registros:**")
            
            normalized_user_text = _normalize_text(user_text)
            only_names = any(token in normalized_user_text for token in ("nombre", "nombres"))
            
            for row in sample:
                if isinstance(row, dict):
                    if only_names:
                        name_parts = [
                            str(row.get(key, "")).strip()
                            for key in ("Nombre", "Apellido", "Nombre_Responsable", "Apellido_Responsable")
                            if row.get(key)
                        ]
                        if name_parts:
                            lines.append("- " + " ".join(name_parts))
                            continue
                    
                    clean_items = [
                        f"{key}: {value}"
                        for key, value in row.items()
                        if value is not None and not str(key).startswith("Unnamed")
                    ]
                    lines.append("- " + " | ".join(clean_items[:5]))
                else:
                    lines.append(f"- {row}")
        
        if total > len(sample):
            lines.append(f"\n💡 ... y {total - len(sample)} registro(s) más.")
        
        return "\n".join(lines)

    return safe_json(data)


def _last_human_text(messages: List[BaseMessage]) -> str:
    for message in reversed(messages):
        if getattr(message, "type", None) == "human":
            return str(getattr(message, "content", "") or "")
    return ""


def _normalize_text(text: str) -> str:
    replacements = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")
    return text.translate(replacements).lower()


def _is_policy_infrastructure_query(text: str) -> bool:
    normalized = _normalize_text(text)
    requests_policy = (
        "politica" in normalized
        and "base" in normalized
        and "dato" in normalized
    )
    return requests_policy and "infraestructura" in normalized


def _is_database_policy_query(text: str) -> bool:
    normalized = _normalize_text(text)
    return (
        any(term in normalized for term in ("normativa", "politica"))
        and "base" in normalized
        and "dato" in normalized
    )


def _format_database_policy_result(tool_messages: List[ToolMessage]) -> str:
    """Convierte el contexto RAG de normativa en una respuesta final trazable."""
    rag_contents = [
        str(message.content or "")
        for message in tool_messages
        if str(message.content or "").startswith("# Contexto recuperado")
        or message.tool_call_id in {"direct_rag_policy", "text_tool_call"}
    ]
    context = "\n".join(rag_contents)
    if not context.strip():
        return "No se encontró normativa relevante sobre acceso a bases de datos."

    controls = []
    for line in context.splitlines():
        clean_line = line.strip()
        if clean_line.startswith("- ") or re.match(r"^\d+\.\s+", clean_line):
            if clean_line not in controls:
                controls.append(clean_line)
        if len(controls) == 8:
            break

    sources = []
    for match in re.findall(r"^Fuente:\s*(.+)$", context, flags=re.MULTILINE):
        source = match.strip()
        if source and source not in sources:
            sources.append(source)

    lines = [
        "La normativa establece que el acceso seguro a bases de datos debe:",
        *controls,
    ]
    if sources:
        lines.extend(["", "Fuentes: " + ", ".join(f"`{source}`" for source in sources) + "."])
    return "\n".join(lines)


def _format_policy_infrastructure_result(
    tool_messages: List[ToolMessage],
) -> str:
    """Combina política RAG y empleados MCP sin depender del texto del LLM."""
    policy_text = ""
    employee_payload: Dict[str, Any] | None = None

    for message in tool_messages:
        content = str(message.content or "")
        if message.tool_call_id == "direct_rag_policy":
            policy_text = content
        elif message.tool_call_id == "direct_infra_employees":
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                employee_payload = parsed

    policy_points = [
        line.strip()
        for line in policy_text.splitlines()
        if line.strip().startswith(("- ", "1. ", "2. ", "3. ", "4. ", "5. "))
    ][:5]

    data = (
        employee_payload.get("data", {})
        if isinstance(employee_payload, dict)
        else {}
    )
    total = int(data.get("total", 0)) if isinstance(data, dict) else 0
    sample = data.get("sample", []) if isinstance(data, dict) else []

    lines = [
        "La política exige autorización explícita, consultas limitadas al mínimo "
        "necesario, validación de entradas y auditoría de los accesos administrativos.",
        "",
        f"En el área de **Infraestructura hay {total} empleados**:",
    ]
    for row in sample:
        if not isinstance(row, dict):
            continue
        full_name = " ".join(
            str(row.get(key, "")).strip() for key in ("Nombre", "Apellido")
        ).strip()
        lines.append(f"- {full_name}: {row.get('Puesto', 'Puesto no informado')}")

    if policy_points:
        lines.extend(["", "Controles relevantes de la política:", *policy_points])

    lines.extend(
        [
            "",
            "Aplicación conjunta: el Administrador puede consultar estos registros, "
            "pero debe limitar la exposición a los campos necesarios, registrar la "
            "consulta y proteger datos sensibles como DNI y salarios.",
            "",
            "Fuente: `normativa_acceso_bases_datos.md` y base MCP de empleados.",
        ]
    )
    return "\n".join(lines)


def _direct_tool_call_for_structured_query(
    messages: List[BaseMessage],
    tools: List[Any],
) -> Dict[str, Any] | List[Dict[str, Any]] | None:
    """Route obvious MCP list queries without relying on model tool selection."""
    user_text = _normalize_text(_last_human_text(messages))
    tool_names = {tool_obj.name for tool_obj in tools}

    filters: Dict[str, Any] = {}
    if "infraestructura" in user_text:
        filters["area"] = "Infraestructura"
    elif "desarrollo" in user_text and "desarrollador" not in user_text:
        filters["area"] = "Desarrollo"
    if "desarrollador" in user_text:
        filters["puesto"] = "Developer"

    if _is_policy_infrastructure_query(user_text):
        employee_tool = next(
            (
                name
                for name in (
                    "consultar_empleados_mcp_administrador",
                    "consultar_empleados_mcp_empleado",
                )
                if name in tool_names
            ),
            None,
        )
        if "rag_retrieve_context" in tool_names and employee_tool:
            return [
                {
                    "name": "rag_retrieve_context",
                    "args": {"query": _last_human_text(messages), "top_k": 2},
                    "id": "direct_rag_policy",
                },
                {
                    "name": employee_tool,
                    "args": {"area": "Infraestructura"},
                    "id": "direct_infra_employees",
                },
            ]

    if _is_database_policy_query(user_text) and "rag_retrieve_context" in tool_names:
        return {
            "name": "rag_retrieve_context",
            "args": {"query": _last_human_text(messages), "top_k": 2},
            "id": "direct_rag_policy",
        }

    salary_terms = ("salario", "sueldo", "mediana salarial", "estadistica salarial")
    if any(term in user_text for term in salary_terms):
        if "estadisticas_salariales_mcp_administrador" in tool_names:
            return {
                "name": "estadisticas_salariales_mcp_administrador",
                "args": filters,
                "id": "direct_salary_statistics",
            }

    if any(term in user_text for term in ("distribucion", "distribui", "porcentaje")):
        distribution_tool = next(
            (
                name
                for name in (
                    "distribucion_empleados_mcp_administrador",
                    "distribucion_empleados_mcp_empleado",
                )
                if name in tool_names
            ),
            None,
        )
        if distribution_tool:
            group_by = "puesto" if "puesto" in user_text else "area"
            return {
                "name": distribution_tool,
                "args": {"group_by": group_by, **filters},
                "id": "direct_employee_distribution",
            }

    asks_for_list = any(
        token in user_text
        for token in ("listado", "lista", "listar", "todos", "todas", "mostrar", "dame")
    )

    if "empleado" in user_text:
        preferred_tools = (
            (
                "contar_empleados_mcp_administrador",
                "contar_empleados_mcp_empleado",
            )
            if _is_count_query(user_text)
            else (
                "consultar_empleados_mcp_administrador",
                "consultar_empleados_mcp_empleado",
            )
        )
        employee_tool = next(
            (
                name
                for name in preferred_tools
                if name in tool_names
            ),
            None,
        )
        if employee_tool is None and _is_count_query(user_text):
            employee_tool = next(
                (
                    name
                    for name in (
                        "consultar_empleados_mcp_administrador",
                        "consultar_empleados_mcp_empleado",
                    )
                    if name in tool_names
                ),
                None,
            )
        if employee_tool:
            return {
                "name": employee_tool,
                "args": filters,
                "id": "direct_empleados_query",
            }
        return {
            "name": "",
            "error": (
                "No tenes permisos para consultar empleados con el rol actual. "
                "Este rol no tiene acceso a la base de empleados."
            ),
        }

    if "cliente" in user_text and asks_for_list:
        return {
            "name": "",
            "error": "La base SQLite disponible contiene únicamente empleados.",
        }

    return None


def invoke_specialist_agent(
    *,
    system_prompt: str,
    messages: List[BaseMessage],
    tools: List[Any] | None = None,
) -> Dict[str, List[BaseMessage]]:
    """Run one specialist agent - EL LLM SIEMPRE TIENE LA ÚLTIMA PALABRA."""

    # ──────────────────────────────────────────────────────────
    # 1. PREPARAR EL MODELO
    # ──────────────────────────────────────────────────────────
    model = build_chat_model()
    prepared_messages: List[BaseMessage] = [SystemMessage(content=system_prompt)] + list(messages)

    bound_model = model
    if tools:
        try:
            bound_model = model.bind_tools(tools)
            logger.info(f"🔧 Herramientas bindeadas: {[t.name for t in tools]}")
        except Exception as exc:
            logger.warning("bind_tools no disponible: %s", exc)
            bound_model = model

    # ──────────────────────────────────────────────────────────
    # 2. PRIMERA INVOCACIÓN: LLM decide qué hacer
    # ──────────────────────────────────────────────────────────
    logger.info("🤖 LLM decide qué acción tomar...")
    first_ai = _invoke_with_fallback(bound_model, prepared_messages, tools)
    new_messages: List[BaseMessage] = [first_ai]

    # ──────────────────────────────────────────────────────────
    # 3. EXTRAER TOOL CALLS
    # ──────────────────────────────────────────────────────────
    tool_calls = getattr(first_ai, "tool_calls", None) or []
    
    if not tool_calls:
        content = getattr(first_ai, "content", "")
        tool_calls = _tool_calls_from_text(content)
        
        if tool_calls and isinstance(content, str):
            clean_content = _clean_tool_tags(content)
            if clean_content and clean_content != content:
                first_ai.content = clean_content
                new_messages[0] = first_ai

    # Las consultas estructuradas autorizadas no pueden depender de que el LLM
    # decida voluntariamente usar MCP. Si respondió sin herramienta, el runtime
    # aplica la política y genera la llamada obligatoria.
    if not tool_calls and tools:
        direct_call = _direct_tool_call_for_structured_query(messages, tools)
        if direct_call:
            if isinstance(direct_call, dict) and direct_call.get("error"):
                return {
                    "messages": [
                        AIMessage(content=str(direct_call["error"]))
                    ]
                }
            tool_calls = (
                direct_call if isinstance(direct_call, list) else [direct_call]
            )
            first_ai = AIMessage(content="", tool_calls=tool_calls)
            new_messages[0] = first_ai
            logger.info(
                "Consulta estructurada: uso de MCP forzado por política (%s)",
                ", ".join(call["name"] for call in tool_calls),
            )

    # ──────────────────────────────────────────────────────────
    # 4. SI NO HAY TOOL CALLS: El LLM ya respondió directamente
    # ──────────────────────────────────────────────────────────
    if not tool_calls:
        logger.info("💬 LLM respondió directamente (sin herramientas)")
        return {"messages": new_messages}

    # ──────────────────────────────────────────────────────────
    # 5. EJECUTAR HERRAMIENTAS
    # ──────────────────────────────────────────────────────────
    logger.info(f"🔧 Ejecutando {len(tool_calls)} herramienta(s)...")
    
    tool_map = {tool_obj.name: tool_obj for tool_obj in tools}
    tool_messages: List[ToolMessage] = []

    for call in tool_calls:
        call_name = call.get("name") if isinstance(call, dict) else getattr(call, "name", "")
        call_args = call.get("args") if isinstance(call, dict) else getattr(call, "args", {})
        call_id = call.get("id") if isinstance(call, dict) else getattr(call, "id", None)

        tool_obj = tool_map.get(call_name)
        if tool_obj is None:
            tool_messages.append(
                ToolMessage(
                    content=safe_json({"error": f"Tool no permitida: {call_name}"}),
                    tool_call_id=str(call_id or "unknown"),
                )
            )
            continue

        try:
            logger.info(f"⚙️ Ejecutando: {call_name} con args: {call_args}")
            result = tool_obj.invoke(call_args or {})
        except Exception as exc:
            result = safe_json({"error": f"Error ejecutando tool {call_name}: {exc}"})

        result_content = result if isinstance(result, str) else safe_json(result)
        result_content = _truncate_tool_result_if_needed(result_content)

        tool_messages.append(
            ToolMessage(
                content=result_content,
                tool_call_id=str(call_id or "unknown"),
            )
        )

    # ──────────────────────────────────────────────────────────
    # 6. 🎯 SEGUNDA INVOCACIÓN: EL LLM GENERA LA RESPUESTA FINAL
    # ──────────────────────────────────────────────────────────
    if tool_messages:
        new_messages.extend(tool_messages)
        
        full_messages = prepared_messages + [first_ai] + tool_messages
        
        logger.info("🤖 LLM generando respuesta final con resultados...")
        
        final_ai = _invoke_with_fallback(bound_model, full_messages, tools)
        
        # ─── VERIFICAR SI EL LLM GENERÓ OTRO TOOL CALL ───
        final_content = getattr(final_ai, "content", "") or ""
        final_tool_calls = getattr(final_ai, "tool_calls", None) or []
        
        if _is_policy_infrastructure_query(_last_human_text(messages)):
            final_ai = AIMessage(
                content=_format_policy_infrastructure_result(tool_messages)
            )
            logger.info("Consulta compuesta: respuesta determinista desde RAG y MCP")
        elif _is_database_policy_query(_last_human_text(messages)):
            final_ai = AIMessage(
                content=_format_database_policy_result(tool_messages)
            )
            logger.info("Consulta normativa: respuesta determinista desde RAG")
        elif any(
            message.tool_call_id
            in {"direct_employee_distribution", "direct_salary_statistics"}
            for message in tool_messages
        ):
            final_ai = AIMessage(
                content=_format_tool_result_for_user(
                    tool_messages,
                    user_text=_last_human_text(messages),
                )
            )
            logger.info("Analítica estructurada: respuesta determinista desde MCP")
        elif _is_count_query(_last_human_text(messages)):
            final_ai = AIMessage(
                content=_format_tool_result_for_user(
                    tool_messages,
                    user_text=_last_human_text(messages),
                )
            )
            logger.info("Conteo estructurado: respuesta determinista desde MCP")
        elif final_tool_calls:
            logger.warning("⚠️ El LLM generó otro tool call nativo, forzando fallback")
            fallback_content = _format_tool_result_for_user(
                tool_messages,
                user_text=_last_human_text(messages),
            )
            final_ai = AIMessage(content=fallback_content)
        elif _looks_like_text_tool_call(final_content):
            logger.warning("⚠️ El LLM generó tool call en texto, forzando fallback")
            fallback_content = _format_tool_result_for_user(
                tool_messages,
                user_text=_last_human_text(messages),
            )
            final_ai = AIMessage(content=fallback_content)
        elif not final_content.strip():
            logger.warning("⚠️ El LLM no generó contenido, usando fallback")
            fallback_content = _format_tool_result_for_user(
                tool_messages,
                user_text=_last_human_text(messages),
            )
            final_ai = AIMessage(content=fallback_content)
        else:
            logger.info(f"✅ LLM generó respuesta válida: {final_content[:100]}...")
        
        new_messages.append(final_ai)
    
    # ──────────────────────────────────────────────────────────
    # 🛡️ GARANTIZAR RESPUESTA VÁLIDA
    # ──────────────────────────────────────────────────────────
    new_messages = _ensure_valid_response(
        new_messages,
        fallback_content="He procesado tu consulta."
    )

    # ──────────────────────────────────────────────────────────
    # ✅ LOG FINAL PARA DEPURACIÓN
    # ──────────────────────────────────────────────────────────
    if new_messages:
        last_msg = new_messages[-1]
        if isinstance(last_msg, AIMessage):
            content = getattr(last_msg, "content", "") or ""
            logger.info(f"📤 Mensaje final: {content[:200]}..." if len(content) > 200 else f"📤 Mensaje final: {content}")
        else:
            logger.warning(f"⚠️ El último mensaje no es AIMessage: {type(last_msg).__name__}")

    return {"messages": new_messages}
