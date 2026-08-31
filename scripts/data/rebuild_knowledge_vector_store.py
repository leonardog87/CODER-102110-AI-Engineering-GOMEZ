#!/usr/bin/env python3
"""Recrea desde cero el índice Chroma de knowledge_base."""

from __future__ import annotations

import logging
import shutil
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import chromadb
from dotenv import load_dotenv
from langchain_chroma import Chroma

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rebuild_knowledge_vector_store")


def _remove_orphan_vector_directories(persist_directory: str) -> int:
    """Elimina segmentos HNSW que Chroma deja tras reemplazar una colección."""
    root = Path(persist_directory).resolve()
    database = root / "chroma.sqlite3"
    with sqlite3.connect(database) as connection:
        active_ids = {
            str(row[0])
            for row in connection.execute(
                "SELECT id FROM segments WHERE scope = 'VECTOR'"
            )
        }

    removed = 0
    for directory in root.iterdir():
        if not directory.is_dir() or directory.name in active_ids:
            continue
        resolved = directory.resolve()
        if resolved.parent != root:
            raise RuntimeError(f"Segmento fuera del directorio Chroma: {resolved}")
        shutil.rmtree(resolved)
        removed += 1
    return removed


def rebuild_knowledge_chromadb() -> bool:
    """Reemplaza la colección usando únicamente las fuentes editables vigentes."""
    try:
        from rag.config import (
            KNOWLEDGE_BASE_PATH,
            KNOWLEDGE_CHROMA_COLLECTION_NAME,
            KNOWLEDGE_CHROMA_PERSIST_DIR,
        )
        from rag.knowledge_documents import (
            get_knowledge_chunks,
            load_knowledge_documents,
        )
        from rag.knowledge_vector_store import (
            get_embeddings,
            normalized_euclidean_relevance,
        )

        documents = load_knowledge_documents()
        chunks = get_knowledge_chunks()
        embeddings = get_embeddings()

        client = chromadb.PersistentClient(path=KNOWLEDGE_CHROMA_PERSIST_DIR)
        collection_names = {
            collection.name for collection in client.list_collections()
        }
        if KNOWLEDGE_CHROMA_COLLECTION_NAME in collection_names:
            client.delete_collection(KNOWLEDGE_CHROMA_COLLECTION_NAME)

        vector_store = Chroma(
            collection_name=KNOWLEDGE_CHROMA_COLLECTION_NAME,
            embedding_function=embeddings,
            persist_directory=KNOWLEDGE_CHROMA_PERSIST_DIR,
            relevance_score_fn=normalized_euclidean_relevance,
        )
        vector_store.add_documents(
            documents=chunks,
            ids=[str(chunk.metadata["chunk_id"]) for chunk in chunks],
        )
        removed_segments = _remove_orphan_vector_directories(
            KNOWLEDGE_CHROMA_PERSIST_DIR
        )

        sources = sorted({document.metadata["source"] for document in documents})
        logger.info("Índice de knowledge_base recreado correctamente.")
        logger.info("Fuentes: %s", ", ".join(sources))
        logger.info("Documentos: %s", len(documents))
        logger.info("Chunks: %s", vector_store._collection.count())
        logger.info("Segmentos obsoletos eliminados: %s", removed_segments)
        logger.info("Origen: %s", KNOWLEDGE_BASE_PATH)
        logger.info("Destino: %s", KNOWLEDGE_CHROMA_PERSIST_DIR)
        return True
    except Exception:
        logger.exception("No se pudo recrear la base de conocimiento simple.")
        return False


if __name__ == "__main__":
    raise SystemExit(0 if rebuild_knowledge_chromadb() else 1)
