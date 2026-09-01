# Agente de desarrollo para proyectos web

Aplicación en español para consultar, comprender y modificar el proyecto web
ubicado dentro de `repositorios`. El agente analiza directamente el código
fuente: no utiliza Chroma, índices vectoriales, manuales parametrizados ni
búsquedas web.

## Funcionalidades

- responde preguntas sobre arquitectura, módulos y procesos;
- sigue referencias entre HTML/ASPX, JavaScript, code-behind, servicios y datos;
- cita los archivos utilizados en cada análisis;
- crea y modifica código mediante operaciones validadas;
- bloquea rutas absolutas, escapes con `..`, binarios y cambios ambiguos;
- conserva preguntas, respuestas y auditoría en SQLite;
- permite limpiar manualmente el historial;
- ofrece interfaz Streamlit y API FastAPI.

## Arquitectura

```text
Usuario
  ├─ Streamlit (app.py, puerto 8501)
  └─ FastAPI (api.py, puerto 8000)
          │
          ▼
      LangGraph
          │
      orchestrator
       ├─ projectReader: comprensión de código y procesos
       ├─ codeEditor: creación y modificación segura
       └─ chatBot: consultas generales sobre el repositorio
          │
          ├─ repositorios/rrhh
          └─ data/chatBot.sqlite3
```

La recuperación busca directamente en los archivos mediante `ripgrep`, puntúa
contenido y rutas, evita fragmentos repetidos y expande símbolos y enlaces para
reconstruir procesos entre capas.

## Requisitos

- Python 3.12 o posterior;
- `ripgrep` (`rg`) disponible en `PATH`;
- un proveedor compatible con OpenAI o Hugging Face;
- Docker y Kubernetes solamente si se utilizarán esos despliegues.

## Instalación local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Configuración mínima:

```env
AGENT_PROJECT_ROOT=./repositorios/rrhh

OPENAI_API_BASE=https://servidor-compatible/v1
OPENAI_API_KEY=
OPENAI_MODEL=

PROJECT_INDEX_CHUNK_SIZE=2400
PROJECT_INDEX_CHUNK_OVERLAP=400
PROJECT_INDEX_TOP_K=10
PROJECT_EDIT_TOP_K=16
PROJECT_READER_MAX_CONTEXT_CHARS=20000

LLM_TIMEOUT_SECONDS=60
LLM_MAX_RETRIES=1
```

`PROJECT_INDEX_*` conserva ese nombre por compatibilidad de configuración, pero
no crea índices persistidos. Los valores controlan el fragmentado y la cantidad
de resultados de la búsqueda directa.

## Ejecución

Streamlit:

```powershell
python -m streamlit run app.py
```

Abrí `http://localhost:8501`.

FastAPI:

```powershell
python -m uvicorn api:app --reload --port 8000
```

- API: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- OpenAPI: `http://localhost:8000/openapi.json`
- Salud: `http://localhost:8000/health`

## Ejemplos de consultas

```text
Explicá el proceso de cambio de email del usuario.

Describí el módulo Control Acceso Web, sus funcionalidades y los procesos
involucrados en cada una.

¿Qué contiene Portal.aspx y con qué archivos se relaciona?

Seguí el flujo desde Backend.ModificarMiMail hasta la persistencia.
```

Ejemplos de cambios:

```text
Modificá WebAsistencia/WebRH/... para validar el correo antes de guardarlo.

Creá una prueba para este servicio siguiendo el patrón existente.
```

El editor valida primero todas las operaciones y utiliza escrituras atómicas.
Las ediciones sólo pueden ocurrir dentro de `AGENT_PROJECT_ROOT`.

## FastAPI 3.0

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/health` | Salud y disponibilidad del repositorio |
| `POST` | `/api/chat` | Consulta o solicitud de modificación |
| `GET` | `/api/history?limit=100` | Recupera entre 1 y 500 registros |
| `DELETE` | `/api/history` | Elimina todo el historial |

Ejemplo:

```powershell
$body = @{ message = "Explicá el proceso del mail" } | ConvertTo-Json
Invoke-RestMethod http://localhost:8000/api/chat `
  -Method Post -ContentType application/json -Body $body
```

La respuesta contiene `answer`, los archivos consultados en `sources` y datos
de auditoría en `audit`. CORS se configura con `API_CORS_ORIGINS`, separando
orígenes mediante `;`.

Más detalles en [docs/api.md](docs/api.md).

## Historial

Streamlit incluye el botón **Limpiar historial**, con confirmación. La acción
elimina el historial visible, la auditoría de sesión y los registros SQLite.
FastAPI ofrece la misma operación mediante `DELETE /api/history`.

## Docker Compose

```powershell
docker compose up --build
```

- Streamlit: `http://localhost:8501`
- FastAPI: `http://localhost:8000/docs`

Compose monta `./repositorios` en `/app/repositorios` con escritura habilitada y
persiste SQLite en el volumen `app-data`.

## Kubernetes

El pod utiliza dos contenedores de la misma imagen: `app` para Streamlit y `api`
para FastAPI. Sólo SQLite requiere PVC; no existe almacenamiento vectorial.

```powershell
docker build -t chatbot:local .
kind create cluster --config k8s/local/kind-config.yaml
kind load docker-image chatbot:local --name chatbot
kubectl apply -k k8s/overlays/local
kubectl rollout status deployment/chatbot -n chatbot --timeout=10m
```

Acceso local:

```powershell
kubectl port-forward service/chatbot 8501:80 -n chatbot
kubectl port-forward service/chatbot 8000:8000 -n chatbot
```

Las modificaciones realizadas sobre el repositorio incluido en la imagen son
efímeras ante una recreación del pod. Para conservarlas en producción debe
montarse un repositorio Git o un PVC en `/app/repositorios`.

Guía completa: [docs/kubernetes.md](docs/kubernetes.md).

## Pruebas y validación

```powershell
python -m compileall -q agent_system data_access app.py api.py tests
python tests/test_api.py
python tests/test_persistence.py
python -m unittest tests.test_project_agents
docker compose config --quiet
pwsh -NoProfile -File scripts/validate-k8s.ps1
```

Las pruebas básicas no requieren un LLM disponible; cuando el proveedor falla,
el agente devuelve una respuesta de respaldo sin detener Streamlit.

## Estructura principal

| Ruta | Responsabilidad |
|---|---|
| `agent_system/` | Grafo, agentes, recuperación y modelo |
| `data_access/` | SQLite e historial |
| `repositorios/` | Proyecto web analizado y modificado |
| `app.py` | Interfaz Streamlit |
| `api.py` | API FastAPI 3.0 |
| `compose.yaml` | Despliegue local en contenedores |
| `k8s/` | Manifiestos Kubernetes |
| `docs/` | Documentación técnica ampliada |

## Seguridad y operación

- no versionar `.env` ni secretos;
- limitar `API_CORS_ORIGINS` en producción;
- revisar y probar los cambios de código antes de confirmarlos;
- respaldar `data/chatBot.sqlite3`;
- usar PostgreSQL u otra base compartida antes de aumentar réplicas;
- persistir el repositorio editable fuera de la capa efímera del contenedor.

El índice de documentación se encuentra en [docs/README.md](docs/README.md).
