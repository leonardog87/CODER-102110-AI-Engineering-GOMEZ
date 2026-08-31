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
    SEMANTIC_SEARCH_ENABLED,
)
from rag.knowledge_documents import get_knowledge_chunks, load_knowledge_documents
from rag.knowledge_vector_store import get_knowledge_vector_store
from rag.ranking import has_lexical_overlap, rerank_documents


def _expand_common_portal_queries(query: str) -> str:
    """Refuerza preguntas frecuentes aun cuando contengan errores menores."""
    normalized = query.lower()
    asks_about_site = "web" in normalized or "portal" in normalized
    asks_about_audience = "quien" in normalized or "quién" in normalized
    if asks_about_site and asks_about_audience:
        return f"{query} ¿A quién está dirigida o dedicada esta web?"
    if any(term in normalized for term in ("contraseña", "contrasena", "clave")):
        return f"{query} ¿Cómo recuperar mi contraseña o clave?"
    if any(term in normalized for term in ("registro", "registrar", "cuenta")):
        return f"{query} ¿Cómo crear un usuario y registrarme por primera vez?"
    if any(term in normalized for term in ("puedo hacer", "para que sirve", "para qué sirve")):
        return f"{query} ¿Qué puedo hacer aquí y qué funciones ofrece el portal?"
    return query


def _intent_matches(query: str, documents: List[Document]) -> List[Document]:
    """Prioriza coincidencias inequívocas para consultas frecuentes y breves."""
    normalized = query.lower()
    stems: tuple[str, ...] = ()
    intent = ""
    if any(
        term in normalized
        for term in ("registro", "registrar", "registro", "cuenta", "crear usuario")
    ):
        intent = "registration"
        stems = ("registr", "crear cuenta")
    elif any(term in normalized for term in ("contraseña", "contrasena", "clave")):
        intent = "password"
        stems = ("contrase", "clave")
    elif any(term in normalized for term in ("contacto", "teléfono", "telefono", "soporte")):
        intent = "contact"
        stems = ("contacto", "teléfono", "telefono", "soporte")
    if not stems:
        return []
    matches = [
        document
        for document in documents
        if any(stem in document.page_content.lower() for stem in stems)
    ]
    def intent_score(document: Document) -> int:
        text = document.page_content.lower()
        score = sum(text.count(stem) for stem in stems)
        if intent == "registration":
            score += (text.count("paso") * 4) + (text.count("haz clic") * 3)
        elif intent == "password":
            score += (text.count("paso") * 3) + (text.count("recuper") * 3)
        elif intent == "contact":
            score += text.count("@") * 3
        return score
    return sorted(matches, key=intent_score, reverse=True)


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
    chunks = get_knowledge_chunks()
    intent_matches = _intent_matches(clean_query, chunks)
    if intent_matches:
        return intent_matches[:top_k]
    lexical = rerank_documents(retrieval_query, chunks)
    lexical_matches = [
        item for item in lexical if has_lexical_overlap(retrieval_query, item[0])
    ]
    if lexical_matches:
        return [document for document, _score in lexical_matches[:top_k]]
    if not SEMANTIC_SEARCH_ENABLED:
        return []
    try:
        candidates = get_knowledge_vector_store().similarity_search_with_relevance_scores(
            retrieval_query,
            k=candidate_k,
        )
    except Exception:
        candidates = []
    relevant = [
        (document, float(score))
        for document, score in candidates
        if float(score) >= KNOWLEDGE_RELEVANCE_THRESHOLD
    ]
    if not relevant:
        # Respaldo léxico sobre la fuente actual. Evita falsos negativos por
        # umbrales de embeddings en preguntas breves como "¿cómo me registro?".
        lexical = rerank_documents(retrieval_query, get_knowledge_chunks())
        relevant = [
            item for item in lexical if has_lexical_overlap(retrieval_query, item[0])
        ][:candidate_k]
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
    """Informa el contenido y configuración del índice único."""
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
