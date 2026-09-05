# Arquitectura de Agente Corporativo IA

## Propósito y alcance

Agente Corporativo IA es una aplicación multiagente para responder consultas
corporativas mediante tres fuentes:

- manuales generales y documentos de conocimiento;
- manuales complejos de seguridad, redes y acceso a datos;
- datos estructurados de empleados con autorización según rol.

La interfaz está implementada en Streamlit. LangGraph dirige cada solicitud al
agente correspondiente, LangChain conecta modelos y herramientas, Chroma
resuelve la recuperación semántica y MCP encapsula el acceso autorizado a
SQLite.

Esta es la documentación técnica de alto nivel del proyecto. Los procedimientos
operativos se desarrollan en:

- `docs/kubernetes.md`: despliegue y operación en Kubernetes;
- `docs/ci-cd.md`: integración y entrega continua;
- `docs/mcp-server.md`: transportes, herramientas y seguridad MCP;
- `docs/metrics.md`: observabilidad y objetivos operativos;
- `docs/trajectory-evaluation.md`: evaluación de trayectorias.

## Vista general

```text
Usuario
  |
  v
Streamlit (app.py)
  |
  v
Estado AgentState de LangGraph
  |
  v
Manager determinista basado en rol
  |
  +-- Invitado --------> RAG de conocimiento general
  |
  +-- Empleado --------> RAG exclusivo del manual de empleados
  |                       + MCP Empleado -> SQLite sin salarios
  |
  |
  v
Evaluador de respuesta
  |
  +-- retry acotado -> Manager
  +-- end -----------> Respuesta al usuario

Ejecución y evaluaciones -> LangSmith
Persistencia ------------> SQLite + dos colecciones Chroma
```

## Flujo de una solicitud

1. Streamlit recibe la consulta y el rol de la sesión.
2. `AgentState` conserva mensajes, rol, agente designado, motivo de selección y
   estado de evaluación.
3. El manager selecciona de forma determinista al agente Invitado o Empleado.
   El texto del usuario no puede elevar sus permisos.
4. El especialista utiliza únicamente las herramientas habilitadas para su rol.
5. El runtime invoca el modelo configurado y procesa llamadas de herramientas
   nativas o expresadas como JSON por modelos sin soporte nativo.
6. Los resultados extensos se reducen antes de volver al modelo, conservando
   totales y estadísticas relevantes.
7. El evaluador decide finalizar o reintentar. El número de ciclos es acotado
   para evitar bucles indefinidos.
8. La respuesta final se muestra en Streamlit y, si está habilitado, la
   trayectoria se registra en LangSmith.

## Agentes y permisos

| Rol | Documentación general | Manuales complejos | Datos de empleados |
|---|---:|---:|---|
| Invitado | Sí | No | No |
| Empleado | No | Sí | Sí, sin salarios ni estadísticas salariales |

El manager de `agent_system/manager_agent.py` no utiliza un LLM para autorizar:
lee `rol_usuario` del estado confiable y asigna un especialista. Cada instancia
MCP también fija su rol al arrancar y solo publica las herramientas permitidas.
La sanitización del rol Empleado se realiza en la capa de datos, no únicamente
en el prompt.

La selección manual de rol incluida en la interfaz simplifica el uso local. En un
entorno real, el rol debe derivarse de una identidad autenticada y de
autorizaciones emitidas por el proveedor de identidad.

## Recuperación documental

Existen dos pipelines RAG independientes:

| Colección | Fuente predeterminada | Persistencia |
|---|---|---|
| Manuales complejos | `manuales_complejos/` | `manuales_complejos_chroma_db/` |
| Conocimiento general | `knowledge_base/` | `manuales_simples_chroma_db/` |

Los manuales complejos se dividen por sección en fragmentos de hasta 1000
caracteres con solapamiento de 180; el conocimiento general usa fragmentos de
600 con solapamiento de 100. El RAG complejo considera al menos 12 candidatos,
combina recuperación vectorial con coincidencias léxicas normalizadas (incluidas
consultas sin tilde) y devuelve como máximo tres fragmentos de la sección más
relevante. El RAG general devuelve hasta dos fragmentos. Los
embeddings usan por defecto
`sentence-transformers/all-MiniLM-L6-v2`. La búsqueda recupera más candidatos
que el resultado final y `rag/ranking.py` los reordena según cobertura textual
y metadatos. El contexto entregado al agente conserva fuente, documento,
fragmento y score heurístico.

## Acceso a datos mediante MCP

`mcp_server.py` ofrece el acceso estructurado mediante Model Context Protocol:

- `stdio` para procesos locales iniciados por la aplicación;
- Streamable HTTP para instancias remotas;
- SSE por compatibilidad.

Sin URLs MCP configuradas, el cliente inicia automáticamente un servidor local
por `stdio`. En modo remoto se configura una URL para Empleado.

SQLite contiene la tabla permitida `empleados`. La capa `data_access/` valida
consultas, aplica filtros, limita resultados, elimina campos no autorizados y
mantiene el historial de conversaciones aislado por rol.

Las operaciones deterministas se publican como tools especializadas:

- conteo total filtrado, sin depender del tamaño de una muestra;
- distribución por área o puesto con porcentajes;
- recuperación de políticas aplicables y combinación con datos de un área;
- verificación léxica del respaldo de una respuesta contra sus fuentes.

## Proveedores de modelos y tolerancia a fallos

El orden de selección del modelo es:

1. endpoint compatible con OpenAI si existe `OPENAI_API_BASE`;
2. Hugging Face Endpoint mediante `HF_MODEL_ID` o `OPENAI_MODEL`;
3. modelo determinista offline si el proveedor o sus dependencias fallan.

El fallback permite pruebas sin conectividad, pero no sustituye
la calidad de un modelo productivo. Las invocaciones usan baja temperatura,
timeout y reintentos acotados.

## Módulos principales

| Responsabilidad | Ubicación |
|---|---|
| Interfaz y sesión | `app.py` |
| Grafo y estado compartido | `agent_system/graph.py`, `agent_system/state.py` |
| Manager y especialistas | `agent_system/*_agent.py` |
| Ejecución de modelos y herramientas | `agent_system/runtime.py`, `agent_system/models.py`, `agent_system/tools.py` |
| Cliente y servidor MCP | `agent_system/mcp_client.py`, `mcp_server.py` |
| Datos, autorización e historial | `data_access/` |
| RAG y ranking | `rag/` |
| Evaluación automática | `trajectory_evaluation/` |
| Contenedores y despliegue | `Dockerfile`, `compose.yaml`, `k8s/` |
| Automatización | `.github/workflows/`, `scripts/` |

## Configuración y secretos

En desarrollo local, `.env` aporta variables al proceso y a Docker Compose. El
archivo real está ignorado por Git; `.env.example` documenta las claves
admitidas sin credenciales.

En Kubernetes la configuración se divide en:

- `ConfigMap`: modelos, endpoints, rutas, tracing y opciones no sensibles;
- `Secret`: claves de OpenAI, Hugging Face y LangSmith;
- volúmenes persistentes: SQLite y ambas colecciones Chroma.

Los secretos no se incorporan a la imagen ni se guardan en manifiestos. Un
`Secret` nativo de Kubernetes solo codifica los valores en Base64, por lo que
producción debe usar cifrado en reposo, RBAC mínimo y preferentemente un gestor
externo sincronizado con External Secrets Operator o una solución GitOps
cifrada como SOPS.

## Seguridad del contenedor y la red

El contenedor:

- se ejecuta como usuario y grupo no root;
- no permite escalamiento de privilegios;
- elimina todas las capabilities Linux;
- utiliza filesystem raíz de solo lectura;
- no monta el token del ServiceAccount;
- escribe únicamente en PVC y en `/tmp`.

Kubernetes limita la entrada mediante `NetworkPolicy` y ejecuta Streamlit y
FastAPI como contenedores del mismo Pod. El Service publica los puertos 80 y
8000; el Ingress dirige `/` a Streamlit y `/api` y `/health` a FastAPI. Las
probes consultan `/_stcore/health` para la UI y `/health/live` o
`/health/ready` para la API.

Estas medidas protegen el runtime, pero la autenticación externa sigue siendo
responsabilidad del Ingress o de la plataforma de identidad.

## Persistencia y escalabilidad

El único Pod de la aplicación utiliza tres PVC `ReadWriteOnce`:

- base SQLite e historial;
- colección Chroma de manuales complejos;
- colección Chroma de conocimiento general.

El Deployment mantiene una réplica y estrategia `Recreate` para impedir que
dos Pods accedan simultáneamente a los archivos persistentes. No se debe
aumentar `replicas` con esta arquitectura.
Para escalar horizontalmente se requiere migrar:

- SQLite a PostgreSQL u otro servicio transaccional compartido;
- Chroma local a un servicio vectorial compartido;
- el historial de sesión a almacenamiento externo.

También deben definirse snapshots periódicos y una restauración probada para
los tres volúmenes.

## Observabilidad y evaluación

LangSmith registra, cuando está habilitado, mensajes, decisiones del grafo,
llamadas de herramientas, latencia y errores. Los experimentos calculan:

- `trajectory_correctness`;
- `trajectory_efficiency`;
- `answer_relevance`.

Kubernetes aporta salud del Pod, reinicios y consumo de recursos. Para series
históricas y alertas se requiere una plataforma como Prometheus/Grafana o el
servicio administrado equivalente.

## Entrega y despliegue

En pull requests y pushes, CI:

1. rechaza un `.env` versionado;
2. compila las fuentes;
3. prueba persistencia, aislamiento por rol y protocolo MCP;
4. renderiza los manifiestos Kubernetes;
5. construye la imagen sin publicarla.

Una etiqueta SemVer activa CD: repite las verificaciones, publica la imagen en
GHCR, genera procedencia de build y despliega por digest inmutable cuando el
environment `production` contiene acceso al clúster. Los secretos de la
aplicación y el certificado TLS deben existir previamente.

## Limitaciones conocidas

- La UI local no implementa autenticación empresarial.
- SQLite y Chroma locales obligan a ejecutar una sola réplica.
- El fallback offline prioriza continuidad funcional, no calidad semántica.
- Los endpoints LLM, LangSmith y MCP remoto dependen de conectividad saliente.
- El Secret y los PVC requieren políticas externas de rotación, backup y
  recuperación.
