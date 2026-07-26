"""Embeddings y vector store persistente para el RAG."""

from __future__ import annotations

from functools import lru_cache
from typing import List

from langchain_core.documents import Document

from rag.config import (
    CHROMA_COLLECTION_NAME,
    CHROMA_PERSIST_DIR,
    EMBEDDING_MODEL_NAME,
    logger,
)
from rag.documents import get_chunked_documents

try:
    from langchain_huggingface import HuggingFaceEmbeddings
except Exception:  # pragma: no cover - fallback defensivo para entornos viejos
    from langchain_community.embeddings import HuggingFaceEmbeddings  # type: ignore

try:
    from langchain_chroma import Chroma
except Exception:  # pragma: no cover
    Chroma = None  # type: ignore


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    """Crea y cachea el objeto de embeddings."""
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        encode_kwargs={"normalize_embeddings": True},
    )


def _build_in_memory_store(chunks: List[Document]):
    from langchain_core.vectorstores import InMemoryVectorStore

    store = InMemoryVectorStore(embedding=get_embeddings())
    store.add_documents(chunks)
    return store


def _build_vector_store(chunks: List[Document]):
    """Construye ChromaDB persistente, con fallback en memoria."""
    embeddings = get_embeddings()

    if Chroma is None:
        logger.warning("ChromaDB no esta disponible. Usando InMemoryVectorStore.")
        return _build_in_memory_store(chunks)

    try:
        logger.info("Inicializando ChromaDB en: %s", CHROMA_PERSIST_DIR)
        vector_store = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            ids=[str(chunk.metadata["chunk_id"]) for chunk in chunks],
            persist_directory=CHROMA_PERSIST_DIR,
            collection_name=CHROMA_COLLECTION_NAME,
        )

        if hasattr(vector_store, "persist"):
            vector_store.persist()

        logger.info("%s chunks guardados en ChromaDB", len(chunks))
        return vector_store
    except Exception as exc:
        logger.warning("Error con ChromaDB: %s", exc)
        logger.warning("Usando InMemoryVectorStore como fallback.")
        return _build_in_memory_store(chunks)


@lru_cache(maxsize=1)
def get_vector_store():
    """Construye el indice vectorial con persistencia en ChromaDB."""
    return _build_vector_store(get_chunked_documents())
