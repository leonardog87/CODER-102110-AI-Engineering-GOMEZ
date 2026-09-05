"""Chat model factory with local fallbacks."""

from __future__ import annotations

import logging
import os
import unicodedata
from functools import lru_cache
from typing import Any, Dict, List

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, BaseMessage

load_dotenv()

logger = logging.getLogger("agente_corporativo.agent_system.models")

_token = os.getenv("HUGGINGFACEHUB_API_TOKEN") or os.getenv("HF_TOKEN")
if _token:
    os.environ["HF_TOKEN"] = _token
    os.environ["HUGGINGFACEHUB_API_TOKEN"] = _token


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

    if openai_api_base and "router.huggingface.co" in openai_api_base:
        openai_api_key = (
            os.getenv("HUGGINGFACEHUB_API_TOKEN")
            or os.getenv("HF_TOKEN")
            or openai_api_key
        )

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
        or os.getenv("AGENTE_CORPORATIVO_HF_MODEL_ID")
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

        employee_tool = next(
            (
                name
                for name in (
                    "consultar_empleados_mcp_empleado",
                )
                if name in tool_names
            ),
            None,
        )
        if "empleado" in normalized_user_text and employee_tool:
            return AIMessage(
                content=(
                    f'{{"name": "{employee_tool}", '
                    '"arguments": {"dni": null, "nombre": null, "apellido": null, '
                    '"area": null, "puesto": null}}'
                )
            )

        if "cliente" in normalized_user_text:
            return AIMessage(
                content="La base SQLite disponible contiene únicamente empleados."
            )

        if "empleado" in normalized_user_text:
            return AIMessage(
                content=(
                    "No tenes permisos para consultar empleados con el rol actual. "
                    "Este rol no tiene acceso a la base de empleados."
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
