"""Reranking heuristico para resultados RAG."""

from __future__ import annotations

import re
from typing import List, Tuple

from langchain_core.documents import Document

STOPWORDS = {
    "de",
    "la",
    "el",
    "y",
    "o",
    "a",
    "en",
    "un",
    "una",
    "los",
    "las",
    "del",
    "por",
    "para",
    "con",
    "sin",
    "que",
    "se",
    "al",
    "lo",
    "su",
    "sus",
    "es",
    "son",
    "como",
    "mas",
    "menos",
    "sobre",
    "cuando",
    "si",
    "no",
}


def _tokenize(text: str) -> List[str]:
    tokens = re.findall(r"[a-záéíóúñ0-9]+", text.lower())
    return [token for token in tokens if token not in STOPWORDS and len(token) > 2]


def rerank_documents(query: str, docs: List[Document]) -> List[Tuple[Document, float]]:
    """Ordena documentos recuperados usando una heuristica simple."""
    query_tokens = set(_tokenize(query))

    if not query_tokens:
        return [(doc, 1.0 / (index + 1)) for index, doc in enumerate(docs)]

    ranked: List[Tuple[Document, float]] = []
    for index, doc in enumerate(docs):
        text_tokens = set(_tokenize(doc.page_content))
        overlap = len(query_tokens & text_tokens)
        coverage = overlap / max(len(query_tokens), 1)

        title = f"{doc.metadata.get('source_title', '')} {doc.metadata.get('category', '')}"
        title_bonus = 0.15 if query_tokens & set(_tokenize(title)) else 0.0
        position_bonus = 1.0 / (index + 1)
        final_score = (coverage * 0.7) + title_bonus + (position_bonus * 0.05)

        ranked.append((doc, final_score))

    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked
