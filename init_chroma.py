#!/usr/bin/env python3
"""
Script para inicializar ChromaDB con los documentos RAG.
"""

import os
import sys
import logging
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("init_chroma")

def init_chromadb():
    """Inicializa ChromaDB con los documentos RAG."""
    try:
        # ✅ CORREGIDO: importar desde la raíz
        from rag.pipeline import get_vector_store, get_corpus_stats
        
        logger.info("🚀 Inicializando ChromaDB...")
        
        # Esto forzará la creación y persistencia
        vector_store = get_vector_store()
        stats = get_corpus_stats()
        
        # Verificar que se guardó
        if hasattr(vector_store, 'persist'):
            vector_store.persist()
            logger.info("💾 Persistencia forzada")
        
        logger.info("✅ ChromaDB inicializada correctamente")
        logger.info(f"📊 Estadísticas:")
        logger.info(f"   - Documentos: {stats['documents']}")
        logger.info(f"   - Chunks: {stats['chunks']}")
        logger.info(f"   - Directorio: {os.getenv('CHROMA_PERSIST_DIR', './manuales_complejos_chroma_db')}")
        logger.info(f"   - Colección: {os.getenv('CHROMA_COLLECTION_NAME', 'manuales_complejos')}")
        
        # Verificar contenido
        try:
            import chromadb
            client = chromadb.PersistentClient(
                path=os.getenv(
                    'CHROMA_PERSIST_DIR',
                    './manuales_complejos_chroma_db',
                )
            )
            collections = client.list_collections()
            logger.info(f"📚 Colecciones en ChromaDB: {[c.name for c in collections]}")
            for col in collections:
                count = col.count()
                logger.info(f"   - {col.name}: {count} documentos")
        except Exception as e:
            logger.warning(f"⚠️ No se pudo verificar ChromaDB: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error inicializando ChromaDB: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = init_chromadb()
    sys.exit(0 if success else 1)
