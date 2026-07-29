"""API pública del pipeline RAG del Agente Corporativo IA.

El módulo se mantiene como fachada para no romper imports existentes:
- agent_system.tools importa retrieve_context
- scripts/data/initialize_complex_vector_store.py importa las funciones de carga
- tests/test_persistence.py valida recuperación y persistencia
"""

from __future__ import annotations

from typing import Any, Dict, List

from langchain_core.documents import Document

from rag.config import CHUNK_OVERLAP, CHUNK_SIZE, EMBEDDING_MODEL_NAME
from rag.documents import get_chunked_documents, load_complex_documents
from rag.ranking import rerank_documents
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
    candidate_k = max(top_k * 2, top_k)
    candidates = vector_store.similarity_search(clean_query, k=candidate_k)
    return rerank_documents(clean_query, candidates)[:top_k]


def retrieve_context(query: str, top_k: int = 3) -> str:
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


def retrieve_documents(query: str, top_k: int = 3) -> List[Document]:
    """Devuelve solo los Document recuperados, sin consolidarlos."""
    return [doc for doc, _score in _get_ranked_documents(query, top_k)]


def get_corpus_stats() -> Dict[str, Any]:
    """Devuelve estadisticas utiles para visualizacion o tests."""
    docs = load_complex_documents()
    chunks = get_chunked_documents()
    return {
        "documents": len(docs),
        "chunks": len(chunks),
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "embedding_model": EMBEDDING_MODEL_NAME,
        "documents_meta": [doc.metadata for doc in docs],
    }


if __name__ == "__main__":
    sample_query = "Que dice la politica sobre accesos a bases de datos y sanitizacion?"
    print(retrieve_context(sample_query, top_k=2))
