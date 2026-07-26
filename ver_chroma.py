#!/usr/bin/env python3
"""
Script para ver el contenido completo de ChromaDB
"""

import os
import json
import numpy as np
from pathlib import Path
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

load_dotenv()

# Configurar ruta
CHROMA_PERSIST_DIR = os.getenv(
    "CHROMA_PERSIST_DIR",
    "./manuales_complejos_chroma_db",
)

print("=" * 70)
print(f"📂 Conectando a ChromaDB en: {CHROMA_PERSIST_DIR}")
print("=" * 70)

# Conectar
client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)

# Listar colecciones
collections = client.list_collections()
print(f"\n📚 Colecciones encontradas: {len(collections)}")

if not collections:
    print("❌ No hay colecciones en ChromaDB")
    exit()

for col in collections:
    print("\n" + "=" * 70)
    print(f"📊 COLECCIÓN: {col.name}")
    print("=" * 70)
    
    # Obtener conteo
    count = col.count()
    print(f"\n📝 Total de documentos: {count}")
    
    if count == 0:
        print("   (vacía)")
        continue
    
    # Obtener TODOS los documentos
    print("\n📄 CONTENIDO COMPLETO:")
    print("-" * 70)
    
    try:
        # Obtener todos los documentos
        results = col.get(
            include=["documents", "metadatas"]  # ❌ Quitamos "embeddings" para evitar el error
        )
        
        if not results or not results.get('ids'):
            print("No se pudieron recuperar los documentos")
            continue
        
        # Mostrar cada documento
        for i, doc_id in enumerate(results['ids'], 1):
            print(f"\n📌 DOCUMENTO {i}: {doc_id}")
            print("-" * 50)
            
            # Metadatos
            if results.get('metadatas') and i <= len(results['metadatas']):
                metadata = results['metadatas'][i-1]
                print(f"📋 METADATOS:")
                for key, value in metadata.items():
                    print(f"   {key}: {value}")
            
            # Contenido
            if results.get('documents') and i <= len(results['documents']):
                content = results['documents'][i-1]
                print(f"\n📝 CONTENIDO:")
                # Mostrar primeras 500 líneas
                lines = content.split('\n')
                for line in lines[:20]:  # Mostrar hasta 20 líneas
                    if line.strip():
                        print(f"   {line}")
                if len(lines) > 20:
                    print(f"   ... y {len(lines) - 20} líneas más")
            
            print("-" * 50)
        
        print(f"\n✅ Total mostrado: {len(results['ids'])} documentos")
        
        # Resumen
        print("\n" + "=" * 70)
        print("📊 RESUMEN:")
        print(f"   - Total documentos: {len(results['ids'])}")
        print(f"   - Con metadatos: {len(results.get('metadatas', []))}")
        
        # Mostrar todos los títulos
        print("\n📋 LISTA DE DOCUMENTOS GUARDADOS:")
        for i, meta in enumerate(results.get('metadatas', []), 1):
            title = meta.get('source_title', 'Sin título')
            doc_id = meta.get('doc_id', 'Sin ID')
            chunk_id = meta.get('chunk_id', '')
            print(f"   {i}. {title} - {chunk_id}")
        
    except Exception as e:
        print(f"❌ Error al obtener datos: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 70)
print("✅ Verificación completada")
