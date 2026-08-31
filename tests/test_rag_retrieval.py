"""Evaluación local de precisión de knowledge_base."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from rag.knowledge_pipeline import retrieve_knowledge_documents
from agent_system.tools import knowledge_retrieve_context


def main() -> int:
    password_docs = retrieve_knowledge_documents("¿Cómo recupero mi contraseña?")
    support_docs = retrieve_knowledge_documents("¿Cuál es el teléfono de soporte?")
    registration_docs = retrieve_knowledge_documents("como me registro?")
    assert password_docs and len(password_docs) <= 3
    assert support_docs and len(support_docs) <= 3
    assert registration_docs and len(registration_docs) <= 3
    assert "registr" in " ".join(
        document.page_content.lower() for document in registration_docs
    )

    registration_context = knowledge_retrieve_context.invoke(
        {"query": "¿Cómo me registro?", "top_k": 2}
    )
    user_context = knowledge_retrieve_context.invoke(
        {"query": "¿Cómo creo un usuario?", "top_k": 2}
    )
    services_context = knowledge_retrieve_context.invoke(
        {"query": "Buen día, ¿qué servicios prestan?", "top_k": 2}
    )
    assert "registr" in registration_context.lower()
    assert "paso" in registration_context.lower()
    assert "crear cuenta" in user_context.lower() or "registr" in user_context.lower()
    assert "no se encontraron fragmentos" not in registration_context.lower()
    assert "manual_servicios.md" in services_context
    assert "servicio" in services_context.lower()

    print("[OK] Recuperación relevante limitada a tres fragmentos")
    print("[OK] Registro y soporte recuperados correctamente")
    print("[OK] Servicios recuperados desde knowledge_base")
    print("[OK] Fuente única knowledge_base disponible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
