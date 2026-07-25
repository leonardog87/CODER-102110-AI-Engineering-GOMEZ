"""rag_pipeline.py

Ciudad Analítica — Módulo 1
Pipeline de RAG + base documental simulada.

Este archivo está pensado con un objetivo pedagógico: mostrar, de forma
simple y trazable, cómo construir una base de conocimiento estática que
pueda ser consultada por agentes sin necesidad de llamar a un LLM.

Flujo general:
1) Se definen documentos mock en Markdown.
2) Se dividen en chunks con RecursiveCharacterTextSplitter.
3) Se convierten a embeddings con HuggingFaceEmbeddings.
4) Se almacenan en un vector store local (FAISS / Chroma / fallback en memoria).
5) Se recupera contexto relevante con similarity search.
6) Se aplica un reranking heurístico simple para reforzar la demo educativa.

Importante:
- No hay generación de texto por LLM en este módulo.
- La salida de retrieve_context(...) es un bloque consolidado y listo para
  ser usado por otro componente/orquestador.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List, Tuple

import os
import re
import logging

from pathlib import Path
from langchain_chroma import Chroma

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# LangChain recomienda usar el paquete moderno langchain-huggingface para
# embeddings con Hugging Face.
try:
    from langchain_huggingface import HuggingFaceEmbeddings
except Exception:  # pragma: no cover - fallback defensivo para entornos viejos
    from langchain_community.embeddings import HuggingFaceEmbeddings  # type: ignore

# Vector stores: intentamos primero FAISS, luego Chroma, y finalmente un
# vector store en memoria como fallback para máxima portabilidad.
try:
    from langchain_community.vectorstores import FAISS
except Exception:  # pragma: no cover
    FAISS = None  # type: ignore

try:
    from langchain_chroma import Chroma
except Exception:  # pragma: no cover
    Chroma = None  # type: ignore

try:
    from langchain_core.vectorstores import InMemoryVectorStore
except Exception:  # pragma: no cover
    InMemoryVectorStore = None  # type: ignore


# -----------------------------------------------------------------------------
# 1) Documentos mock (base de conocimiento estática)
# -----------------------------------------------------------------------------
#
# Cada documento simula una pieza de conocimiento interna de la empresa.
# Están escritos en Markdown para que el splitter pueda trabajar sobre un texto
# relativamente natural y con estructura pedagógica.
# -----------------------------------------------------------------------------
MOCK_DOCUMENTS: List[Dict[str, str]] = [
    {
        "doc_id": "aws-security-policy",
        "title": "Manual de Políticas de Seguridad en la Nube (AWS)",
        "category": "security",
        "content": """
# Manual de Políticas de Seguridad en la Nube (AWS)

## Objetivo
Establecer lineamientos mínimos para operar infraestructura en AWS sin exponer
información sensible ni configuraciones críticas.

## Principios generales
- Aplicar el principio de privilegio mínimo en IAM.
- Utilizar MFA para accesos administrativos.
- Mantener separación entre ambientes: desarrollo, prueba y producción.
- Registrar eventos relevantes en CloudTrail y centralizar logs.
- Evitar credenciales embebidas en código fuente.

## Controles obligatorios
1. Las claves de acceso no deben compartirse por correo ni mensajería.
2. Los buckets S3 con datos internos deben tener acceso privado por defecto.
3. Las instancias EC2 con servicios sensibles deben estar protegidas por SG
   restrictivos y grupos de seguridad revisados periódicamente.
4. Las bases de datos deben usar cifrado en reposo y en tránsito.
5. Los secretos deben almacenarse en un gestor dedicado, nunca en archivos de
   configuración planos.

## Respuesta ante incidentes
- Rotar credenciales afectadas.
- Revisar logs de acceso.
- Registrar el incidente con hora, alcance y sistemas impactados.
- Notificar al responsable de seguridad.

## Buenas prácticas de auditoría
- Revisar permisos de IAM cada 30 días.
- Validar que no existan roles con acceso excesivo.
- Verificar que los recursos expuestos a internet estén justificados.
""",
    },
    {
        "doc_id": "network-troubleshooting",
        "title": "Guía de Resolución de Problemas Comunes de Red",
        "category": "network",
        "content": """
# Guía de Resolución de Problemas Comunes de Red

## Objetivo
Ayudar al equipo de soporte a identificar fallas típicas de conectividad,
latencia y resolución de nombres.

## Síntomas frecuentes
- El usuario no navega en internet.
- La VPN conecta pero no accede a recursos internos.
- La aplicación responde lenta o con timeouts.
- No resuelve nombres DNS.

## Checklist de diagnóstico
1. Confirmar que el enlace físico esté activo.
2. Verificar dirección IP, máscara, gateway y DNS.
3. Probar conectividad con ping al gateway y a una IP externa.
4. Probar resolución DNS con herramientas de consulta.
5. Revisar proxy, firewall local y políticas de seguridad.
6. Evaluar saturación del enlace y latencia de salto intermedio.

## Problemas habituales y acciones
### 1. DNS incorrecto
Si el DNS está mal configurado, el usuario puede tener conectividad IP pero no
resolver dominios. Corregir la configuración y volver a probar.

### 2. VPN sin acceso interno
Revisar rutas, split tunneling, políticas del túnel y autenticación.

### 3. Timeouts intermitentes
Verificar jitter, pérdida de paquetes, congestión de red y balanceadores.

### 4. Puerto bloqueado
Comprobar reglas de firewall y ACLs de red.

## Evidencias recomendadas
- Captura de ipconfig / ifconfig.
- Resultado de ping y tracert.
- Estado de la VPN.
- Identificación del segmento afectado.
""",
    },
    {
        "doc_id": "db-access-policy",
        "title": "Normativas de Acceso a Bases de Datos y Manejo de Información Sensible",
        "category": "data-governance",
        "content": """
# Normativas de Acceso a Bases de Datos y Manejo de Información Sensible

## Objetivo
Definir reglas para consultar, administrar y proteger información de clientes.

## Alcance
Aplica a todo usuario, agente o servicio que interactúe con datos de clientes,
operaciones o información sensible.

## Reglas de acceso
- El acceso a datos críticos requiere autorización explícita.
- Toda consulta debe limitarse al mínimo necesario.
- No se permite exponer información financiera completa sin justificación.
- Los identificadores de cliente deben validarse antes de cualquier búsqueda.
- Los inputs de usuario deben sanitizarse para evitar inyección o consultas
  fuera de alcance.

## Información sensible
Se considera sensible cualquier dato que identifique al cliente, sus cuentas,
contratos, montos, claves, tokens o información privada de operación.

## Buenas prácticas
1. Registrar toda consulta administrativa.
2. Enmascarar valores sensibles en la salida.
3. Evitar devolver listas completas si el caso de uso pide un ID puntual.
4. No mezclar acceso de soporte básico con acceso administrativo.
5. Rechazar consultas ambiguas o fuera de contexto.

## Ejemplo de sanitización esperada
- ID válido: "CUST-1024"
- ID inválido: "CUST-1024; DROP TABLE clientes;"

## Política de respuesta
Si una consulta excede el alcance permitido, el sistema debe responder con una
negativa segura y sugerir el canal correcto.
""",
    },
]


# -----------------------------------------------------------------------------
# 2) Embeddings
# -----------------------------------------------------------------------------
#
# Se usa un modelo gratuito de Hugging Face. Este modelo es liviano y muy
# apropiado para demos educativas porque no requiere infraestructura propia.
# 
# Nota pedagógica: normalize_embeddings=True ayuda a que la similitud coseno
# funcione mejor en muchos escenarios de búsqueda semántica.
# -----------------------------------------------------------------------------
EMBEDDING_MODEL_NAME = os.getenv(
    "RAG_EMBEDDING_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    """Crea y cachea el objeto de embeddings.

    Caching:
    - Evita descargar/cargar el modelo múltiples veces.
    - Mejora la velocidad de respuesta de la demo.
    """
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_NAME,
        encode_kwargs={"normalize_embeddings": True},
    )


# -----------------------------------------------------------------------------
# 3) Chunking / división semántica aproximada
# -----------------------------------------------------------------------------
#
# RecursiveCharacterTextSplitter intenta cortar por separadores naturales
# (por ejemplo: dobles saltos de línea, saltos simples, espacios, etc.).
# Es un excelente punto de partida para RAG porque mantiene mejor la coherencia
# que un corte fijo arbitrario.
# -----------------------------------------------------------------------------
CHUNK_SIZE = 850
CHUNK_OVERLAP = 150


@lru_cache(maxsize=1)
def _get_text_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )


# -----------------------------------------------------------------------------
# 4) Construcción de documentos LangChain
# -----------------------------------------------------------------------------

def load_mock_documents() -> List[Document]:
    """Convierte la lista de diccionarios mock en Document objects.

    Cada documento lleva metadata para trazabilidad:
    - doc_id: identificador lógico
    - title: título legible
    - category: tipo de conocimiento
    """
    docs: List[Document] = []
    for item in MOCK_DOCUMENTS:
        docs.append(
            Document(
                page_content=item["content"].strip(),
                metadata={
                    "doc_id": item["doc_id"],
                    "title": item["title"],
                    "category": item["category"],
                },
            )
        )
    return docs


@lru_cache(maxsize=1)
def get_chunked_documents() -> List[Document]:
    """Aplica chunking a los documentos mock.

    Esto simula la etapa de ingestión documental de un RAG real.
    """
    splitter = _get_text_splitter()
    chunks: List[Document] = []

    for doc in load_mock_documents():
        doc_chunks = splitter.split_documents([doc])
        for i, chunk in enumerate(doc_chunks, start=1):
            # Agregamos metadata útil para observabilidad y trazabilidad.
            chunk.metadata = dict(chunk.metadata or {})
            chunk.metadata.update(
                {
                    "chunk_id": f"{doc.metadata['doc_id']}-chunk-{i}",
                    "chunk_index": i,
                    "source_title": doc.metadata["title"],
                }
            )
            chunks.append(chunk)

    return chunks


# -----------------------------------------------------------------------------
# 5) Vector store local
# -----------------------------------------------------------------------------
#
# Intentamos usar FAISS primero porque es un estándar muy conocido para demos.
# Si no está disponible, usamos Chroma en local. Si tampoco está instalado,
# caemos a InMemoryVectorStore para mantener la demo funcional con el mínimo
# de dependencias.
# -----------------------------------------------------------------------------

# ──────────────────────────────────────────────────────────────
# CONFIGURACIÓN DE LOGGING
# ──────────────────────────────────────────────────────────────
logger = logging.getLogger("ciudad_analitica.rag_pipeline")

# ──────────────────────────────────────────────────────────────
# CONFIGURACIÓN DE PERSISTENCIA
# ──────────────────────────────────────────────────────────────
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "ciudad_analitica_rag")

# Asegurar que el directorio existe
Path(CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)


def _build_vector_store(chunks: List[Document]):
    """
    Construye el vector store usando ChromaDB con persistencia.
    """
    embeddings = get_embeddings()
    
    # ─── USAR CHROMADB PERSISTENTE ───
    try:
        logger.info(f"📂 Inicializando ChromaDB en: {CHROMA_PERSIST_DIR}")
        
        # ✅ Usar from_documents para crear y persistir en un solo paso
        vector_store = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            persist_directory=CHROMA_PERSIST_DIR,
            collection_name=CHROMA_COLLECTION_NAME,
        )
        
        # ✅ Forzar persistencia
        if hasattr(vector_store, 'persist'):
            vector_store.persist()
            logger.info(f"✅ {len(chunks)} chunks guardados en ChromaDB")
        
        return vector_store
        
    except Exception as e:
        logger.warning(f"❌ Error con ChromaDB: {e}")
        logger.warning("🔄 Usando InMemoryVectorStore como fallback...")
        
        from langchain_core.vectorstores import InMemoryVectorStore
        store = InMemoryVectorStore(embedding=embeddings)
        store.add_documents(chunks)
        return store
        
    except Exception as e:
        logger.warning(f"❌ Error con ChromaDB: {e}")
        logger.warning("🔄 Usando InMemoryVectorStore como fallback...")
        
        # Fallback a InMemoryVectorStore
        from langchain_core.vectorstores import InMemoryVectorStore
        store = InMemoryVectorStore(embedding=embeddings)
        store.add_documents(chunks)
        return store


@lru_cache(maxsize=1)
def get_vector_store():
    """Construye el índice vectorial con persistencia en ChromaDB."""
    return _build_vector_store(get_chunked_documents())


# -----------------------------------------------------------------------------
# 6) Reranking básico (educativo)
# -----------------------------------------------------------------------------
#
# El vector search recupera candidatos semánticamente relevantes, pero en una
# demo educativa conviene añadir una segunda capa muy simple de ranking para
# explicar por qué algunos fragmentos quedan arriba.
#
# Este reranking NO usa LLM. Solo mezcla:
# - orden inicial de recuperación,
# - solapamiento léxico con la query,
# - bonus por coincidencias de términos importantes.
# -----------------------------------------------------------------------------

def _tokenize(text: str) -> List[str]:
    tokens = re.findall(r"[a-záéíóúñ0-9]+", text.lower())
    # Filtro mínimo de stopwords para que el score sea más útil en la demo.
    stopwords = {
        "de",
        "la",
        "el",
        "y",
        "o",
        "a",
        "en",
        "un",
        "una",
        "los",
        "las",
        "del",
        "por",
        "para",
        "con",
        "sin",
        "que",
        "se",
        "al",
        "lo",
        "su",
        "sus",
        "es",
        "son",
        "como",
        "más",
        "menos",
        "sobre",
        "cuando",
        "si",
        "no",
    }
    return [t for t in tokens if t not in stopwords and len(t) > 2]


def _rerank_documents(query: str, docs: List[Document]) -> List[Tuple[Document, float]]:
    """Ordena documentos recuperados usando una heurística simple.

    El score final es una mezcla de:
    - score por solapamiento de tokens,
    - bonus por términos clave de la query,
    - bonus por aparecer antes en la recuperación inicial.
    """
    query_tokens = set(_tokenize(query))
    ranked: List[Tuple[Document, float]] = []

    if not query_tokens:
        # Si la query está vacía o casi vacía, devolvemos el orden original.
        return [(doc, 1.0 / (idx + 1)) for idx, doc in enumerate(docs)]

    for idx, doc in enumerate(docs):
        text_tokens = set(_tokenize(doc.page_content))
        overlap = len(query_tokens & text_tokens)
        coverage = overlap / max(len(query_tokens), 1)

        # Bonus pequeño por presencia de palabras del título/categoría.
        title = str(doc.metadata.get("source_title", "")) + " " + str(doc.metadata.get("category", ""))
        title_tokens = set(_tokenize(title))
        title_bonus = 0.15 if query_tokens & title_tokens else 0.0

        # Bonus decreciente por el orden de recuperación inicial.
        position_bonus = 1.0 / (idx + 1)

        final_score = (coverage * 0.7) + title_bonus + (position_bonus * 0.05)
        ranked.append((doc, final_score))

    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked


# -----------------------------------------------------------------------------
# 7) API pública del módulo
# -----------------------------------------------------------------------------

def retrieve_context(query: str, top_k: int = 3) -> str:
    """Recupera contexto relevante como texto consolidado.

    Parámetros
    ----------
    query:
        Consulta del usuario o del agente.
    top_k:
        Número de fragmentos finales a devolver después del reranking.

    Retorna
    -------
    str
        Bloque de contexto listo para inyectarse en otro componente.
    """
    clean_query = (query or "").strip()
    if not clean_query:
        return "Contexto recuperado: no se recibió una consulta válida."

    vector_store = get_vector_store()

    # Recuperación inicial por similitud semántica.
    # Pedimos un poco más de resultados para que el reranking tenga material.
    candidate_k = max(top_k * 2, top_k)

    # La mayoría de los vector stores de LangChain soportan similarity_search.
    candidates = vector_store.similarity_search(clean_query, k=candidate_k)

    # Segunda capa: reranking didáctico.
    ranked = _rerank_documents(clean_query, candidates)
    selected = ranked[:top_k]

    if not selected:
        return "Contexto recuperado: no se encontraron fragmentos relevantes."

    # Consolidamos los fragmentos en un bloque claro y trazable.
    lines: List[str] = ["# Contexto recuperado", ""]
    for idx, (doc, score) in enumerate(selected, start=1):
        meta = doc.metadata or {}
        lines.append(f"## Fragmento {idx}")
        lines.append(f"Fuente: {meta.get('source_title', 'Desconocida')}")
        lines.append(f"Documento: {meta.get('doc_id', 'N/A')}")
        lines.append(f"Chunk: {meta.get('chunk_id', 'N/A')}")
        lines.append(f"Score heurístico: {score:.3f}")
        lines.append("")
        lines.append(doc.page_content.strip())
        lines.append("")

    return "\n".join(lines).strip()


def retrieve_documents(query: str, top_k: int = 3) -> List[Document]:
    """Devuelve solo los Document recuperados, sin consolidarlos.

    Útil para debugging, tests o para mostrar trazabilidad más rica en Streamlit.
    """
    clean_query = (query or "").strip()
    if not clean_query:
        return []

    vector_store = get_vector_store()
    candidates = vector_store.similarity_search(clean_query, k=max(top_k * 2, top_k))
    ranked = _rerank_documents(clean_query, candidates)
    return [doc for doc, _score in ranked[:top_k]]


# -----------------------------------------------------------------------------
# 8) Información de estado para depuración / observabilidad
# -----------------------------------------------------------------------------

def get_corpus_stats() -> Dict[str, Any]:
    """Devuelve estadísticas útiles para visualización o tests."""
    docs = load_mock_documents()
    chunks = get_chunked_documents()
    return {
        "documents": len(docs),
        "chunks": len(chunks),
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "embedding_model": EMBEDDING_MODEL_NAME,
        "documents_meta": [d.metadata for d in docs],
    }


if __name__ == "__main__":
    # Mini smoke test manual. No es parte de la app, pero ayuda a validar el
    # módulo cuando se ejecuta directamente.
    sample_query = "¿Qué dice la política sobre accesos a bases de datos y sanitización?"
    print(retrieve_context(sample_query, top_k=2))
