# Arquitectura de chatBot

## Propósito

chatBot es una aplicación genérica con un único agente y una única fuente de
conocimiento no parametrizada: `knowledge_base/`. Allí se almacenan todos los
documentos del negocio, incluidos servicios, valores, contacto, registro,
login, políticas y procedimientos.

## Flujo

```text
Usuario -> Streamlit o FastAPI -> LangGraph -> chatBot
                                           -> knowledge_base
                                           -> respuesta
```

1. La interfaz o `POST /api/chat` recibe la consulta.
2. LangGraph ejecuta directamente el nodo `chatBot`.
3. El runtime obliga a consultar `knowledge_retrieve_context`.
4. El pipeline busca fragmentos en `knowledge_base/` y conserva sus fuentes.
5. El modelo redacta una respuesta; las llamadas internas nunca se muestran.
6. La interacción se guarda en `data/chatBot.sqlite3`.

## Recuperación

| Fuente | Índice persistente | Colección |
|---|---|---|
| `knowledge_base/` | `knowledge_base_chroma_db/` | `knowledge_base` |

La recuperación léxica funciona sin conexión. La búsqueda semántica es opcional
mediante `RAG_SEMANTIC_SEARCH_ENABLED=true` y utiliza el modelo indicado en
`RAG_EMBEDDING_MODEL`.

## Componentes

| Responsabilidad | Ubicación |
|---|---|
| Interfaz Streamlit | `app.py` |
| API HTTP | `api.py` |
| Grafo y agente | `agent_system/graph.py`, `agent_system/chatbot_agent.py` |
| Runtime y herramientas | `agent_system/runtime.py`, `agent_system/tools.py` |
| Fuente e índice RAG | `knowledge_base/`, `rag/` |
| Historial | `data_access/query_history.py`, `data/chatBot.sqlite3` |
| Despliegue | `Dockerfile`, `compose.yaml`, `k8s/` |

## Persistencia y despliegue

Kubernetes utiliza dos PVC `ReadWriteOnce`: uno para SQLite y otro para Chroma.
El Deployment mantiene una réplica y estrategia `Recreate`. Para escalar se
deben sustituir ambos almacenes locales por servicios compartidos.

El contenedor se ejecuta sin privilegios, con filesystem raíz de solo lectura,
probes HTTP y escritura limitada a `/app/data`, `/app/knowledge_base_chroma_db`
y `/tmp`.
