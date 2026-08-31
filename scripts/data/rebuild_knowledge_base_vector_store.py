#!/usr/bin/env python3
"""Recrea desde cero el índice vectorial de knowledge_base."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.data.rebuild_knowledge_vector_store import rebuild_knowledge_chromadb


if __name__ == "__main__":
    raise SystemExit(0 if rebuild_knowledge_chromadb() else 1)
