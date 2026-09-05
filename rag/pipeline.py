"""API pública del pipeline RAG del Agente Corporativo IA.

El módulo se mantiene como fachada para no romper imports existentes:
- agent_system.tools importa retrieve_context
- scripts/data/initialize_complex_vector_store.py importa las funciones de carga
- tests/test_persistence.py valida recuperación y persistencia
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

from langchain_core.documents import Document

from rag.config import (
    COMPLEX_CHUNK_OVERLAP,
    COMPLEX_CHUNK_SIZE,
    COMPLEX_RETRIEVAL_CANDIDATES,
    COMPLEX_RETRIEVAL_TOP_K,
    COMPLEX_RELEVANCE_THRESHOLD,
    EMBEDDING_MODEL_NAME,
)
from rag.documents import get_chunked_documents, load_complex_documents
from rag.ranking import _tokenize, rerank_documents
from rag.vector_store import get_embeddings, get_vector_store

__all__ = [
    "get_chunked_documents",
    "get_corpus_stats",
    "get_embeddings",
    "get_vector_store",
    "load_complex_documents",
    "retrieve_context",
    "retrieve_documents",
]


def _get_ranked_documents(query: str, top_k: int) -> List[tuple[Document, float]]:
    clean_query = (query or "").strip()
    if not clean_query:
        return []

    vector_store = get_vector_store()
    candidate_k = max(COMPLEX_RETRIEVAL_CANDIDATES, top_k)
    candidates = vector_store.similarity_search_with_relevance_scores(
        clean_query,
        k=candidate_k,
    )
    query_tokens = set(_tokenize(clean_query))
    query_tokens = {
        token
        for token in query_tokens
        if not any(
            token != other and other.startswith(token)
            for other in query_tokens
        )
    }
    # El embedding aporta candidatos semánticos, pero no debe poder ocultar
    # coincidencias textuales inequívocas. Se agregan chunks del corpus que
    # contengan términos de la consulta (p. ej. "reintegro" y "guardería"),
    # aunque no hayan quedado dentro del top vectorial.
    lexical_candidates: List[tuple[Document, float]] = []
    candidate_ids: set[str] = set()
    for document, score in candidates:
        if not query_tokens & set(_tokenize(document.page_content)):
            continue
        lexical_candidates.append((document, float(score)))
        candidate_ids.add(str(document.metadata.get("chunk_id", "")))

    for document in get_chunked_documents():
        chunk_id = str(document.metadata.get("chunk_id", ""))
        if chunk_id in candidate_ids:
            continue
        if query_tokens & set(_tokenize(document.page_content)):
            lexical_candidates.append((document, 0.0))
            candidate_ids.add(chunk_id)
    if len(query_tokens) == 1:
        query_token = next(iter(query_tokens))
        frequencies = [
            _tokenize(document.page_content).count(query_token)
            for document, _score in lexical_candidates
        ]
        max_frequency = max(frequencies, default=0)
        relevant = [
            item
            for item, frequency in zip(lexical_candidates, frequencies)
            if frequency >= max(1, math.ceil(max_frequency * 0.5))
        ]
    else:
        relevant = [
            item
            for item in lexical_candidates
            if len(query_tokens & set(_tokenize(item[0].page_content)))
            / len(query_tokens)
            >= 0.5
        ]
    ranked = rerank_documents(
        clean_query,
        [document for document, _score in relevant],
        [score for _document, score in relevant],
    )

    # Cuando una sección coincide con más conceptos de la consulta que las
    # demás, conservamos solo ese nivel de cobertura. Por ejemplo, "cambiar
    # foto de perfil" no debe traer "cambiar contraseña" solo porque ambos
    # trámites parten del mismo menú de perfil.
    if ranked and len(query_tokens) > 1:
        overlaps = [
            len(query_tokens & set(_tokenize(document.page_content)))
            for document, _score in ranked
        ]
        max_overlap = max(overlaps)
        if max_overlap >= 2:
            ranked = [
                item
                for item, overlap in zip(ranked, overlaps)
                if overlap == max_overlap
            ]

    # La cuota ``top_k`` es un máximo, no una obligación. Sin este filtro se
    # completaba la cuota con trámites distintos que apenas compartían palabras
    # genéricas con la consulta.
    # Solo se admiten secciones cuya relevancia sea muy cercana a la mejor.
    # Un umbral permisivo incluía "Cambio de contraseña" (0.694) junto con
    # "Foto de perfil" (0.793), porque ambas mencionan el icono de perfil.
    # Los chunks que completan la sección ganadora se incorporan después como
    # siblings, por lo que este corte no trunca sus pasos o requisitos.
    relative_threshold = (
        ranked[0][1] * 0.90 if ranked else COMPLEX_RELEVANCE_THRESHOLD
    )
    effective_threshold = max(COMPLEX_RELEVANCE_THRESHOLD, relative_threshold)
    anchors = [
        (document, score)
        for document, score in ranked
        if score >= effective_threshold
    ]

    # Un resultado que cae dentro de una sección Markdown debe aportar la
    # sección completa. Así no se pierden requisitos ubicados en el chunk
    # contiguo ni se completa la cuota con otro trámite.
    all_chunks = get_chunked_documents()
    selected: List[tuple[Document, float]] = []
    selected_ids: set[str] = set()
    for anchor, score in anchors:
        section_index = anchor.metadata.get("section_index")
        if section_index is None:
            siblings = [anchor]
        else:
            siblings = sorted(
                (
                    chunk
                    for chunk in all_chunks
                    if chunk.metadata.get("source") == anchor.metadata.get("source")
                    and chunk.metadata.get("page") == anchor.metadata.get("page")
                    and chunk.metadata.get("section_index") == section_index
                ),
                key=lambda chunk: int(chunk.metadata.get("chunk_index", 0)),
            )
        for sibling in siblings:
            chunk_id = str(sibling.metadata.get("chunk_id", ""))
            if chunk_id in selected_ids:
                continue
            selected.append((sibling, score))
            selected_ids.add(chunk_id)
            if len(selected) >= top_k:
                return selected

    return selected


def retrieve_context(query: str, top_k: int = COMPLEX_RETRIEVAL_TOP_K) -> str:
    """Recupera contexto relevante como texto consolidado."""
    if not (query or "").strip():
        return "Contexto recuperado: no se recibio una consulta valida."

    selected = _get_ranked_documents(query, top_k)
    if not selected:
        return "Contexto recuperado: no se encontraron fragmentos relevantes."

    lines: List[str] = ["# Contexto recuperado", ""]
    for index, (doc, score) in enumerate(selected, start=1):
        meta = doc.metadata or {}
        lines.append(f"## Fragmento {index}")
        lines.append(f"Fuente: {meta.get('source_title', 'Desconocida')}")
        lines.append(f"Documento: {meta.get('doc_id', 'N/A')}")
        lines.append(f"Chunk: {meta.get('chunk_id', 'N/A')}")
        lines.append(f"Score heuristico: {score:.3f}")
        lines.append("")
        lines.append(doc.page_content.strip())
        lines.append("")

    return "\n".join(lines).strip()


def retrieve_documents(
    query: str,
    top_k: int = COMPLEX_RETRIEVAL_TOP_K,
) -> List[Document]:
    """Devuelve solo los Document recuperados, sin consolidarlos."""
    return [doc for doc, _score in _get_ranked_documents(query, top_k)]


def get_corpus_stats() -> Dict[str, Any]:
    """Devuelve estadisticas utiles para visualizacion o tests."""
    docs = load_complex_documents()
    chunks = get_chunked_documents()
    return {
        "documents": len(docs),
        "chunks": len(chunks),
        "chunk_size": COMPLEX_CHUNK_SIZE,
        "chunk_overlap": COMPLEX_CHUNK_OVERLAP,
        "embedding_model": EMBEDDING_MODEL_NAME,
        "documents_meta": [doc.metadata for doc in docs],
    }
