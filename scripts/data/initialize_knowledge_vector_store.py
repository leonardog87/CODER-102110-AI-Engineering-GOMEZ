#!/usr/bin/env python3
"""Inicializa la base vectorial persistente de knowledge_base."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("initialize_knowledge_vector_store")


def init_knowledge_chromadb() -> bool:
    try:
        from rag.knowledge_pipeline import get_knowledge_stats
        from rag.knowledge_vector_store import get_knowledge_vector_store

        vector_store = get_knowledge_vector_store()
        stats = get_knowledge_stats()
        count = vector_store._collection.count()

        logger.info("Base vectorial de conocimiento inicializada.")
        logger.info("PDF: %s", ", ".join(stats["sources"]))
        logger.info("Paginas con texto: %s", stats["pages"])
        logger.info("Chunks cargados: %s", count)
        logger.info("Directorio: %s", stats["persist_directory"])
        logger.info("Coleccion: %s", stats["collection_name"])
        return True
    except Exception:
        logger.exception("No se pudo inicializar la base vectorial de conocimiento.")
        return False


if __name__ == "__main__":
    sys.exit(0 if init_knowledge_chromadb() else 1)
