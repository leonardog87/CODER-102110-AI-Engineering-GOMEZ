"""Configuracion compartida del pipeline RAG."""

from __future__ import annotations

import logging
import os
from pathlib import Path

EMBEDDING_MODEL_NAME = os.getenv(
    "RAG_EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)

CHUNK_SIZE = 850
CHUNK_OVERLAP = 150

COMPLEX_MANUALS_PATH = Path(
    os.getenv("COMPLEX_MANUALS_PATH", "./manuales_complejos")
)
CHROMA_PERSIST_DIR = os.getenv(
    "CHROMA_PERSIST_DIR",
    "./manuales_complejos_chroma_db",
)
CHROMA_COLLECTION_NAME = os.getenv(
    "CHROMA_COLLECTION_NAME",
    "manuales_complejos",
)

KNOWLEDGE_BASE_PATH = Path(os.getenv("KNOWLEDGE_BASE_PATH", "./knowledge_base"))
KNOWLEDGE_CHROMA_PERSIST_DIR = os.getenv(
    "KNOWLEDGE_CHROMA_PERSIST_DIR",
    "./manuales_simples_chroma_db",
)
KNOWLEDGE_CHROMA_COLLECTION_NAME = os.getenv(
    "KNOWLEDGE_CHROMA_COLLECTION_NAME",
    "manuales_simples",
)

Path(CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
Path(KNOWLEDGE_CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
COMPLEX_MANUALS_PATH.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("agente_corporativo.rag.pipeline")
