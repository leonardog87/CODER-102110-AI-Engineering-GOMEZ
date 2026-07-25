"""Shared role and agent identifiers."""

ROLE_INVITADO = "Invitado"
ROLE_SOPORTE = "Soporte_Nivel_1"
ROLE_ADMIN = "Admin_Nivel_2"

AGENT_MANAGER = "agente_encargado"
AGENT_PUBLIC = "agente_publico"
AGENT_SUPPORT = "agente_soporte"
AGENT_ADMIN = "agente_admin"

ROLE_TO_AGENT = {
    ROLE_INVITADO: AGENT_PUBLIC,
    ROLE_SOPORTE: AGENT_SUPPORT,
    ROLE_ADMIN: AGENT_ADMIN,
}

DEFAULT_ROLE = ROLE_INVITADO
DEFAULT_AGENT = AGENT_PUBLIC
