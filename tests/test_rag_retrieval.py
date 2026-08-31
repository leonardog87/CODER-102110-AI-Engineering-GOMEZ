"""Evaluación local de precisión básica para ambos índices RAG."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from rag.knowledge_pipeline import retrieve_knowledge_documents
from rag.pipeline import retrieve_documents
from agent_system.manager_agent import agente_encargado


def _sources(documents) -> set[str]:
    return {str(document.metadata.get("source", "")) for document in documents}


def test_deterministic_role_sources() -> None:
    invited = agente_encargado({"rol_usuario": "Invitado"})
    employee = agente_encargado({"rol_usuario": "Empleado"})

    invited_text = invited["motivo_designacion"].lower()
    employee_text = employee["motivo_designacion"].lower()

    assert "manual_usuario" in invited_text
    assert "manual_usuario" in employee_text
    assert "manual_empleado" in employee_text
    assert "manual_empleado" not in invited_text


def main() -> int:
    password_docs = retrieve_knowledge_documents("¿Cómo recupero mi contraseña?")
    support_docs = retrieve_knowledge_documents("¿Cuál es el teléfono de soporte?")
    audience_docs = retrieve_knowledge_documents("a quien esta dirgida esta web?")
    registration_docs = retrieve_knowledge_documents("como me registro?")
    capabilities_docs = retrieve_knowledge_documents("que puedo hacer aqui?")
    assert password_docs and len(password_docs) <= 2
    assert support_docs and len(support_docs) <= 2
    assert audience_docs and len(audience_docs) <= 2
    assert registration_docs and len(registration_docs) <= 2
    assert capabilities_docs and len(capabilities_docs) <= 2
    assert "empleados del ministerio de capital humano" in " ".join(
        document.page_content.lower() for document in audience_docs
    )
    assert "registrarme" in " ".join(
        document.page_content.lower() for document in registration_docs
    )
    assert "qué puedo hacer aquí" in " ".join(
        document.page_content.lower() for document in capabilities_docs
    )

    assert not retrieve_knowledge_documents(
        "¿Cómo obtengo un acta de nacimiento del Registro Civil?"
    )
    assert not retrieve_knowledge_documents("receta de cocina italiana")

    database_docs = retrieve_documents(
        "política de acceso seguro a bases de datos"
    )
    network_docs = retrieve_documents("diagnóstico de problemas de red y DNS")
    assert "normativa_acceso_bases_datos.md" in _sources(database_docs)
    assert "guia_problemas_red.md" in _sources(network_docs)

    test_deterministic_role_sources()

    print("[OK] Recuperación relevante limitada a dos fragmentos")
    print("[OK] Público destinatario del portal recuperado correctamente")
    print("[OK] Consultas fuera de dominio filtradas")
    print("[OK] Fuentes complejas correctas para normativa y red")
    print("[OK] Contexto determinista por rol configurado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
