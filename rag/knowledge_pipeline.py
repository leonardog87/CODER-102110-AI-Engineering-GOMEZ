"""Consulta de los conocimientos no parametrizados almacenados en PDF."""

from __future__ import annotations

from typing import Any, Dict, List

from langchain_core.documents import Document

from rag.config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    EMBEDDING_MODEL_NAME,
    KNOWLEDGE_CHROMA_COLLECTION_NAME,
    KNOWLEDGE_CHROMA_PERSIST_DIR,
)
from rag.knowledge_documents import get_knowledge_chunks, load_knowledge_documents
from rag.knowledge_vector_store import get_knowledge_vector_store


def retrieve_knowledge_documents(query: str, top_k: int = 3) -> List[Document]:
    """Recupera fragmentos relevantes de los PDF."""
    clean_query = (query or "").strip()
    if not clean_query:
        return []
    return get_knowledge_vector_store().similarity_search(clean_query, k=top_k)


def retrieve_knowledge_context(query: str, top_k: int = 3) -> str:
    """Formatea los fragmentos recuperados con su archivo y página."""
    documents = retrieve_knowledge_documents(query, top_k)
    if not documents:
        return "No se encontraron fragmentos relevantes en knowledge_base."

    sections = ["# Contexto de la base de conocimiento", ""]
    for index, document in enumerate(documents, start=1):
        metadata = document.metadata or {}
        sections.extend(
            [
                f"## Fragmento {index}",
                f"Fuente: {metadata.get('source', 'Desconocida')}",
                f"Página: {metadata.get('page', 'N/A')}",
                "",
                document.page_content.strip(),
                "",
            ]
        )
    return "\n".join(sections).strip()


def get_knowledge_stats() -> Dict[str, Any]:
    """Informa el contenido y configuración del segundo índice."""
    documents = load_knowledge_documents()
    chunks = get_knowledge_chunks()
    return {
        "pages": len(documents),
        "chunks": len(chunks),
        "sources": sorted({doc.metadata["source"] for doc in documents}),
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "embedding_model": EMBEDDING_MODEL_NAME,
        "persist_directory": KNOWLEDGE_CHROMA_PERSIST_DIR,
        "collection_name": KNOWLEDGE_CHROMA_COLLECTION_NAME,
    }
