# Arquitectura del proyecto

## Propósito

La aplicación se centra en la lectura y comprensión del proyecto real contenido dentro de la carpeta [repositorios](../repositorios). La fuente de verdad ya no es documentación parametrizada ni manuales antiguos; la lectura autorizada es el código y los archivos del proyecto web/backend presentes en el repositorio local.

## Flujo

```text
Usuario -> Streamlit o FastAPI -> LangGraph -> orchestrator
                                      -> projectReader
                                      -> chatBot
                                      -> codeEditor
                                      -> respuesta
```

1. La interfaz o `POST /api/chat` recibe la consulta.
2. El orquestador decide si la solicitud requiere lectura del proyecto, respuesta general o edición.
3. `projectReader` recorre los archivos reales dentro de `repositorios` y extrae contexto útil.
4. `codeEditor` trabaja sobre los archivos del repositorio para crear o corregir código.
5. `chatBot` responde usando el proyecto real y no documentación antigua.
6. La conversación queda persistida en `data/chatBot.sqlite3`.

FastAPI mantiene endpoints síncronos para que el trabajo bloqueante de LangGraph y SQLite se ejecute en el pool de hilos del framework. Expone chat, consulta y limpieza de historial. Al apagar el servidor, el ciclo de vida cierra la conexión SQLite compartida.

## Componentes

| Responsabilidad | Ubicación |
|---|---|
| Interfaz Streamlit | `app.py` |
| API HTTP | `api.py` |
| Grafo principal | `agent_system/graph.py` |
| Orquestación | `agent_system/orchestrator.py` |
| Lector de proyecto | `agent_system/project_reader_agent.py` |
| Editor de código | `agent_system/code_editor_agent.py` |
| Chat general | `agent_system/chatbot_agent.py` |
| Estado | `agent_system/state.py` |
| Historial | `data_access/query_history.py`, `data/chatBot.sqlite3` |
| Despliegue | `Dockerfile`, `compose.yaml`, `k8s/` |

## Alcance de fuentes

| Fuente | Estado |
|---|---|
| [repositorios](../repositorios) | Autorizada y principal |
| manuales y documentación antigua | Eliminada del flujo |
| web / búsquedas externas | Desactivada |
| `knowledge_base` / RAG documental | Fuera del diseño activo |

## Persistencia y despliegue

La persistencia mínima necesaria es el historial SQLite en `/app/data` para la conversación. El contenedor no requiere volúmenes vectoriales ni almacenamiento Chroma para la operación actual.

La misma imagen ejecuta Streamlit y FastAPI como servicios separados en Compose
y como dos contenedores del mismo pod en Kubernetes. Ambos comparten SQLite y el
repositorio. No existen índices vectoriales ni volúmenes de Chroma.
