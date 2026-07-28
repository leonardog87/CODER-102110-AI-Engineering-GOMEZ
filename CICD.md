# CI/CD

El repositorio utiliza GitHub Actions y publica imágenes en GitHub Container
Registry (`ghcr.io`).

## Integración continua

`.github/workflows/ci.yml` se ejecuta en cada pull request y push a `main` o
`master`. El pipeline:

1. instala las dependencias con Python 3.12;
2. rechaza un archivo `.env` versionado;
3. compila todos los módulos Python;
4. prueba persistencia y aislamiento por roles;
5. prueba negociación, autorización y herramientas MCP;
6. construye la imagen de producción sin publicarla.

Conviene proteger la rama principal y exigir los checks `Python checks` y
`Container build` antes de aceptar un merge.

## Entrega continua

`.github/workflows/cd.yml` se activa con una etiqueta SemVer como `v1.0.0` o
manualmente desde GitHub Actions. Repite las pruebas y, si finalizan
correctamente:

- construye la imagen;
- publica etiquetas SemVer, SHA y `latest` en GHCR;
- genera una atestación de procedencia de la imagen;
- utiliza el environment de GitHub `production`, donde pueden configurarse
  aprobaciones obligatorias;
- despliega por digest en Kubernetes cuando `KUBE_CONFIG_B64` y `K8S_HOST`
  están configurados.

Ejemplo de release:

```powershell
git tag v1.0.0
git push origin v1.0.0
```

La imagen resultante queda disponible como:

```text
ghcr.io/<organización-o-usuario>/<repositorio>:1.0.0
```

## Secretos

Nunca se debe versionar `.env`. Para ejecución local:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Los secretos del runtime deben configurarse en la plataforma que despliega la
imagen. GitHub Actions utiliza solamente el `GITHUB_TOKEN` efímero para GHCR y
no necesita claves del modelo ni de LangSmith durante CI/CD.

## Despliegue de la imagen

El workflow entrega una imagen inmutable y verificable. El entorno de ejecución
(Kubernetes, Cloud Run, Render, ECS u otro) debe consumir esa imagen, inyectar
los secretos y montar almacenamiento persistente para:

- `/app/data`
- `/app/manuales_complejos_chroma_db`
- `/app/manuales_simples_chroma_db`

El contenedor expone el puerto `8501` y define un health check contra
`/_stcore/health`.

Los manifiestos Kubernetes y su operación se documentan en `KUBERNETES.md`.
