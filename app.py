"""
app.py
------
Interfaz principal de "Ciudad Analítica" con Streamlit.
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

from agent_system.constants import (
    AGENT_MANAGER,
    DEFAULT_AGENT,
    DEFAULT_ROLE,
    ROLE_ADMIN,
    ROLE_INVITADO,
    ROLE_SOPORTE,
    ROLE_TO_AGENT,
)

# ---------------------------------------------------------------------
# Configuración de logging
# ---------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ciudad_analitica.app")

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
logger.info(f"  LANGSMITH_API_KEY: {os.environ.get('LANGSMITH_API_KEY')[:20] if os.environ.get('LANGSMITH_API_KEY') else 'NO DEFINIDA'}...")
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
    page_title="Ciudad Analítica",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------
# Rutas solicitadas por el enunciado.
# ---------------------------------------------------------------------
LOGO_PATH = Path(os.getenv("LOGO_PATH", "logo.jpg"))

ROLE_OPTIONS = {
    "Invitado (Público)": ROLE_INVITADO,
    "Soporte_Nivel_1 (Técnico)": ROLE_SOPORTE,
    "Admin_Nivel_2 (Administrador)": ROLE_ADMIN,
}

ROLE_PERMISSIONS = {
    ROLE_INVITADO: {
        "Clientes": "Bloqueada",
        "Empleados": "Bloqueada",
        "RAG": "Bloqueado",
        "badge": "🟡 Invitado",
    },
    ROLE_SOPORTE: {
        "Clientes": "Solo datos públicos",
        "Empleados": "Bloqueado",
        "RAG": "Habilitado",
        "badge": "🟠 Soporte Nivel 1",
    },
    ROLE_ADMIN: {
        "Clientes": "Acceso Total",
        "Empleados": "Acceso Total",
        "RAG": "Habilitado",
        "badge": "🟢 Admin Nivel 2",
    },
}

PUBLIC_SERVICES = [
    "Migración e Infraestructura Cloud",
    "Implementación de Data Pipelines",
    "Auditoría de Ciberseguridad",
]


# ---------------------------------------------------------------------
# Estado inicial de la app.
# ---------------------------------------------------------------------
def init_session_state() -> None:
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "audit_log" not in st.session_state:
        st.session_state.audit_log = []
    if "selected_role_label" not in st.session_state:
        st.session_state.selected_role_label = "Invitado (Público)"
    if "langsmith_enabled" not in st.session_state:
        st.session_state.langsmith_enabled = os.getenv("LANGSMITH_TRACING", "true").lower() == "true"


def role_to_internal(role_label: str) -> str:
    return ROLE_OPTIONS.get(role_label, DEFAULT_ROLE)


def internal_to_node(role: str) -> str:
    return ROLE_TO_AGENT.get(role, DEFAULT_AGENT)


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


def render_sidebar() -> str:
    st.sidebar.title("Ciudad Analítica")
    render_logo()

    st.sidebar.subheader("Iniciar Sesión como:")
    selected_label = st.sidebar.selectbox(
        "Iniciar Sesión como:",
        list(ROLE_OPTIONS.keys()),
        index=list(ROLE_OPTIONS.keys()).index(st.session_state.selected_role_label)
        if st.session_state.selected_role_label in ROLE_OPTIONS
        else 0,
        key="role_selector",
    )

    st.session_state.selected_role_label = selected_label
    role = role_to_internal(selected_label)

    st.sidebar.markdown("### 🔐 Observabilidad de permisos")
    perms = ROLE_PERMISSIONS[role]

    st.sidebar.info(
        f"**Rol actual:** {perms['badge']}\n\n"
        f"**Clientes:** {perms['Clientes']}\n\n"
        f"**Empleados:** {perms['Empleados']}\n\n"
        f"**RAG:** {perms['RAG']}"
    )

    st.sidebar.caption(
        "La interfaz cambia según el rol, pero la política real se aplica también en MCP y en el grafo."
    )

    st.sidebar.divider()
    st.sidebar.markdown("### 📊 LangSmith")
    if st.session_state.langsmith_enabled:
        project = os.getenv("LANGSMITH_PROJECT", "proyecto_coder")
        st.sidebar.success(f"✅ Trazabilidad activa\n\nProyecto: `{project}`")
        st.sidebar.caption("Ver en: https://smith.langchain.com")
    else:
        st.sidebar.warning("⚠️ LangSmith desactivado")

    return role


def render_header(role: str) -> None:
    st.title("🏢 Ciudad Analítica - Centro de Operaciones IA")
    st.write(
        "Una simulación educativa para ver cómo un agente cambia su comportamiento "
        "según el nivel de acceso, usando RAG, MCP y LangGraph."
    )

    if role == ROLE_INVITADO:
        st.markdown("### Servicios principales")
        cols = st.columns(3)
        for col, service in zip(cols, PUBLIC_SERVICES):
            with col:
                st.info(service)


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
        "input_usuario": user_text,
        "respuesta_asistente": ai_text,
        "tool_traces": tool_traces,
    }
    st.session_state.audit_log.append(entry)


def render_chat_history() -> None:
    for item in st.session_state.chat_history:
        with st.chat_message(item["role"]):
            st.markdown(item["content"])


def render_audit_panel() -> None:
    with st.expander("🛠️ Auditoría de Procesamiento MCP / RAG", expanded=False):
        if not st.session_state.audit_log:
            st.info("Todavía no hay trazas. Envía un mensaje para ver el recorrido completo.")
            return

        last = st.session_state.audit_log[-1]
        st.markdown(f"**Rol:** `{last['rol_usuario']}`")
        st.markdown(f"**Agente encargado:** `{last.get('agente_encargado', AGENT_MANAGER)}`")
        st.markdown(f"**Nodo LangGraph ejecutado:** `{last['nodo_ejecutado']}`")
        st.markdown(f"**Motivo de designacion:** {last.get('motivo_designacion', 'No informado.')}")

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


def invoke_graph(user_input: str, role: str) -> Dict[str, Any]:
    """
    Llama al grafo con el estado mínimo solicitado por el módulo.
    Usa el método más confiable para LangSmith: tracer manual con callbacks.
    """
    if app_graph is None:
        raise RuntimeError(
            f"No se pudo importar el grafo de agentes: {AGENTS_IMPORT_ERROR}"
        )

    # Configuración de entrada
    input_state = {
        "messages": [HumanMessage(content=user_input)],
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
    logger = logging.getLogger("ciudad_analitica.app")

    init_session_state()
    role = render_sidebar()
    render_header(role)

    if app_graph is None:
        st.error(
            "No se pudo cargar el grafo de agentes. "
            "Revisá la configuración del LLM y las dependencias."
        )
        with st.expander("Detalle técnico", expanded=False):
            st.exception(AGENTS_IMPORT_ERROR)
        return

    render_chat_history()

    user_input = st.chat_input("Escribí tu consulta para Ciudad Analítica...")

    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        try:
            with st.spinner("Procesando con LangGraph, RAG y MCP..."):
                result_state = invoke_graph(user_input=user_input, role=role)

            messages = result_state.get("messages", []) if isinstance(result_state, dict) else []
            assistant_text = _extract_last_ai_message(messages)
            tool_traces = _extract_tool_traces(messages)

            if not assistant_text:
                assistant_text = (
                    "No se pudo recuperar una respuesta textual del grafo, "
                    "pero la interacción fue procesada."
                )

            st.session_state.chat_history.append(
                {"role": "assistant", "content": assistant_text}
            )
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
            st.session_state.chat_history.append({"role": "assistant", "content": error_text})
            st.session_state.audit_log.append(
                {
                    "rol_usuario": role,
                    "nodo_ejecutado": internal_to_node(role),
                    "agente_encargado": AGENT_MANAGER,
                    "motivo_designacion": "La ejecucion fallo antes de completar la designacion.",
                    "input_usuario": user_input,
                    "respuesta_asistente": error_text,
                    "tool_traces": [
                        {
                            "status_code": 500,
                            "status": "error",
                            "message": str(exc),
                        }
                    ],
                }
            )
            st.error(error_text)

    render_audit_panel()


if __name__ == "__main__":
    main()