"""Evaluación local de precisión básica para ambos índices RAG."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from rag.knowledge_pipeline import retrieve_knowledge_documents
from rag.pipeline import retrieve_documents


def _sources(documents) -> set[str]:
    return {str(document.metadata.get("source", "")) for document in documents}


def main() -> int:
    password_docs = retrieve_knowledge_documents("¿Cómo recupero mi contraseña?")
    support_docs = retrieve_knowledge_documents("¿Cuál es el teléfono de soporte?")
    assert password_docs and len(password_docs) <= 2
    assert support_docs and len(support_docs) <= 2

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

    print("[OK] Recuperación relevante limitada a dos fragmentos")
    print("[OK] Consultas fuera de dominio filtradas")
    print("[OK] Fuentes complejas correctas para normativa y red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
