#!/usr/bin/env python3
"""Muestra los fragmentos guardados en la base Chroma de manuales simples."""

from __future__ import annotations

import os

import chromadb
from dotenv import load_dotenv


def ver_chroma_manuales_simples() -> None:
    """Lista colecciones, metadatos y texto de los manuales simples."""
    load_dotenv()
    persist_directory = os.getenv(
        "KNOWLEDGE_CHROMA_PERSIST_DIR",
        "./manuales_simples_chroma_db",
    )

    print("=" * 70)
    print(f"Base Chroma de manuales simples: {persist_directory}")
    print("=" * 70)

    client = chromadb.PersistentClient(path=persist_directory)
    collections = client.list_collections()

    if not collections:
        print("No se encontraron colecciones.")
        return

    for collection in collections:
        print(f"\nColección: {collection.name}")
        print(f"Total de fragmentos: {collection.count()}")

        results = collection.get(include=["documents", "metadatas"])
        ids = results.get("ids") or []
        documents = results.get("documents") or []
        metadatas = results.get("metadatas") or []

        for index, document_id in enumerate(ids):
            metadata = metadatas[index] if index < len(metadatas) else {}
            content = documents[index] if index < len(documents) else ""

            print("\n" + "-" * 70)
            print(f"Fragmento {index + 1}: {document_id}")
            print(f"Fuente: {metadata.get('source', 'Desconocida')}")
            print(f"Título: {metadata.get('source_title', 'Desconocido')}")
            print(f"Página: {metadata.get('page', 'N/A')}")
            print(f"Índice del chunk: {metadata.get('chunk_index', 'N/A')}")
            print("\nContenido:")
            print(content)

    print("\n" + "=" * 70)
    print("Verificación completada.")


if __name__ == "__main__":
    ver_chroma_manuales_simples()
