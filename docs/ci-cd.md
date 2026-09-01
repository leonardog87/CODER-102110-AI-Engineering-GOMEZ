# CI/CD

El repositorio utiliza GitHub Actions para compilar la imagen y validar la aplicación antes del despliegue.

## Integración continua

`.github/workflows/ci.yml` se ejecuta en cada pull request y push a `main` o `master`. El pipeline:

1. instala las dependencias con Python 3.12;
2. valida la compilación de todos los módulos Python;
3. ejecuta la suite de persistencia y validación del agente;
4. valida el contrato de FastAPI y el enrutamiento del proyecto;
5. renderiza los manifiestos de Kubernetes;
6. construye la imagen de la aplicación.

Conviene proteger la rama principal y exigir los checks de compilación y pruebas antes de aceptar un merge.

## Entrega continua

`.github/workflows/cd.yml` se activa con una etiqueta SemVer o manualmente desde GitHub Actions. Repite las pruebas y, si finalizan correctamente:

- construye la imagen;
- publica la versión en el registro del proyecto;
- reutiliza la imagen para el despliegue del entorno correspondiente.

## Secretos

Nunca se debe versionar `.env`. Para ejecución local:

```powershell
docker compose up --build
```

Los secretos del runtime deben configurarse en la plataforma que despliegue la imagen. GitHub Actions solo debe usar credenciales temporales del entorno.

## Despliegue de la imagen

El entorno de ejecución debe consumir la imagen final, inyectar los secretos necesarios y mantener almacenamiento persistente para:

- `/app/data`

El contenedor expone el puerto `8501` para la UI y el puerto `8000` para la API, con health checks contra la ruta apropiada.

Los manifiestos Kubernetes y su operación se documentan en [docs/kubernetes.md](kubernetes.md).
