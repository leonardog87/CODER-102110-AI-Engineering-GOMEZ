"""Configuración compartida para el acceso a datos."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agente_corporativo.mcp.server")

EMPLEADOS_CSV_PATH = Path(os.getenv("EMPLEADOS_CSV", "raw_data/empleados.csv"))
SQLITE_DB_PATH = Path(
    os.getenv("AGENTE_CORPORATIVO_DB", "data/agente_corporativo.sqlite3")
)

ALLOWED_TABLES = {"empleados"}
