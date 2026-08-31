"""Carga y segmentación de las fuentes editables de knowledge_base."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from rag.config import KNOWLEDGE_BASE_PATH, KNOWLEDGE_CHUNK_OVERLAP, KNOWLEDGE_CHUNK_SIZE

SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf"}


def _source_files() -> List[Path]:
    """Devuelve las fuentes de texto canónicas en orden estable."""
    if not KNOWLEDGE_BASE_PATH.exists():
        raise FileNotFoundError(
            f"No existe la carpeta de conocimiento: {KNOWLEDGE_BASE_PATH}"
        )
    return sorted(
        path
        for path in KNOWLEDGE_BASE_PATH.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def _read_text(path: Path) -> List[Document]:
    if path.suffix.lower() == ".pdf":
        relative_path = path.relative_to(KNOWLEDGE_BASE_PATH).as_posix()
        return [
            Document(
                page_content=text,
                metadata={
                    "source": relative_path,
                    "source_title": path.stem,
                    "page": page_number,
                    "document_type": "pdf",
                },
            )
            for page_number, page in enumerate(PdfReader(str(path)).pages, start=1)
            if (text := (page.extract_text() or "").strip())
        ]
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return []
    relative_path = path.relative_to(KNOWLEDGE_BASE_PATH).as_posix()
    return [
        Document(
            page_content=text,
            metadata={
                "source": relative_path,
                "source_title": path.stem,
                "page": 1,
                "document_type": path.suffix.lower().lstrip("."),
            },
        )
    ]


@lru_cache(maxsize=1)
def load_knowledge_documents() -> List[Document]:
    """Carga las fuentes editables que alimentan el índice simple."""
    documents = [
        document for path in _source_files() for document in _read_text(path)
    ]
    if not documents:
        raise ValueError(
            f"No hay fuentes {sorted(SUPPORTED_EXTENSIONS)} en {KNOWLEDGE_BASE_PATH}."
        )
    return documents


@lru_cache(maxsize=1)
def get_knowledge_chunks() -> List[Document]:
    """Segmenta las páginas y asigna identificadores reproducibles."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=KNOWLEDGE_CHUNK_SIZE,
        chunk_overlap=KNOWLEDGE_CHUNK_OVERLAP,
        separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " ", ""],
    )
    chunks: List[Document] = []

    for document in load_knowledge_documents():
        for chunk_index, chunk in enumerate(
            splitter.split_documents([document]),
            start=1,
        ):
            source_key = (
                f"{chunk.metadata['source']}:{chunk.metadata['page']}:{chunk_index}"
            )
            chunk.metadata = {
                **chunk.metadata,
                "chunk_index": chunk_index,
                "chunk_id": hashlib.sha256(source_key.encode("utf-8")).hexdigest(),
            }
            chunks.append(chunk)

    return chunks
