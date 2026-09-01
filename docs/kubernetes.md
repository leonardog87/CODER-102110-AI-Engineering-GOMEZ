# Despliegue en Kubernetes

El pod ejecuta dos contenedores de la misma imagen: Streamlit en `8501` y
FastAPI en `8000`. Ambos comparten el historial SQLite de `/app/data` y acceden
al proyecto de `/app/repositorios/rrhh`. No se utiliza Chroma ni almacenamiento
vectorial.

## Requisitos

- Kubernetes con una StorageClass predeterminada;
- `kubectl` y una imagen accesible por el clúster;
- Secret `chatbot-secrets` con las credenciales del proveedor LLM;
- para producción, ingress-nginx y el Secret TLS `chatbot-tls`.

## Despliegue local con kind

```powershell
docker build -t chatbot:local .
kind create cluster --config k8s/local/kind-config.yaml
kind load docker-image chatbot:local --name chatbot
kubectl apply -k k8s/overlays/local
kubectl rollout status deployment/chatbot -n chatbot --timeout=10m
```

Accesos locales:

```powershell
kubectl port-forward service/chatbot 8501:80 -n chatbot
kubectl port-forward service/chatbot 8000:8000 -n chatbot
```

- Streamlit: `http://localhost:8501`
- FastAPI: `http://localhost:8000/docs`
- Salud: `http://localhost:8000/health`

## Configuración y secretos

La configuración no sensible está en `k8s/base/configmap.yaml`. Kubernetes no
lee `.env`. Las credenciales se crean desde un archivo no versionado:

```powershell
Copy-Item k8s/secrets.env.example k8s/secrets.env
kubectl -n chatbot create secret generic chatbot-secrets `
  --from-env-file=k8s/secrets.env --dry-run=client -o yaml | kubectl apply -f -
```

En producción usá un gestor de secretos o cifrado en reposo. Si una credencial
fue versionada, debe revocarse y rotarse.

## Persistencia y código editable

El PVC `app-data` almacena únicamente SQLite. El repositorio viene incluido en
la imagen; las modificaciones de código dentro de Kubernetes sobreviven durante
la vida del pod, pero no una recreación. Para conservarlas en producción montá
un repositorio Git o un PVC en `/app/repositorios` y aplicá revisión, pruebas y
commit fuera del agente.

## Verificación

```powershell
.\scripts\validate-k8s.ps1
kubectl get pods,pvc,service,ingress -n chatbot
kubectl logs deployment/chatbot -c app -n chatbot
kubectl logs deployment/chatbot -c api -n chatbot
curl http://localhost:8000/health
```

El Deployment usa una réplica y estrategia `Recreate`, apropiadas para SQLite.
Para alta disponibilidad se debe migrar el historial a una base compartida.
