"""Comprueba que la política predeterminada solo exponga fuentes locales."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent_system import retrieval_policy  # noqa: E402
from agent_system.web_tools import (  # noqa: E402
    web_retrieve_allowed_url,
    web_search_allowed,
)
from agent_system.invitado_agent import INVITADO_TOOLS  # noqa: E402
from agent_system.empleado_agent import EMPLEADO_TOOLS  # noqa: E402
from agent_system.administrador_agent import ADMINISTRADOR_TOOLS  # noqa: E402


def main() -> int:
    local_tool = SimpleNamespace(name="knowledge_retrieve_context")
    sqlite_tool = SimpleNamespace(name="consultar_empleados_mcp_empleado")
    external_tool = SimpleNamespace(name="web_search")
    retrieval_policy.WEB_SEARCH_ENABLED = False
    selected = retrieval_policy.enabled_tools(
        [local_tool, sqlite_tool, external_tool]
    )

    assert [tool.name for tool in selected] == [
        "knowledge_retrieve_context",
        "consultar_empleados_mcp_empleado",
    ]
    assert all(tool.name in retrieval_policy.LOCAL_TOOL_NAMES for tool in selected)
    for role_tools in (INVITADO_TOOLS, EMPLEADO_TOOLS, ADMINISTRADOR_TOOLS):
        assert not ({tool.name for tool in role_tools} & retrieval_policy.WEB_TOOL_NAMES)

    assert "desactivada" in web_search_allowed.invoke({"query": "prueba"})
    assert "desactivada" in web_retrieve_allowed_url.invoke(
        {"url": "https://argentina.gob.ar/"}
    )

    retrieval_policy.WEB_SEARCH_ENABLED = True
    selected_when_enabled = retrieval_policy.enabled_tools(
        [local_tool, external_tool, web_search_allowed, web_retrieve_allowed_url]
    )
    assert [tool.name for tool in selected_when_enabled] == [
        "knowledge_retrieve_context",
        "web_search_allowed",
        "web_retrieve_allowed_url",
    ]
    retrieval_policy.WEB_SEARCH_ENABLED = False
    print("[OK] Búsqueda web desactivada y herramientas externas filtradas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
