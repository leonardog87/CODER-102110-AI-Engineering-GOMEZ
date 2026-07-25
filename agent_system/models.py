"""Chat model factory with local fallbacks."""

from __future__ import annotations

import logging
import os
import unicodedata
from functools import lru_cache, wraps
from typing import Any, Dict, List, Optional
from contextlib import contextmanager

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage

load_dotenv()

logger = logging.getLogger("ciudad_analitica.agent_system.models")

_token = os.getenv("HUGGINGFACEHUB_API_TOKEN") or os.getenv("HF_TOKEN")
if _token:
    os.environ["HF_TOKEN"] = _token
    os.environ["HUGGINGFACEHUB_API_TOKEN"] = _token


def get_langsmith_tracer():
    """Obtiene un tracer de LangSmith configurado con el proyecto actual."""
    try:
        from langchain.callbacks.tracers import LangChainTracer
        from langsmith import Client
    except ImportError:
        logger.warning("LangChainTracer o Client no están disponibles")
        return None
        
    langsmith_api_key: str = os.getenv("LANGSMITH_API_KEY", "")
    langsmith_project: str = os.getenv("LANGSMITH_PROJECT", "proyecto_coder")
    langsmith_tracing: str = os.getenv("LANGSMITH_TRACING", "true")
    
    if langsmith_tracing.lower() != "true":
        logger.info("LangSmith tracing está desactivado")
        return None
        
    if not langsmith_api_key:
        logger.warning("No se encontró LANGSMITH_API_KEY")
        return None
        
    try:
        client = Client(api_key=langsmith_api_key)
        tracer = LangChainTracer(
            project_name=langsmith_project,
            client=client
        )
        logger.info(f"Tracer de LangSmith creado para proyecto: {langsmith_project}")
        return tracer
    except Exception as e:
        logger.warning(f"No se pudo crear tracer de LangSmith: {e}")
        return None


@contextmanager
def langsmith_tracing(project_name: Optional[str] = None):
    """Context manager para habilitar tracing de LangSmith."""
    tracer = get_langsmith_tracer()
    if tracer:
        try:
            # Intentar usar el tracer directamente
            from langchain.callbacks.manager import CallbackManager
            # Creamos un manager con el tracer
            manager = CallbackManager([tracer])
            # Lo pasamos como contexto
            yield manager
        except Exception as e:
            logger.warning(f"Error en LangSmith tracing: {e}")
            yield None
    else:
        logger.info("LangSmith no disponible, ejecutando sin tracing")
        yield None


def with_langsmith_tracing(func):
    """Decorador para ejecutar funciones con tracing de LangSmith."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        tracer = get_langsmith_tracer()
        if tracer:
            # Si la función acepta config, agregamos el callback
            if "config" in kwargs:
                kwargs["config"] = kwargs.get("config", {})
                if "callbacks" not in kwargs["config"]:
                    kwargs["config"]["callbacks"] = []
                kwargs["config"]["callbacks"].append(tracer)
            else:
                # Si no, intentamos con run_manager
                try:
                    from langchain.callbacks.manager import CallbackManager
                    kwargs["callback_manager"] = CallbackManager([tracer])
                except ImportError:
                    pass
        return func(*args, **kwargs)
    return wrapper


@lru_cache(maxsize=1)
def build_chat_model():
    """Return the preferred chat model, falling back to an offline fake model."""

    # Configurar LangSmith primero
    langsmith_tracing = os.getenv("LANGSMITH_TRACING", "true")
    langsmith_api_key = os.getenv("LANGSMITH_API_KEY", "")
    langsmith_project = os.getenv("LANGSMITH_PROJECT", "proyecto_coder")

    # Activar el tracing de LangSmith
    if langsmith_tracing.lower() == "true" and langsmith_api_key:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = langsmith_project
        logger.info(f"LangSmith tracing activado para proyecto: {langsmith_project}")
    elif langsmith_tracing.lower() == "true" and not langsmith_api_key:
        logger.warning("LangSmith tracing activado pero no hay API key")
    else:
        logger.info("LangSmith tracing desactivado explícitamente")

    openai_api_base = os.getenv("OPENAI_API_BASE") or os.getenv("OPENAI_BASE_URL")
    openai_api_key = os.getenv("OPENAI_API_KEY")
    openai_model = os.getenv("OPENAI_MODEL", "qwen/qwen2.5-coder-14b")

    if openai_api_base:
        try:
            from langchain_openai import ChatOpenAI

            logger.info(f"Inicializando ChatOpenAI con modelo: {openai_model}")
            return ChatOpenAI(
                model=openai_model,
                api_key=openai_api_key or "not-needed",
                base_url=openai_api_base,
                temperature=0.1,
                timeout=60,
                max_retries=2,
            )
        except Exception as exc:
            logger.warning("No se pudo inicializar ChatOpenAI local: %s", exc)

    try:
        from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
    except Exception as exc:
        logger.warning("No se pudo importar langchain_huggingface: %s", exc)
        return fallback_chat_model()

    model_id = (
        os.getenv("HF_MODEL_ID")
        or os.getenv("CIUDAD_ANALITICA_HF_MODEL_ID")
        or openai_model
    )
    token = os.getenv("HUGGINGFACEHUB_API_TOKEN") or os.getenv("HF_TOKEN")

    if token:
        os.environ["HF_TOKEN"] = token
        os.environ["HUGGINGFACEHUB_API_TOKEN"] = token

    if not model_id:
        logger.warning("No se especificó modelo para HuggingFace")
        return fallback_chat_model()

    try:
        logger.info(f"Inicializando HuggingFaceEndpoint con modelo: {model_id}")
        endpoint_kwargs: Dict[str, Any] = {
            "repo_id": model_id,
            "task": "text-generation",
            "max_new_tokens": 512,
            "temperature": 0.1,
            "do_sample": False,
            "repetition_penalty": 1.03,
            "timeout": 60,
        }
        if token:
            endpoint_kwargs["huggingfacehub_api_token"] = token

        llm_endpoint = HuggingFaceEndpoint(**endpoint_kwargs)
        return ChatHuggingFace(llm=llm_endpoint)
    except Exception as exc:
        logger.warning("No se pudo inicializar HuggingFaceEndpoint: %s", exc)
        return fallback_chat_model()


class OfflineFallbackChatModel:
    """Small local model facade used when external providers are unavailable."""

    def __init__(self, tools: List[Any] | None = None):
        self.tools = tools or []

    def bind_tools(self, tools: List[Any]):
        """Bind tools to the model."""
        self.tools = tools or []
        return self

    def _available_tool_names(self) -> set[str]:
        """Get available tool names."""
        return {str(getattr(tool, "name", "")) for tool in self.tools}

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize text for better matching."""
        normalized = unicodedata.normalize("NFKD", text.lower())
        return "".join(char for char in normalized if not unicodedata.combining(char))

    def invoke(self, messages: List[BaseMessage]) -> AIMessage:
        """Invoke the fallback model with messages."""
        if any(getattr(message, "type", None) == "tool" for message in messages):
            return AIMessage(content="")

        user_text = ""
        for message in reversed(messages):
            if getattr(message, "type", None) == "human":
                user_text = str(getattr(message, "content", "") or "")
                break

        normalized_user_text = self._normalize(user_text)
        tool_names = self._available_tool_names()

        if "empleado" in normalized_user_text and "consultar_empleados_mcp_admin" in tool_names:
            return AIMessage(
                content=(
                    '{"name": "consultar_empleados_mcp_admin", '
                    '"arguments": {"empleado_id": null, "nombre": null, "area": null, "rol": null}}'
                )
            )

        if "cliente" in normalized_user_text:
            if "consultar_clientes_mcp_admin" in tool_names:
                return AIMessage(
                    content=(
                        '{"name": "consultar_clientes_mcp_admin", '
                        '"arguments": {"cliente_id": null, "nombre": null, "estado": null, "segmento": null}}'
                    )
                )
            if "consultar_clientes_mcp_soporte" in tool_names:
                return AIMessage(
                    content=(
                        '{"name": "consultar_clientes_mcp_soporte", '
                        '"arguments": {"cliente_id": null, "nombre": null, "estado": null, "segmento": null}}'
                    )
                )

        if "empleado" in normalized_user_text:
            return AIMessage(
                content=(
                    "No tenes permisos para consultar empleados con el rol actual. "
                    "Inicia sesion como Admin_Nivel_2 para acceder a esa informacion."
                )
            )

        content = (
            "Respuesta de respaldo: el grafo esta operativo y el agente fue designado, "
            "pero el proveedor LLM configurado no esta disponible ahora."
        )
        if user_text:
            content += f" Consulta recibida: {user_text}"

        return AIMessage(content=content)


def fallback_chat_model() -> OfflineFallbackChatModel:
    """Offline model used when external chat providers are unavailable."""
    logger.info("Usando modelo de respaldo offline")
    return OfflineFallbackChatModel()