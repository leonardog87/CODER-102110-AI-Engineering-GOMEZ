"""Manager agent that delegates to a specialist with an explicit tool set."""

from __future__ import annotations

import logging
from typing import Literal

from agent_system.constants import (
    AGENT_ADMINISTRADOR,
    AGENT_EMPLEADO,
    AGENT_INVITADO,
    DEFAULT_AGENT,
    DEFAULT_ROLE,
    ROLE_ADMINISTRADOR,
    ROLE_EMPLEADO,
)
from agent_system.state import AgentName, AgentState

logger = logging.getLogger("agente_corporativo.agent_system.manager_agent")


def agente_encargado(state: AgentState) -> dict:
    """Choose the specialist agent from the authenticated role.

    This manager is intentionally deterministic: authorization should depend on
    trusted application state, not on an LLM interpretation of the user's text.
    """

    rol = state.get("rol_usuario", DEFAULT_ROLE)

    if rol == ROLE_EMPLEADO:
        agente: AgentName = AGENT_EMPLEADO
        motivo = (
            "Rol Empleado: acceso a manual_usuario.md, manual_empleados.md y "
            "datos de empleados sin información salarial."
        )
    elif rol == ROLE_ADMINISTRADOR:
        agente = AGENT_ADMINISTRADOR
        motivo = (
            "Rol Administrador: acceso a manual_usuario.md, manual_empleados.md y "
            "al conjunto completo de datos de empleados."
        )
    else:
        agente = AGENT_INVITADO
        motivo = (
            "Rol Invitado: acceso exclusivo a manual_usuario.md y "
            "documentación pública del Ministerio."
        )

    logger.info("Agente encargado designo %s para rol %s", agente, rol)
    return {
        "agente_designado": agente,
        "motivo_designacion": motivo,
    }


def enrutar_por_designacion(
    state: AgentState,
) -> Literal["agente_invitado", "agente_empleado", "agente_administrador"]:
    return state.get("agente_designado", DEFAULT_AGENT)
