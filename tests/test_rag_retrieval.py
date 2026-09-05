"""Evaluación local de precisión básica para ambos índices RAG."""

from __future__ import annotations

import sys
from pathlib import Path

from langchain_core.messages import HumanMessage

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from rag.knowledge_pipeline import retrieve_knowledge_documents
from rag.pipeline import retrieve_documents
from agent_system.manager_agent import agente_encargado
from agent_system.runtime import (
    _is_ambiguous_personal_data_update,
    invoke_specialist_agent,
)
from agent_system.tools import rag_retrieve_context


def _sources(documents) -> set[str]:
    return {str(document.metadata.get("source", "")) for document in documents}


def test_deterministic_role_sources() -> None:
    invited = agente_encargado({"rol_usuario": "Invitado"})
    employee = agente_encargado({"rol_usuario": "Empleado"})

    invited_text = invited["motivo_designacion"].lower()
    employee_text = employee["motivo_designacion"].lower()

    assert "manual_usuario" in invited_text
    assert "manual_usuario" not in employee_text
    assert "manual_empleado" in employee_text
    assert "manual_empleado" not in invited_text


def test_family_context_excludes_unrelated_procedures() -> None:
    family_docs = retrieve_documents(
        "¿Cómo actualizo los datos de mi grupo familiar?",
        top_k=3,
    )
    family_context = " ".join(
        document.page_content.lower() for document in family_docs
    )
    assert family_docs
    assert "actualización de datos de grupo familiar" in family_context, family_context
    assert "copia legible del dni del familiar" in family_context, family_context
    assert "vía presencial" in family_context, family_context
    assert "cambio de entidad bancaria" not in family_context, family_context


def test_profile_photo_excludes_password_change() -> None:
    photo_docs = retrieve_documents("¿Cómo cambio mi foto de perfil?", top_k=3)
    photo_context = " ".join(
        document.page_content.lower() for document in photo_docs
    )
    assert photo_docs
    assert "carga y modificación de la foto de perfil" in photo_context, photo_context
    assert "cambio de contraseña" not in photo_context, photo_context


def test_guarderia_reimbursement_is_retrieved() -> None:
    guarderia_docs = retrieve_documents(
        "Como funciona el reintegro por guarderia?",
        top_k=3,
    )
    guarderia_context = " ".join(
        document.page_content.lower() for document in guarderia_docs
    )
    assert guarderia_docs
    assert "reintegro por guardería" in guarderia_context, guarderia_context
    assert "trámite de alta del beneficio" in guarderia_context, guarderia_context
    assert "trámite mensual" in guarderia_context, guarderia_context


def test_ambiguous_personal_data_update_requires_clarification() -> None:
    assert _is_ambiguous_personal_data_update("¿Cómo actualizo mis datos?")
    assert not _is_ambiguous_personal_data_update(
        "¿Cómo actualizo los datos de mi grupo familiar?"
    )
    result = invoke_specialist_agent(
        system_prompt="",
        messages=[HumanMessage(content="¿Cómo actualizo mis datos?")],
        tools=[rag_retrieve_context],
    )
    response = result["messages"][-1].content
    assert "¿Qué datos querés actualizar" in response
    assert "No encontré" not in response


def test_guest_site_audience_query() -> None:
    audience_docs = retrieve_knowledge_documents("a quien esta dirigido el sitio?")
    audience_context = " ".join(
        document.page_content.lower() for document in audience_docs
    )
    assert audience_docs
    assert "empleados del ministerio de capital humano" in audience_context


def main() -> int:
    password_docs = retrieve_knowledge_documents("¿Cómo recupero mi contraseña?")
    support_docs = retrieve_knowledge_documents("¿Cuál es el teléfono de soporte?")
    audience_docs = retrieve_knowledge_documents("a quien esta dirigido el sitio?")
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

    test_family_context_excludes_unrelated_procedures()
    test_profile_photo_excludes_password_change()
    test_guarderia_reimbursement_is_retrieved()

    assert not retrieve_documents("familiar", top_k=3)

    test_deterministic_role_sources()

    print("[OK] Recuperación relevante limitada a dos fragmentos")
    print("[OK] Público destinatario del portal recuperado correctamente")
    print("[OK] Consultas fuera de dominio filtradas")
    print("[OK] Fuentes complejas correctas para normativa y red")
    print("[OK] Grupo familiar recuperado completo y sin trámites ajenos")
    print("[OK] Contexto determinista por rol configurado")
    return 0


if __name__ == "__main__":
    if "--audience-only" in sys.argv:
        test_guest_site_audience_query()
        print("[OK] El rol Invitado recupera el público destinatario del sitio")
        raise SystemExit(0)
    if "--ambiguity-only" in sys.argv:
        test_ambiguous_personal_data_update_requires_clarification()
        print("[OK] Las actualizaciones ambiguas solicitan precisión")
        raise SystemExit(0)
    if "--family-only" in sys.argv:
        test_family_context_excludes_unrelated_procedures()
        print("[OK] Grupo familiar recuperado completo y sin trámites ajenos")
        raise SystemExit(0)
    raise SystemExit(main())
