"""
app.py
------
Interfaz principal de "Agente Corporativo IA" con Streamlit.
"""

from __future__ import annotations

import json
import os
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from data_access.query_history import load_query_history, save_query_record

from agent_system.constants import (
    AGENT_MANAGER,
    DEFAULT_AGENT,
    DEFAULT_ROLE,
    ROLE_ADMINISTRADOR,
    ROLE_EMPLEADO,
    ROLE_INVITADO,
    ROLE_TO_AGENT,
)

# ---------------------------------------------------------------------
# Configuración de logging
# ---------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agente_corporativo.app")

# ---------------------------------------------------------------------
# Carga de variables de entorno.
# ---------------------------------------------------------------------
load_dotenv()

# ---------------------------------------------------------------------
# 🔥 CONFIGURACIÓN EXPLÍCITA DE LANGSMITH - FORZADA
# ---------------------------------------------------------------------
# Leer variables del .env
langsmith_api_key = os.getenv("LANGSMITH_API_KEY", "")
langsmith_project = os.getenv("LANGSMITH_PROJECT", "proyecto_coder")
langsmith_tracing = os.getenv("LANGSMITH_TRACING", "true")

# FORZAR las variables de entorno para LangChain/LangGraph
os.environ["LANGSMITH_TRACING"] = langsmith_tracing
os.environ["LANGSMITH_API_KEY"] = langsmith_api_key
os.environ["LANGSMITH_PROJECT"] = langsmith_project

# También forzar la variable específica que usa el cliente
os.environ["LANGCHAIN_TRACING_V2"] = langsmith_tracing
os.environ["LANGCHAIN_API_KEY"] = langsmith_api_key
os.environ["LANGCHAIN_PROJECT"] = langsmith_project

logger.info("=" * 60)
logger.info("🔍 CONFIGURACIÓN DE LANGSMITH")
logger.info(f"  LANGSMITH_TRACING: {os.environ.get('LANGSMITH_TRACING')}")
logger.info(
    "  LANGSMITH_API_KEY: %s",
    "CONFIGURADA" if os.environ.get("LANGSMITH_API_KEY") else "NO DEFINIDA",
)
logger.info(f"  LANGSMITH_PROJECT: {os.environ.get('LANGSMITH_PROJECT')}")
logger.info(f"  LANGCHAIN_TRACING_V2: {os.environ.get('LANGCHAIN_TRACING_V2')}")
logger.info("=" * 60)

# ---------------------------------------------------------------------
# Inyección explícita del token en variables de entorno globales.
# ---------------------------------------------------------------------
token = os.getenv("HUGGINGFACEHUB_API_TOKEN")
if token:
    os.environ["HF_TOKEN"] = token
    os.environ["HUGGINGFACEHUB_API_TOKEN"] = token

# ---------------------------------------------------------------------
# Importación del grafo de agentes después de cargar el entorno.
# ---------------------------------------------------------------------
try:
    from agents import app_graph
except Exception as exc:
    app_graph = None
    AGENTS_IMPORT_ERROR = exc
    logger.error(f"Error importando app_graph: {exc}")
else:
    AGENTS_IMPORT_ERROR = None
    logger.info("✅ app_graph importado correctamente")

# ---------------------------------------------------------------------
# Configuración de página.
# ---------------------------------------------------------------------
st.set_page_config(
    page_title="Agente Corporativo IA",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------
# Rutas solicitadas por el enunciado.
# ---------------------------------------------------------------------
LOGO_PATH = Path(os.getenv("LOGO_PATH", "logo.jpg"))

ROLE_OPTIONS = {
    "Invitado": ROLE_INVITADO,
    "Empleado": ROLE_EMPLEADO,
    "Administrador": ROLE_ADMINISTRADOR,
}

ROLE_PERMISSIONS = {
    ROLE_INVITADO: {
        "Manuales simples": "Habilitado",
        "Manuales complejos": "Bloqueado",
        "SQLite empleados": "Bloqueado",
        "badge": "🟡 Invitado",
    },
    ROLE_EMPLEADO: {
        "Manuales simples": "Habilitado",
        "Manuales complejos": "Habilitado",
        "SQLite empleados": "Sin salarios",
        "badge": "🟠 Empleado",
    },
    ROLE_ADMINISTRADOR: {
        "Manuales simples": "Habilitado",
        "Manuales complejos": "Habilitado",
        "SQLite empleados": "Acceso completo",
        "badge": "🟢 Administrador",
    },
}

SIMPLE_MANUAL_TOPICS = [
    "Registro y verificación de cuenta",
    "Recuperación de contraseña",
    "Contacto y recomendaciones de seguridad",
]


# ---------------------------------------------------------------------
# Estado inicial de la app.
# ---------------------------------------------------------------------
def init_session_state() -> None:
    if "chat_history_by_role" not in st.session_state:
        st.session_state.chat_history_by_role = {}
    if "audit_log_by_role" not in st.session_state:
        st.session_state.audit_log_by_role = {}
    if "loaded_history_roles" not in st.session_state:
        st.session_state.loaded_history_roles = set()
    if "selected_role_label" not in st.session_state:
        st.session_state.selected_role_label = "Invitado"
    if "langsmith_enabled" not in st.session_state:
        st.session_state.langsmith_enabled = os.getenv("LANGSMITH_TRACING", "true").lower() == "true"


def role_to_internal(role_label: str) -> str:
    return ROLE_OPTIONS.get(role_label, DEFAULT_ROLE)


def internal_to_node(role: str) -> str:
    return ROLE_TO_AGENT.get(role, DEFAULT_AGENT)


def ensure_role_history_loaded(role: str) -> None:
    """Carga desde SQLite únicamente el historial del rol activo."""
    if role in st.session_state.loaded_history_roles:
        return

    records = load_query_history(role)
    chat_history: List[Dict[str, str]] = []
    audit_log: List[Dict[str, Any]] = []
    for record in records:
        chat_history.extend(
            [
                {"role": "user", "content": record["user_query"]},
                {"role": "assistant", "content": record["assistant_response"]},
            ]
        )
        audit_log.append(
            {
                "record_id": record["id"],
                "created_at": record["created_at"],
                "rol_usuario": record["role"],
                "nodo_ejecutado": record["agent_name"],
                "agente_encargado": AGENT_MANAGER,
                "motivo_designacion": record["designation_reason"],
                "cycle_count": record["cycle_count"],
                "evaluation_decision": record["evaluation_decision"],
                "evaluation_reason": record["evaluation_reason"],
                "input_usuario": record["user_query"],
                "respuesta_asistente": record["assistant_response"],
                "tool_traces": record["tool_traces"],
            }
        )

    st.session_state.chat_history_by_role[role] = chat_history
    st.session_state.audit_log_by_role[role] = audit_log
    st.session_state.loaded_history_roles.add(role)


def role_chat_history(role: str) -> List[Dict[str, str]]:
    ensure_role_history_loaded(role)
    return st.session_state.chat_history_by_role[role]


def role_audit_log(role: str) -> List[Dict[str, Any]]:
    ensure_role_history_loaded(role)
    return st.session_state.audit_log_by_role[role]


def safe_json_loads(value: Any) -> Optional[Any]:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return None
    try:
        return json.loads(value)
    except Exception:
        return None


def render_logo() -> None:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)
    else:
        st.warning(
            "No se encontró el logo corporativo en la ruta indicada. "
            "Se continúa con una interfaz estándar para no interrumpir la demo."
        )


def render_topbar() -> str:
    """Renderiza una cabecera horizontal compacta y siempre visible."""
    st.markdown(
        """
        <style>
        .st-key-agent_topbar {
            position: fixed;
            top: 2.5rem;
            left: 50%;
            transform: translateX(-50%);
            width: min(calc(100vw - 2rem), 1380px);
            z-index: 1000001;
            background: Canvas;
            color: CanvasText;
            border: 1px solid rgba(128, 128, 128, 0.28);
            border-radius: 0.65rem;
            box-shadow: 0 0.2rem 0.8rem rgba(0, 0, 0, 0.12);
            backdrop-filter: blur(12px);
            padding: 0.35rem 0.75rem;
            overflow: hidden;
        }
        .st-key-agent_topbar [data-testid="stVerticalBlock"] {
            gap: 0.2rem;
        }
        .st-key-agent_topbar [data-testid="stHorizontalBlock"] {
            gap: 0.75rem;
            align-items: center;
            flex-wrap: nowrap;
        }
        .st-key-agent_topbar [data-testid="column"] {
            min-width: 0;
            overflow: hidden;
        }
        .st-key-agent_topbar h3,
        .st-key-agent_topbar h4 {
            margin: 0;
            padding: 0;
            font-size: 0.92rem;
            line-height: 1.15;
        }
        .st-key-agent_topbar [data-testid="stAlert"] {
            padding: 0.3rem 0.5rem;
            min-height: 0;
        }
        .st-key-agent_topbar [data-testid="stAlert"] p,
        .st-key-agent_topbar [data-testid="stCaptionContainer"],
        .st-key-agent_topbar label {
            font-size: 0.74rem;
            line-height: 1.1;
        }
        .st-key-agent_topbar p {
            margin-top: 0;
            margin-bottom: 0;
        }
        .st-key-agent_topbar [data-testid="stImage"] img {
            max-height: 38px;
            object-fit: contain;
        }
        .st-key-agent_topbar [data-baseweb="select"] > div {
            min-height: 1.9rem;
            font-size: 0.8rem;
        }
        .agent-topbar-spacer {
            height: 7.5rem;
        }
        .agent-brand-name {
            margin: 0;
            font-size: 0.88rem;
            font-weight: 700;
            line-height: 1.05;
            white-space: nowrap;
        }
        @media (max-width: 768px) {
            .st-key-agent_topbar {
                top: 0.5rem;
                width: calc(100vw - 1rem);
                max-height: 48vh;
                overflow-y: auto;
            }
            .agent-topbar-spacer {
                height: 11rem;
            }
            .agent-brand-name {
                white-space: normal;
                font-size: 0.72rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container(key="agent_topbar"):
        brand_column, status_column, role_column = st.columns(
            [1.45, 3.7, 1.65],
            vertical_alignment="center",
        )

        with brand_column:
            logo_column, name_column = st.columns(
                [0.42, 1.58],
                vertical_alignment="center",
            )
            with logo_column:
                if LOGO_PATH.exists():
                    st.image(str(LOGO_PATH), width=38)
                else:
                    st.markdown("🤖")
            with name_column:
                st.markdown(
                    '<p class="agent-brand-name">Agente Corporativo IA</p>',
                    unsafe_allow_html=True,
                )

        with role_column:
            selected_label = st.selectbox(
                "Rol de acceso",
                list(ROLE_OPTIONS.keys()),
                index=list(ROLE_OPTIONS.keys()).index(
                    st.session_state.selected_role_label
                )
                if st.session_state.selected_role_label in ROLE_OPTIONS
                else 0,
                key="role_selector",
                label_visibility="collapsed",
            )

        st.session_state.selected_role_label = selected_label
        role = role_to_internal(selected_label)
        perms = ROLE_PERMISSIONS[role]

        with status_column:
            trace_status = "activa" if st.session_state.langsmith_enabled else "inactiva"
            st.markdown(
                f"**🔐 {perms['badge']}** · Trazabilidad {trace_status}"
            )

        permission_columns = st.columns(3)
        permission_items = (
            ("📘 Manuales simples", perms["Manuales simples"]),
            ("📚 Manuales complejos", perms["Manuales complejos"]),
            ("🗃️ SQLite empleados", perms["SQLite empleados"]),
        )
        for column, (label, value) in zip(permission_columns, permission_items):
            with column:
                st.info(f"**{label}:** {value}")

    st.markdown(
        '<div class="agent-topbar-spacer" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    return role


def render_header(role: str) -> None:
    st.caption("Asistente corporativo con acceso controlado por rol")

    if role == ROLE_INVITADO:
        st.markdown("### Temas disponibles en los manuales simples")
        cols = st.columns(3)
        for col, topic in zip(cols, SIMPLE_MANUAL_TOPICS):
            with col:
                st.info(topic)


def _extract_last_ai_message(messages: List[BaseMessage]) -> str:
    """Extrae el contenido del último mensaje del asistente."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            return getattr(msg, "content", "") or ""
    return ""


def _extract_tool_traces(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
    traces: List[Dict[str, Any]] = []

    for msg in messages:
        if isinstance(msg, ToolMessage):
            payload = safe_json_loads(msg.content)
            trace_item: Dict[str, Any] = {
                "tool_call_id": getattr(msg, "tool_call_id", None),
                "raw_content": msg.content,
            }
            if isinstance(payload, dict):
                trace_item.update(payload)
            else:
                trace_item["parsed"] = payload
            traces.append(trace_item)

    return traces


def append_audit_entry(
    role: str,
    user_text: str,
    ai_text: str,
    tool_traces: List[Dict[str, Any]],
    result_state: Optional[Dict[str, Any]] = None,
) -> None:
    result_state = result_state or {}
    agente_designado = result_state.get("agente_designado") or internal_to_node(role)
    motivo_designacion = result_state.get("motivo_designacion") or "Designacion no informada por el grafo."
    entry = {
        "rol_usuario": role,
        "nodo_ejecutado": agente_designado,
        "agente_encargado": AGENT_MANAGER,
        "motivo_designacion": motivo_designacion,
        "cycle_count": int(result_state.get("cycle_count", 1)),
        "evaluation_decision": result_state.get("evaluation_decision", "end"),
        "evaluation_reason": result_state.get(
            "evaluation_reason",
            "Evaluación no informada por el grafo.",
        ),
        "input_usuario": user_text,
        "respuesta_asistente": ai_text,
        "tool_traces": tool_traces,
    }
    record_id = save_query_record(
        role=role,
        agent_name=agente_designado,
        user_query=user_text,
        assistant_response=ai_text,
        designation_reason=motivo_designacion,
        tool_traces=tool_traces,
        cycle_count=entry["cycle_count"],
        evaluation_decision=entry["evaluation_decision"],
        evaluation_reason=entry["evaluation_reason"],
    )
    entry["record_id"] = record_id
    role_audit_log(role).append(entry)


def render_chat_history(role: str) -> None:
    for item in role_chat_history(role):
        with st.chat_message(item["role"]):
            st.markdown(item["content"])


def render_audit_panel(role: str) -> None:
    audit_log = role_audit_log(role)
    with st.expander("🛠️ Auditoría de Procesamiento MCP / RAG", expanded=False):
        if not audit_log:
            st.info("Todavía no hay trazas. Envía un mensaje para ver el recorrido completo.")
            return

        last = audit_log[-1]
        st.markdown(f"**Rol:** `{last['rol_usuario']}`")
        st.markdown(f"**Agente encargado:** `{last.get('agente_encargado', AGENT_MANAGER)}`")
        st.markdown(f"**Nodo LangGraph ejecutado:** `{last['nodo_ejecutado']}`")
        st.markdown(f"**Motivo de designacion:** {last.get('motivo_designacion', 'No informado.')}")
        st.markdown(
            f"**Ciclos ejecutados:** `{last.get('cycle_count', 1)}` · "
            f"**Decisión:** `{last.get('evaluation_decision', 'end')}`"
        )
        st.markdown(
            f"**Evaluación:** {last.get('evaluation_reason', 'No informada.')}"
        )

        st.markdown("**Entrada del usuario:**")
        st.code(last["input_usuario"], language="text")

        st.markdown("**Salida del asistente:**")
        st.write(last["respuesta_asistente"] or "Sin respuesta textual disponible.")

        traces = last.get("tool_traces", [])
        if traces:
            st.markdown("**Trazas de herramientas / seguridad:**")
            for idx, trace in enumerate(traces, start=1):
                with st.container(border=True):
                    st.markdown(f"**Evento {idx}**")
                    status_code = trace.get("status_code")
                    status = trace.get("status")
                    message = trace.get("message")
                    if status_code is not None:
                        st.write(f"Estado: {status_code} - {status}")
                    if message:
                        st.write(f"Mensaje: {message}")
                    st.json(trace, expanded=False)
        else:
            st.caption("No se ejecutaron herramientas en esta interacción.")


# =====================================================================
# 🔥 FUNCIÓN QUE FUNCIONA SIEMPRE CON LANGSMITH
# =====================================================================
def get_langsmith_tracer():
    """Obtiene un tracer de LangSmith configurado con el proyecto actual."""
    try:
        from langchain.callbacks.tracers import LangChainTracer
        from langsmith import Client
    except ImportError as e:
        logger.warning(f"No se pudo importar LangSmith: {e}")
        return None
        
    langsmith_api_key = os.getenv("LANGSMITH_API_KEY", "")
    langsmith_project = os.getenv("LANGSMITH_PROJECT", "proyecto_coder")
    langsmith_tracing = os.getenv("LANGSMITH_TRACING", "true")
    
    if langsmith_tracing.lower() != "true":
        logger.info("LangSmith tracing está desactivado")
        return None
        
    if not langsmith_api_key:
        logger.warning("No se encontró LANGSMITH_API_KEY")
        return None
        
    try:
        # ✅ Crear el cliente y tracer
        client = Client(api_key=langsmith_api_key)
        tracer = LangChainTracer(
            project_name=langsmith_project,
            client=client
        )
        logger.info(f"✅ Tracer de LangSmith creado para proyecto: {langsmith_project}")
        return tracer
    except Exception as e:
        logger.warning(f"No se pudo crear tracer de LangSmith: {e}")
        return None


def invoke_graph(
    user_input: str,
    role: str,
    conversation_history: List[Dict[str, str]],
) -> Dict[str, Any]:
    """
    Llama al grafo con el estado mínimo solicitado por el módulo.
    Usa el método más confiable para LangSmith: tracer manual con callbacks.
    """
    if app_graph is None:
        raise RuntimeError(
            f"No se pudo importar el grafo de agentes: {AGENTS_IMPORT_ERROR}"
        )

    # Configuración de entrada
    contextual_messages: List[BaseMessage] = []
    for item in conversation_history[-20:]:
        content = str(item.get("content", ""))
        if item.get("role") == "user":
            contextual_messages.append(HumanMessage(content=content))
        elif item.get("role") == "assistant":
            contextual_messages.append(AIMessage(content=content))
    contextual_messages.append(HumanMessage(content=user_input))

    input_state = {
        "messages": contextual_messages,
        "rol_usuario": role,
    }

    # Verificar si LangSmith está activado
    langsmith_enabled = os.getenv("LANGSMITH_TRACING", "true").lower() == "true"
    project_name = os.getenv("LANGSMITH_PROJECT", "proyecto_coder")

    logger.info(f"📊 LangSmith activado: {langsmith_enabled}")
    logger.info(f"📊 Proyecto LangSmith: {project_name}")

    if langsmith_enabled:
        # ✅ Método más confiable: Tracer manual con callbacks
        tracer = get_langsmith_tracer()
        if tracer:
            logger.info(f"🚀 Ejecutando grafo con LangSmith tracer: {project_name}")
            
            # ✅ Importante: Pasar el tracer en la configuración
            result = app_graph.invoke(
                input_state,
                config={"callbacks": [tracer]}
            )
            
            messages = result.get("messages", [])
            logger.info(f"✅ Resultado del grafo: {len(messages)} mensajes procesados")
            logger.info(f"🔍 Revisa https://smith.langchain.com/projects/{project_name}")
            return result
        else:
            logger.warning("⚠️ No se pudo crear el tracer, ejecutando sin tracing")
            return app_graph.invoke(input_state)
    else:
        logger.info("⚠️ Ejecutando grafo sin LangSmith tracing")
        return app_graph.invoke(input_state)


def main() -> None:
    global logger
    logger = logging.getLogger("agente_corporativo.app")

    init_session_state()
    role = render_topbar()
    ensure_role_history_loaded(role)
    render_header(role)

    if app_graph is None:
        st.error(
            "No se pudo cargar el grafo de agentes. "
            "Revisá la configuración del LLM y las dependencias."
        )
        with st.expander("Detalle técnico", expanded=False):
            st.exception(AGENTS_IMPORT_ERROR)
        return

    render_chat_history(role)

    user_input = st.chat_input("Escribí tu consulta para el Agente Corporativo IA...")

    if user_input:
        chat_history = role_chat_history(role)
        previous_history = list(chat_history)
        chat_history.append({"role": "user", "content": user_input})

        try:
            with st.spinner("Procesando con LangGraph, RAG y MCP..."):
                result_state = invoke_graph(
                    user_input=user_input,
                    role=role,
                    conversation_history=previous_history,
                )

            messages = result_state.get("messages", []) if isinstance(result_state, dict) else []
            assistant_text = _extract_last_ai_message(messages)
            tool_traces = _extract_tool_traces(messages)

            if not assistant_text:
                assistant_text = (
                    "No se pudo recuperar una respuesta textual del grafo, "
                    "pero la interacción fue procesada."
                )

            chat_history.append({"role": "assistant", "content": assistant_text})
            append_audit_entry(role, user_input, assistant_text, tool_traces, result_state)

            if st.session_state.langsmith_enabled:
                project = os.getenv("LANGSMITH_PROJECT", "proyecto_coder")
                st.success(f"✅ Trazabilidad registrada en LangSmith: {project}")
                st.info(f"🔍 Ver en: https://smith.langchain.com/projects/{project}")

            st.rerun()

        except Exception as exc:
            error_text = (
                "Ocurrió un problema al procesar la solicitud. "
                "La interfaz sigue disponible para seguir trabajando."
            )
            chat_history.append({"role": "assistant", "content": error_text})
            append_audit_entry(
                role,
                user_input,
                error_text,
                [
                    {
                        "status_code": 500,
                        "status": "error",
                        "message": str(exc),
                    }
                ],
                {
                    "agente_designado": internal_to_node(role),
                    "motivo_designacion": (
                        "La ejecución falló antes de completar la designación."
                    ),
                },
            )
            st.error(error_text)

    render_audit_panel(role)


if __name__ == "__main__":
    main()
