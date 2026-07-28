# Arquitectura de Ciudad Analítica

## Resumen

Ciudad Analítica es un sistema de agentes con recuperación documental,
consulta estructurada protegida por rol, evaluación automática y despliegue
contenedorizado.

```text
Usuario
  |
  v
Streamlit
  |
  v
Manager determinista -----> Estado compartido de LangGraph
  |                                  |
  +--> Agente Invitado               v
  +--> Agente Empleado        Evaluador cíclico
  +--> Agente Administrador      | retry / end
          |
          +--> Retrieval --> Ranking --> Chroma
          |
          +--> Adaptador LangChain --> MCP --> SQLite/RBAC
          |
          +--> Modelo LLM

Toda la ejecución --> LangSmith --> trazas, experimentos y feedback
```

## Módulos

| Responsabilidad | Ubicación | Implementación |
|---|---|---|
| Retrieval | `rag/pipeline.py`, `rag/knowledge_pipeline.py` | Búsqueda vectorial sobre Chroma |
| Ranking | `rag/ranking.py` | Reranking heurístico por cobertura y metadatos |
| Orquestación | `agent_system/runtime.py`, agentes especialistas | LangChain, modelos y herramientas |
| Ciclo del agente | `agent_system/graph.py`, `evaluator_agent.py` | LangGraph con manager, especialistas, evaluación y retry acotado |
| MCP | `mcp_server.py`, `agent_system/mcp_client.py` | stdio y Streamable HTTP con herramientas por rol |
| Datos | `data_access/` | SQLite, migración, sanitización y auditoría |
| Observabilidad | `app.py`, `trajectory_evaluation/` | Trazas LangSmith y evaluadores automáticos |
| Despliegue | `Dockerfile`, `compose.yaml`, `k8s/` | Contenedor, ejecución local y Kubernetes |

## Límites de seguridad

El manager no interpreta el rol con un LLM: lo recibe del estado confiable de
la aplicación. Cada proceso MCP fija el rol al arrancar y expone únicamente
las herramientas correspondientes. Un MCP Administrador no debe publicarse
fuera de la red privada.

En Kubernetes:

- el contenedor no tiene privilegios ni token de ServiceAccount;
- el filesystem raíz es de solo lectura;
- las credenciales provienen de un Secret externo;
- la NetworkPolicy permite entrada solamente desde el namespace de la
  aplicación y `ingress-nginx`;
- el acceso externo usa TLS en el Ingress.

La selección de rol de la UI sirve como demostración funcional. Antes de
ofrecer el sistema a usuarios no confiables, el Ingress debe integrarse con un
proveedor de identidad y el rol debe derivarse de la identidad autenticada.

## Persistencia y escalado

SQLite y Chroma utilizan tres PersistentVolumeClaims `ReadWriteOnce`. Por esa
razón el Deployment usa una réplica y estrategia `Recreate`, evitando dos
escritores simultáneos durante una actualización.

Para escalar horizontalmente se deben reemplazar:

- SQLite por PostgreSQL u otro servicio transaccional compartido;
- Chroma local por un servicio vectorial compartido;
- el historial local por almacenamiento externo.

No se debe aumentar `replicas` antes de completar esa migración.

## Observabilidad

LangSmith recibe la trayectoria completa de LangChain/LangGraph. Los
experimentos registran:

- `trajectory_correctness`;
- `trajectory_efficiency`;
- `answer_relevance`.

Kubernetes supervisa inicio, disponibilidad y vida del proceso mediante
`/_stcore/health`. Las métricas y alertas recomendadas están definidas en
`METRICS.md`.

## Flujo de entrega

Un pull request ejecuta pruebas y construye el contenedor. Una etiqueta SemVer
publica una imagen inmutable en GHCR, genera su atestación y, si el environment
`production` tiene acceso al cluster, despliega exactamente el digest
publicado.
