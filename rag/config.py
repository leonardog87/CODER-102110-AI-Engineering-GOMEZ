"""Configuración de la única fuente RAG: knowledge_base."""

from __future__ import annotations

import logging
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _project_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


EMBEDDING_MODEL_NAME = os.getenv(
    "RAG_EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)
SEMANTIC_SEARCH_ENABLED = os.getenv(
    "RAG_SEMANTIC_SEARCH_ENABLED", "false"
).strip().lower() in {"1", "true", "yes", "on", "si", "sí"}

KNOWLEDGE_CHUNK_SIZE = int(os.getenv("KNOWLEDGE_CHUNK_SIZE", "600"))
KNOWLEDGE_CHUNK_OVERLAP = int(os.getenv("KNOWLEDGE_CHUNK_OVERLAP", "100"))
KNOWLEDGE_RETRIEVAL_TOP_K = int(os.getenv("KNOWLEDGE_RETRIEVAL_TOP_K", "3"))
KNOWLEDGE_RETRIEVAL_CANDIDATES = int(
    os.getenv("KNOWLEDGE_RETRIEVAL_CANDIDATES", "8")
)
KNOWLEDGE_RELEVANCE_THRESHOLD = float(
    os.getenv("KNOWLEDGE_RELEVANCE_THRESHOLD", "0.20")
)

KNOWLEDGE_BASE_PATH = _project_path(
    os.getenv("KNOWLEDGE_BASE_PATH", "./knowledge_base")
)
KNOWLEDGE_CHROMA_PERSIST_DIR = str(
    _project_path(
        os.getenv("KNOWLEDGE_CHROMA_PERSIST_DIR", "./knowledge_base_chroma_db")
    )
)
KNOWLEDGE_CHROMA_COLLECTION_NAME = os.getenv(
    "KNOWLEDGE_CHROMA_COLLECTION_NAME", "knowledge_base"
)

KNOWLEDGE_BASE_PATH.mkdir(parents=True, exist_ok=True)
Path(KNOWLEDGE_CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("chatBot.rag")
