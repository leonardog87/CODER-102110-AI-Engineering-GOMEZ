"""Carga y segmentación de los PDF almacenados en knowledge_base."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.config import CHUNK_OVERLAP, CHUNK_SIZE, KNOWLEDGE_BASE_PATH


def _pdf_files() -> List[Path]:
    """Devuelve los PDF de la base de conocimiento en orden estable."""
    if not KNOWLEDGE_BASE_PATH.exists():
        raise FileNotFoundError(
            f"No existe la carpeta de conocimiento: {KNOWLEDGE_BASE_PATH}"
        )
    return sorted(
        path
        for path in KNOWLEDGE_BASE_PATH.rglob("*")
        if path.is_file() and path.suffix.lower() == ".pdf"
    )


def _read_pdf(path: Path) -> List[Document]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError(
            "Se necesita la dependencia 'pypdf' para procesar knowledge_base."
        ) from exc

    reader = PdfReader(str(path))
    relative_path = path.relative_to(KNOWLEDGE_BASE_PATH).as_posix()
    documents: List[Document] = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            continue
        documents.append(
            Document(
                page_content=text,
                metadata={
                    "source": relative_path,
                    "source_title": path.stem,
                    "page": page_number,
                    "document_type": "pdf",
                },
            )
        )

    return documents


@lru_cache(maxsize=1)
def load_knowledge_documents() -> List[Document]:
    """Extrae el texto de todos los PDF disponibles."""
    return [document for path in _pdf_files() for document in _read_pdf(path)]


@lru_cache(maxsize=1)
def get_knowledge_chunks() -> List[Document]:
    """Segmenta las páginas y asigna identificadores reproducibles."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
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
