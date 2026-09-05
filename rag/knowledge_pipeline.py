"""Consulta del conocimiento general almacenado en fuentes editables."""

from __future__ import annotations

import logging
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
from rag.ranking import _tokenize, rerank_documents

logger = logging.getLogger("agente_corporativo.rag.knowledge_pipeline")


def _expand_common_portal_queries(query: str) -> str:
    """Refuerza preguntas frecuentes aun cuando contengan errores menores."""
    normalized_tokens = set(_tokenize(query))
    normalized = " ".join(_tokenize(query))
    asks_about_site = bool(normalized_tokens & {"web", "portal", "sitio"})
    asks_about_audience = bool(
        normalized_tokens & {"quien", "dirigido", "destinado", "creado"}
    )
    if asks_about_site and asks_about_audience:
        return f"{query} ¿A quién está dirigida o dedicada esta web?"
    if any(term in normalized for term in ("contraseña", "contrasena", "clave")):
        return f"{query} ¿Cómo recuperar mi contraseña o clave?"
    if any(term in normalized for term in ("registro", "registrar", "cuenta")):
        return f"{query} ¿Cómo crear un usuario y registrarme por primera vez?"
    if any(term in normalized for term in ("puedo hacer", "para que sirve", "para qué sirve")):
        return f"{query} ¿Qué puedo hacer aquí y qué funciones ofrece el portal?"
    return query


def retrieve_knowledge_documents(
    query: str,
    top_k: int = KNOWLEDGE_RETRIEVAL_TOP_K,
) -> List[Document]:
    """Recupera y reordena fragmentos relevantes de las fuentes simples."""
    clean_query = (query or "").strip()
    if not clean_query:
        return []
    retrieval_query = _expand_common_portal_queries(clean_query)
    candidate_k = max(KNOWLEDGE_RETRIEVAL_CANDIDATES, top_k)
    try:
        candidates = (
            get_knowledge_vector_store().similarity_search_with_relevance_scores(
                retrieval_query,
                k=candidate_k,
            )
        )
    except Exception as exc:
        logger.warning(
            "Búsqueda vectorial no disponible; se usará recuperación léxica: %s",
            exc,
        )
        candidates = []
    query_tokens = set(_tokenize(retrieval_query))
    lexical_query_tokens = set(_tokenize(clean_query))
    relevant = []
    selected_ids: set[str] = set()
    for document, score in candidates:
        if float(score) < KNOWLEDGE_RELEVANCE_THRESHOLD:
            continue
        relevant.append((document, float(score)))
        selected_ids.add(str(document.metadata.get("chunk_id", "")))

    # Respaldo léxico para consultas cuya formulación no supera el umbral
    # vectorial. La normalización compartida tolera tildes omitidas.
    for document in get_knowledge_chunks():
        chunk_id = str(document.metadata.get("chunk_id", ""))
        if chunk_id in selected_ids:
            continue
        document_tokens = set(_tokenize(document.page_content))
        coverage = len(lexical_query_tokens & document_tokens) / max(
            len(lexical_query_tokens), 1
        )
        if coverage < 0.5:
            continue
        relevant.append((document, 0.0))
        selected_ids.add(chunk_id)
    ranked = rerank_documents(
        retrieval_query,
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
