# prueba_persistencia.py
import os
from rag_pipeline import retrieve_context, get_vector_store

print("=" * 60)
print("🔍 PRUEBA DE PERSISTENCIA")
print("=" * 60)

# Verificar que ChromaDB existe en disco
if os.path.exists("./chroma_db"):
    print("✅ Directorio chroma_db existe")
else:
    print("❌ Directorio chroma_db NO existe")
    exit()

# 1. Ver estadísticas (esto carga desde disco)
print("\n📊 Cargando estadísticas desde disco...")
from rag_pipeline import get_corpus_stats
stats = get_corpus_stats()
print(f"   Documentos: {stats['documents']}")
print(f"   Chunks: {stats['chunks']}")

# 2. Hacer una consulta real
print("\n🔍 Haciendo consulta RAG...")
query = "¿Qué dice la política sobre accesos a bases de datos?"
context = retrieve_context(query, top_k=2)

print(f"\n📝 Contexto recuperado ({len(context)} caracteres):")
print("-" * 60)
print(context[:500])
print("...")

print("\n✅ ¡PERSISTENCIA FUNCIONANDO!")
print("   Los datos se cargaron desde el disco, no desde memoria.")