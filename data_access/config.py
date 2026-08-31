"""Configuración compartida para el acceso a datos."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chatBot.data_access")

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _project_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


SQLITE_DB_PATH = _project_path(os.getenv("CHATBOT_DB", "data/chatBot.sqlite3"))
