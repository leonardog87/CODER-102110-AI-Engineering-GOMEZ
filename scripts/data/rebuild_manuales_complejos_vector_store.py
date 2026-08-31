#!/usr/bin/env python3
"""Recrea desde cero el índice vectorial de manuales_complejos."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.data.rebuild_complex_vector_store import recrear_manuales_complejos_chroma


if __name__ == "__main__":
    raise SystemExit(0 if recrear_manuales_complejos_chroma() else 1)
