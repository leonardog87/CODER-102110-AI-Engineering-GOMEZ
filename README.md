# Agente Corporativo IA

Sistema multiagente para consultar documentación y datos corporativos con
recuperación aumentada (RAG), autorización por rol y trazabilidad de
trayectorias.

El proyecto integra Streamlit, LangChain, LangGraph, Chroma, Model Context
Protocol (MCP), LangSmith, Docker y Kubernetes.

## Arquitectura

```mermaid
flowchart TD
    U[Usuario] --> UI[Streamlit]
    UI --> S[Estado LangGraph]
    S --> M[Manager determinista]
    M --> I[Agente Invitado]
    M --> E[Agente Empleado]
    M --> A[Agente Administrador]
    I --> KG[RAG de conocimiento general]
    E --> KG
    E --> CR[RAG de manuales complejos]
    A --> KG
    A --> CR
    E --> ME[MCP Empleado]
    A --> MA[MCP Administrador]
    ME --> DB[(SQLite)]
    MA --> DB
    I --> EV[Evaluador]
    E --> EV
    A --> EV
    EV -->|retry acotado| M
    EV -->|end| UI
    S -. trazas .-> LS[LangSmith]
    KG --> C1[(Chroma)]
    CR --> C2[(Chroma)]
```

La descripción completa está en
[docs/architecture.md](docs/architecture.md).

## Capacidades por rol

| Rol | Conocimiento general | Manuales complejos | Datos de empleados |
|---|---:|---:|---|
| Invitado | Sí | No | No |
| Empleado | Sí | Sí | Sí, sin salarios |
| Administrador | Sí | Sí | Sí, incluido salario y estadísticas |

La selección manual de rol simplifica el uso local. Antes de desplegar en un
entorno empresarial debe reemplazarse por identidad verificada, como se explica
en [docs/architecture.md](docs/architecture.md).

## Requisitos

- Python 3.12;
- Docker Desktop para contenedores;
- `kubectl` y `kind` para Kubernetes local;
- una API compatible con OpenAI o una cuenta de Hugging Face;
- LangSmith opcional para trazas y evaluaciones.

## Instalación local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Completá en `.env` al menos un proveedor de modelo:

```env
OPENAI_API_BASE=https://endpoint-compatible/v1
OPENAI_API_KEY=...
OPENAI_MODEL=...
```

También puede utilizarse `HUGGINGFACEHUB_API_TOKEN` y `HF_MODEL_ID`. El `.env`
real está excluido de Git y no debe contenerse en la imagen.

La búsqueda web externa está desactivada por defecto, por lo que la recuperación
usa exclusivamente los manuales vectorizados y la base SQLite:

```env
WEB_SEARCH_ENABLED=false
WEB_SEARCH_PROVIDER=tavily
WEB_SEARCH_API_KEY=
WEB_SEARCH_ALLOWED_DOMAINS=argentina.gob.ar
WEB_SYNC_LOCAL_ON_DIFFERENCE=true
```

Al cambiar `WEB_SEARCH_ENABLED=true`, `primary_retrieve_context` consulta Tavily
como fuente principal. Si Tavily no está disponible, falla la conexión o no hay
resultados autorizados, la herramienta usa automáticamente RAG local. El contenido
web nuevo o modificado se sincroniza con URL y fecha en
`knowledge_base/actualizaciones_web.md`, sin sobrescribir los manuales canónicos.
Para activarlo, configurá la clave del proveedor, uno o más dominios separados por
comas y reiniciá la aplicación. Las herramientas web solo pueden consultar
`WEB_SEARCH_ALLOWED_DOMAINS`.

## Ejecución rápida

Aplicación local:

```powershell
streamlit run app.py
```

Abrí `http://localhost:8501`.

API para un frontend C#/JavaScript:

```powershell
uvicorn api:app --reload --port 8000
```

La API queda disponible en `http://localhost:8000` y su contrato interactivo
en `http://localhost:8000/docs`. `POST /api/chat` recibe `message`, `role` y,
opcionalmente, `conversation_history`; `GET /api/history/{role}` recupera el
historial persistido. Para un frontend remoto, configurá
`API_CORS_ORIGINS` separado por `;` en `.env` (por ejemplo,
`https://mi-frontend.example.com`). En producción, el rol debe obtenerse de la
identidad autenticada del backend, no confiarse al JSON del navegador.

Con Docker Compose:

```powershell
docker compose up --build
```

Compose publica Streamlit en `http://localhost:8501` y la API en
`http://localhost:8000`.

## Ejemplos de uso

### Invitado

- “¿Qué servicios ofrece el asistente corporativo?”
- “Resumí las recomendaciones generales del manual de usuario.”
- “¿Puedo consultar la nómina de empleados?”

La última pregunta debe ser rechazada porque el rol Invitado no accede a datos
de empleados.

### Empleado

- “¿Qué indica la normativa sobre el acceso seguro a bases de datos?”
- “Mostrame los empleados del área de Infraestructura.”
- “¿Cuál es el sueldo promedio del área de Desarrollo?”

La consulta salarial debe ser rechazada y ningún resultado MCP debe incluir
`Sueldo_ARS`.

### Administrador

- “Listá los empleados del área de Desarrollo.”
- “¿Cuál es el sueldo promedio de los empleados consultados?”
- “Combiná la política de acceso a bases de datos con la información del área
  de Infraestructura.”

## Inicialización e inspección de datos

```powershell
python scripts/data/migrate_employees_to_sqlite.py
python scripts/data/initialize_complex_vector_store.py
python scripts/data/initialize_knowledge_vector_store.py
python scripts/data/rebuild_knowledge_vector_store.py
python scripts/data/inspect_sqlite_database.py
python scripts/data/inspect_employee_analytics.py count --puesto desarrolladores
python scripts/data/inspect_employee_analytics.py distribution --group-by area
python scripts/data/inspect_employee_analytics.py salary `
  --role Administrador --area Infraestructura
```

Las utilidades restantes están documentadas por su nombre en `scripts/data/`.

## Pruebas

La suite es local y no requiere credenciales de proveedores. La guía de alcance
y resolución de problemas está en [docs/testing.md](docs/testing.md).

```powershell
python -m compileall -q .
python tests/test_persistence.py
python tests/test_mcp_protocol.py
python tests/test_rag_retrieval.py
.\scripts\validate-k8s.ps1
```

## Kubernetes local

```powershell
docker build -t agente-corporativo-ia:local .
kind create cluster --config k8s/local/kind-config.yaml
kind load docker-image agente-corporativo-ia:local `
  --name agente-corporativo-ia
Copy-Item k8s/secrets.env.example k8s/secrets.env
```

Después de completar `k8s/secrets.env`:

```powershell
kubectl apply -f k8s/base/namespace.yaml
kubectl -n agente-corporativo-ia create secret generic `
  agente-corporativo-ia-secrets `
  --from-env-file=k8s/secrets.env `
  --dry-run=client -o yaml |
  kubectl apply -f -
kubectl apply -k k8s/overlays/local
kubectl rollout status deployment/agente-corporativo-ia `
  -n agente-corporativo-ia --timeout=10m
kubectl port-forward service/agente-corporativo-ia 8501:80 `
  -n agente-corporativo-ia
```

La guía completa y la evidencia de ejecución están en
[docs/kubernetes.md](docs/kubernetes.md) y
[docs/evidence/README.md](docs/evidence/README.md).

## Evaluación con LangSmith

Configurá `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` y un dataset con entradas
`question` y `rol_usuario`. Luego ejecutá:

```powershell
python -m trajectory_evaluation.create_dataset
python -m trajectory_evaluation.trajectory_accuracy `
  --dataset agente-corporativo-ia-trajectory
```

Los resultados y su procedimiento reproducible se encuentran en
[docs/evaluation-results.md](docs/evaluation-results.md).

## Documentación

El índice completo está en [docs/README.md](docs/README.md).

## Estado del proyecto

La arquitectura es desplegable. Para un entorno empresarial se deben sustituir
la selección manual de rol por identidad
verificada, gestionar secretos externamente, migrar SQLite a PostgreSQL,
utilizar almacenamiento vectorial compartido e instalar monitoreo y backups.
