"""Shared role and agent identifiers."""

ROLE_INVITADO = "Invitado"
ROLE_EMPLEADO = "Empleado"

AGENT_MANAGER = "agente_encargado"
AGENT_INVITADO = "agente_invitado"
AGENT_EMPLEADO = "agente_empleado"

ROLE_TO_AGENT = {
    ROLE_INVITADO: AGENT_INVITADO,
    ROLE_EMPLEADO: AGENT_EMPLEADO,
}

DEFAULT_ROLE = ROLE_INVITADO
DEFAULT_AGENT = AGENT_INVITADO
