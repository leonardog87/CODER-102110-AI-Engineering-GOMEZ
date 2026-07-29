"""Consulta del conocimiento general almacenado en fuentes editables."""

from __future__ import annotations

from typing import Any, Dict, List

from langchain_core.documents import Document

from rag.config import (
    EMBEDDING_MODEL_NAME,
    KNOWLEDGE_CHUNK_OVERLAP,
    KNOWLEDGE_CHUNK_SIZE,
    KNOWLEDGE_CHROMA_COLLECTION_NAME,
    KNOWLEDGE_CHROMA_PERSIST_DIR,
    KNOWLEDGE_RETRIEVAL_CANDIDATES,
    KNOWLEDGE_RETRIEVAL_TOP_K,
    KNOWLEDGE_RELEVANCE_THRESHOLD,
)
from rag.knowledge_documents import get_knowledge_chunks, load_knowledge_documents
from rag.knowledge_vector_store import get_knowledge_vector_store
from rag.ranking import rerank_documents


def retrieve_knowledge_documents(
    query: str,
    top_k: int = KNOWLEDGE_RETRIEVAL_TOP_K,
) -> List[Document]:
    """Recupera y reordena fragmentos relevantes de las fuentes simples."""
    clean_query = (query or "").strip()
    if not clean_query:
        return []
    candidate_k = max(KNOWLEDGE_RETRIEVAL_CANDIDATES, top_k)
    candidates = get_knowledge_vector_store().similarity_search_with_relevance_scores(
        clean_query,
        k=candidate_k,
    )
    relevant = [
        (document, float(score))
        for document, score in candidates
        if float(score) >= KNOWLEDGE_RELEVANCE_THRESHOLD
    ]
    ranked = rerank_documents(
        clean_query,
        [document for document, _score in relevant],
        [score for _document, score in relevant],
    )
    return [document for document, _score in ranked[:top_k]]


def retrieve_knowledge_context(
    query: str,
    top_k: int = KNOWLEDGE_RETRIEVAL_TOP_K,
) -> str:
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
        "documents": len(documents),
        "chunks": len(chunks),
        "sources": sorted({doc.metadata["source"] for doc in documents}),
        "chunk_size": KNOWLEDGE_CHUNK_SIZE,
        "chunk_overlap": KNOWLEDGE_CHUNK_OVERLAP,
        "embedding_model": EMBEDDING_MODEL_NAME,
        "persist_directory": KNOWLEDGE_CHROMA_PERSIST_DIR,
        "collection_name": KNOWLEDGE_CHROMA_COLLECTION_NAME,
    }
