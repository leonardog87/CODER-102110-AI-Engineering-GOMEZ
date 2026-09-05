"""Reranking heuristico para resultados RAG."""

from __future__ import annotations

import re
import unicodedata
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
    # Las consultas de usuarios suelen omitir tildes. Normalizarlas permite
    # que "guarderia" coincida con "guardería" y "como" con "cómo".
    decomposed = unicodedata.normalize("NFKD", text.lower())
    normalized_text = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    tokens = re.findall(r"[a-z0-9]+", normalized_text)
    normalized: List[str] = []
    suffixes = (
        "amiento", "imiento", "aciones", "acion", "mente", "ando", "iendo",
        "ieron", "ieron", "ar", "er", "ir", "as", "es", "os", "a", "e", "o",
    )
    for token in tokens:
        if token in STOPWORDS or len(token) <= 2:
            continue
        normalized.append(token)
        for suffix in suffixes:
            if len(token) > len(suffix) + 3 and token.endswith(suffix):
                normalized.append(token[: -len(suffix)])
                break
    return normalized


def rerank_documents(
    query: str,
    docs: List[Document],
    vector_scores: List[float] | None = None,
) -> List[Tuple[Document, float]]:
    """Combina similitud vectorial, coincidencia léxica y continuidad temática."""
    query_tokens = set(_tokenize(query))

    if not query_tokens:
        return [(doc, 1.0 / (index + 1)) for index, doc in enumerate(docs)]

    ranked: List[Tuple[Document, float]] = []
    for index, doc in enumerate(docs):
        text_tokens = set(_tokenize(doc.page_content))
        overlap = len(query_tokens & text_tokens)
        coverage = overlap / max(len(query_tokens), 1)
        frequency = sum(
            _tokenize(doc.page_content).count(token) for token in query_tokens
        )
        frequency_bonus = min(frequency / 100, 0.08)

        normalized_query = " ".join(_tokenize(query))
        normalized_text = " ".join(_tokenize(doc.page_content))
        phrase_bonus = 0.10 if normalized_query in normalized_text else 0.0

        title = f"{doc.metadata.get('source_title', '')} {doc.metadata.get('category', '')}"
        title_bonus = 0.10 if query_tokens & set(_tokenize(title)) else 0.0
        position_bonus = 1.0 / (index + 1)
        vector_score = (
            vector_scores[index]
            if vector_scores is not None and index < len(vector_scores)
            else position_bonus
        )
        final_score = (
            (vector_score * 0.25)
            + (coverage * 0.55)
            + frequency_bonus
            + phrase_bonus
            + title_bonus
            + (position_bonus * 0.02)
        )

        ranked.append((doc, final_score))

    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked
