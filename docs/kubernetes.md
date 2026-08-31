# Despliegue en Kubernetes

## Elección

Kubernetes es preferible a serverless para este proyecto porque SQLite y las
dos colecciones Chroma requieren almacenamiento persistente y un único
escritor. El manifiesto utiliza una réplica, PVC `ReadWriteOnce` y estrategia
`Recreate`.

## Requisitos

- cluster Kubernetes con StorageClass predeterminada;
- controlador `ingress-nginx`;
- Secret TLS llamado `chatbot-tls`;
- `kubectl`;
- imagen publicada en GHCR;
- acceso de red saliente al proveedor LLM y LangSmith.

## Ejecución local con kind

El overlay `k8s/overlays/local` reutiliza la imagen
`chatbot:local`, desactiva su descarga desde un registro y utiliza la
StorageClass local del cluster.

```powershell
docker build -t chatbot:local .
kind create cluster --config k8s/local/kind-config.yaml
kind load docker-image chatbot:local `
  --name chatbot
```

Después de crear `chatbot-secrets` desde las credenciales locales:

```powershell
kubectl apply -k k8s/overlays/local
kubectl rollout status deployment/chatbot `
  -n chatbot --timeout=10m
kubectl port-forward service/chatbot 8501:80 `
  -n chatbot
```

La aplicación queda disponible en `http://localhost:8501`. El port-forward
debe permanecer en ejecución mientras se utiliza la aplicación.

## Secretos

`.env` es apropiado únicamente para desarrollo local y Compose. Kubernetes no
lee ese archivo: la configuración no sensible vive en
`k8s/base/configmap.yaml` y las credenciales se inyectan desde el Secret
`chatbot-secrets`.

Para un cluster local, creá un archivo que no será versionado:

```powershell
Copy-Item k8s/secrets.env.example k8s/secrets.env
```

Completá las credenciales y desplegá:

```powershell
.\scripts\deploy-k8s.ps1 `
  -Image ghcr.io/organizacion/repositorio@sha256:<digest> `
  -SecretsFile k8s/secrets.env
```

Antes de producción, reemplazá `chatbot.example.com` en
`k8s/overlays/production/ingress.yaml` por el dominio real.

El script:

1. valida la referencia de imagen;
2. crea o actualiza el Secret sin imprimir credenciales;
3. renderiza Kustomize con la imagen indicada;
4. aplica los objetos;
5. reinicia el Deployment para cargar cualquier secreto actualizado;
6. espera que finalice el rollout.

Un `Secret` nativo evita guardar credenciales en manifiestos o imágenes, pero
sus valores solo están codificados en Base64. En producción habilitá cifrado de
Secret en reposo y RBAC de mínimo privilegio. Preferentemente, sincronizá las
credenciales desde un gestor (Vault, AWS Secrets Manager, GCP Secret Manager o
Azure Key Vault) mediante External Secrets Operator. Otra opción GitOps es
SOPS, manteniendo únicamente el archivo cifrado en Git.

No conviertas `.env` directamente en un Secret: contiene también rutas, nombres
de modelos y otras opciones que corresponden al `ConfigMap`. Si una credencial
real fue versionada alguna vez, eliminar el archivo actual no basta; revocala,
rotala y limpiá el historial según la política del repositorio.

## Verificación

```powershell
.\scripts\validate-k8s.ps1
kubectl get pods,pvc,service,ingress -n chatbot
kubectl logs deployment/chatbot -n chatbot
kubectl port-forward service/chatbot 8501:80 `
  -n chatbot
```

La comprobación local queda disponible en `http://localhost:8501`.

## CD automático

Configurá en el environment de GitHub `production`:

- `KUBE_CONFIG_B64`: kubeconfig de una identidad de despliegue, codificado en
  Base64 y limitado al namespace;
- `K8S_HOST`: dominio público sin protocolo.

El Secret `chatbot-secrets` y el TLS deben aprovisionarse previamente
en el cluster. Al publicar una etiqueta `vX.Y.Z`, CD despliega la imagen por
digest y espera el rollout. Si los secretos de CD no existen, la imagen se
publica pero el despliegue se omite explícitamente.

## Operación

Realizá snapshots periódicos de los tres PVC. Para rollback:

```powershell
kubectl rollout undo deployment/chatbot `
  -n chatbot
```

Con estrategia `Recreate` habrá una interrupción breve durante la actualización.
Alta disponibilidad requiere migrar SQLite y Chroma a servicios compartidos.
