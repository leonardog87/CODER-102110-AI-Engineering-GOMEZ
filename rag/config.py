"""Configuracion compartida del pipeline RAG."""

from __future__ import annotations

import logging
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _project_path(value: str) -> Path:
    """Resuelve rutas relativas contra la raíz, no contra el proceso actual."""
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


EMBEDDING_MODEL_NAME = os.getenv(
    "RAG_EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)

COMPLEX_CHUNK_SIZE = int(os.getenv("COMPLEX_CHUNK_SIZE", "1000"))
COMPLEX_CHUNK_OVERLAP = int(os.getenv("COMPLEX_CHUNK_OVERLAP", "180"))
COMPLEX_RETRIEVAL_TOP_K = int(os.getenv("COMPLEX_RETRIEVAL_TOP_K", "3"))
COMPLEX_RETRIEVAL_CANDIDATES = int(os.getenv("COMPLEX_RETRIEVAL_CANDIDATES", "12"))

KNOWLEDGE_CHUNK_SIZE = int(os.getenv("KNOWLEDGE_CHUNK_SIZE", "600"))
KNOWLEDGE_CHUNK_OVERLAP = int(os.getenv("KNOWLEDGE_CHUNK_OVERLAP", "100"))
KNOWLEDGE_RETRIEVAL_TOP_K = int(os.getenv("KNOWLEDGE_RETRIEVAL_TOP_K", "2"))
KNOWLEDGE_RETRIEVAL_CANDIDATES = int(
    os.getenv("KNOWLEDGE_RETRIEVAL_CANDIDATES", "6")
)

COMPLEX_RELEVANCE_THRESHOLD = float(
    os.getenv("COMPLEX_RELEVANCE_THRESHOLD", "0.15")
)
KNOWLEDGE_RELEVANCE_THRESHOLD = float(
    os.getenv("KNOWLEDGE_RELEVANCE_THRESHOLD", "0.30")
)

COMPLEX_MANUALS_PATH = _project_path(
    os.getenv("COMPLEX_MANUALS_PATH", "./manuales_complejos")
)
CHROMA_PERSIST_DIR = str(
    _project_path(
        os.getenv("CHROMA_PERSIST_DIR", "./manuales_complejos_chroma_db")
    )
)
CHROMA_COLLECTION_NAME = os.getenv(
    "CHROMA_COLLECTION_NAME",
    "manuales_complejos",
)

KNOWLEDGE_BASE_PATH = _project_path(
    os.getenv("KNOWLEDGE_BASE_PATH", "./knowledge_base")
)
KNOWLEDGE_CHROMA_PERSIST_DIR = str(
    _project_path(
        os.getenv(
            "KNOWLEDGE_CHROMA_PERSIST_DIR",
            "./manuales_simples_chroma_db",
        )
    )
)
KNOWLEDGE_CHROMA_COLLECTION_NAME = os.getenv(
    "KNOWLEDGE_CHROMA_COLLECTION_NAME",
    "manuales_simples",
)

Path(CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
Path(KNOWLEDGE_CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
COMPLEX_MANUALS_PATH.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("agente_corporativo.rag.pipeline")
