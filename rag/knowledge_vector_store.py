"""Base Chroma independiente para documentos no parametrizados."""

from __future__ import annotations

from functools import lru_cache

from langchain_chroma import Chroma

from rag.config import (
    KNOWLEDGE_CHROMA_COLLECTION_NAME,
    KNOWLEDGE_CHROMA_PERSIST_DIR,
    logger,
)
from rag.knowledge_documents import get_knowledge_chunks
from rag.vector_store import get_embeddings, normalized_euclidean_relevance


@lru_cache(maxsize=1)
def get_knowledge_vector_store() -> Chroma:
    """Abre la colección persistente y sincroniza las fuentes editables."""
    vector_store = Chroma(
        collection_name=KNOWLEDGE_CHROMA_COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=KNOWLEDGE_CHROMA_PERSIST_DIR,
        relevance_score_fn=normalized_euclidean_relevance,
    )

    chunks = get_knowledge_chunks()
    if not chunks:
        raise ValueError("No se encontraron fuentes de texto en knowledge_base.")

    chunk_ids = [str(chunk.metadata["chunk_id"]) for chunk in chunks]
    current_ids = set(chunk_ids)
    stored_ids = set(vector_store._collection.get(include=[])["ids"])
    obsolete_ids = sorted(stored_ids - current_ids)
    if obsolete_ids:
        vector_store.delete(ids=obsolete_ids)
        logger.info("%s chunks obsoletos eliminados.", len(obsolete_ids))
    vector_store.add_documents(
        documents=chunks,
        ids=chunk_ids,
    )
    logger.info(
        "%s chunks de knowledge_base sincronizados en %s",
        len(chunks),
        KNOWLEDGE_CHROMA_PERSIST_DIR,
    )

    return vector_store
