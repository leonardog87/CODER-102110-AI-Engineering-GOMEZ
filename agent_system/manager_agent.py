"""Manager agent that delegates to a specialist with an explicit tool set."""

from __future__ import annotations

import logging
from typing import Literal

from agent_system.constants import (
    AGENT_ADMIN,
    AGENT_PUBLIC,
    AGENT_SUPPORT,
    DEFAULT_AGENT,
    DEFAULT_ROLE,
    ROLE_ADMIN,
    ROLE_SOPORTE,
)
from agent_system.state import AgentName, AgentState

logger = logging.getLogger("ciudad_analitica.agent_system.manager_agent")


def agente_encargado(state: AgentState) -> dict:
    """Choose the specialist agent from the authenticated role.

    This manager is intentionally deterministic: authorization should depend on
    trusted application state, not on an LLM interpretation of the user's text.
    """

    rol = state.get("rol_usuario", DEFAULT_ROLE)

    if rol == ROLE_SOPORTE:
        agente: AgentName = AGENT_SUPPORT
        motivo = "Rol Soporte_Nivel_1: habilita RAG y consulta MCP limitada a clientes."
    elif rol == ROLE_ADMIN:
        agente = AGENT_ADMIN
        motivo = "Rol Admin_Nivel_2: habilita RAG y consultas MCP de clientes y empleados."
    else:
        agente = AGENT_PUBLIC
        motivo = "Rol Invitado: sin herramientas internas ni acceso a datos."

    logger.info("Agente encargado designo %s para rol %s", agente, rol)
    return {
        "agente_designado": agente,
        "motivo_designacion": motivo,
    }


def enrutar_por_designacion(
    state: AgentState,
) -> Literal["agente_publico", "agente_soporte", "agente_admin"]:
    return state.get("agente_designado", DEFAULT_AGENT)
