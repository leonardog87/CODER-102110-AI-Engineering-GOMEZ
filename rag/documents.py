"""Carga y segmentación de los manuales complejos."""

from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag.config import COMPLEX_CHUNK_OVERLAP, COMPLEX_CHUNK_SIZE, COMPLEX_MANUALS_PATH

SUPPORTED_EXTENSIONS = {".pdf", ".md", ".txt"}


def _source_files() -> List[Path]:
    """Devuelve los archivos admitidos en un orden reproducible."""
    if not COMPLEX_MANUALS_PATH.exists():
        raise FileNotFoundError(
            f"No existe la carpeta de manuales complejos: {COMPLEX_MANUALS_PATH}"
        )

    return sorted(
        path
        for path in COMPLEX_MANUALS_PATH.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def _base_metadata(path: Path) -> dict:
    return {
        "source": path.relative_to(COMPLEX_MANUALS_PATH).as_posix(),
        "source_title": path.stem,
        "document_type": path.suffix.lower().lstrip("."),
    }


def _read_pdf(path: Path) -> List[Document]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("Se necesita la dependencia 'pypdf' para leer PDF.") from exc

    metadata = _base_metadata(path)
    documents: List[Document] = []
    for page_number, page in enumerate(PdfReader(str(path)).pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            documents.append(
                Document(
                    page_content=text,
                    metadata={**metadata, "page": page_number},
                )
            )
    return documents


def _read_text(path: Path) -> List[Document]:
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return []
    if path.suffix.lower() == ".md":
        sections = re.split(r"(?=^###\s+)", text, flags=re.MULTILINE)
        return [
            Document(
                page_content=section.strip(),
                metadata={
                    **_base_metadata(path),
                    "page": 1,
                    "section_index": section_index,
                },
            )
            for section_index, section in enumerate(sections, start=1)
            if section.strip()
        ]
    return [
        Document(
            page_content=text,
            metadata={**_base_metadata(path), "page": 1},
        )
    ]


@lru_cache(maxsize=1)
def load_complex_documents() -> List[Document]:
    """Carga PDF, Markdown y texto plano desde manuales_complejos."""
    documents: List[Document] = []
    for path in _source_files():
        documents.extend(_read_pdf(path) if path.suffix.lower() == ".pdf" else _read_text(path))

    if not documents:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(
            f"No hay archivos con texto en {COMPLEX_MANUALS_PATH}. "
            f"Formatos admitidos: {supported}."
        )
    return documents


@lru_cache(maxsize=1)
def get_chunked_documents() -> List[Document]:
    """Segmenta los manuales y asigna identificadores reproducibles."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=COMPLEX_CHUNK_SIZE,
        chunk_overlap=COMPLEX_CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks: List[Document] = []

    for document in load_complex_documents():
        for chunk_index, chunk in enumerate(
            splitter.split_documents([document]),
            start=1,
        ):
            source_key = (
                f"{document.metadata['source']}:{document.metadata['page']}:"
                f"{document.metadata.get('section_index', 0)}:{chunk_index}"
            )
            chunk.metadata = {
                **chunk.metadata,
                "chunk_index": chunk_index,
                "chunk_id": hashlib.sha256(source_key.encode("utf-8")).hexdigest(),
            }
            chunks.append(chunk)

    return chunks
