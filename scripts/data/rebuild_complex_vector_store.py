#!/usr/bin/env python3
"""Recrea desde cero la base Chroma de manuales complejos."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import chromadb
from dotenv import load_dotenv
from langchain_chroma import Chroma

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rebuild_complex_vector_store")


def recrear_manuales_complejos_chroma() -> bool:
    """Reemplaza la colección usando únicamente los archivos de la carpeta fuente."""
    try:
        from rag.config import (
            CHROMA_COLLECTION_NAME,
            CHROMA_PERSIST_DIR,
            COMPLEX_MANUALS_PATH,
        )
        from rag.documents import get_chunked_documents, load_complex_documents
        from rag.vector_store import get_embeddings

        # Se valida el contenido antes de eliminar la colección existente.
        documents = load_complex_documents()
        chunks = get_chunked_documents()
        # El modelo también se carga antes de modificar la colección. Si su
        # descarga o inicialización falla, la base existente queda intacta.
        embeddings = get_embeddings()

        client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        collection_names = {
            collection.name for collection in client.list_collections()
        }
        if CHROMA_COLLECTION_NAME in collection_names:
            client.delete_collection(CHROMA_COLLECTION_NAME)

        vector_store = Chroma(
            collection_name=CHROMA_COLLECTION_NAME,
            embedding_function=embeddings,
            persist_directory=CHROMA_PERSIST_DIR,
        )
        vector_store.add_documents(
            documents=chunks,
            ids=[str(chunk.metadata["chunk_id"]) for chunk in chunks],
        )

        sources = sorted({document.metadata["source"] for document in documents})
        logger.info("Base de manuales complejos recreada correctamente.")
        logger.info("Archivos: %s", ", ".join(sources))
        logger.info("Documentos/páginas con texto: %s", len(documents))
        logger.info("Chunks: %s", vector_store._collection.count())
        logger.info("Origen: %s", COMPLEX_MANUALS_PATH)
        logger.info("Destino: %s", CHROMA_PERSIST_DIR)
        logger.info("Colección: %s", CHROMA_COLLECTION_NAME)
        return True
    except Exception:
        logger.exception("No se pudo recrear la base de manuales complejos.")
        return False


if __name__ == "__main__":
    sys.exit(0 if recrear_manuales_complejos_chroma() else 1)
