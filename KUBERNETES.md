# Despliegue en Kubernetes

## Elección

Kubernetes es preferible a serverless para este proyecto porque SQLite y las
dos colecciones Chroma requieren almacenamiento persistente y un único
escritor. El manifiesto utiliza una réplica, PVC `ReadWriteOnce` y estrategia
`Recreate`.

## Requisitos

- cluster Kubernetes con StorageClass predeterminada;
- controlador `ingress-nginx`;
- Secret TLS llamado `ciudad-analitica-tls`;
- `kubectl`;
- imagen publicada en GHCR;
- acceso de red saliente al proveedor LLM y LangSmith.

## Ejecución local con kind

El overlay `k8s/overlays/local` reutiliza la imagen
`ciudad-analitica:local`, desactiva su descarga desde un registro y utiliza la
StorageClass local del cluster.

```powershell
docker build -t ciudad-analitica:local .
kind create cluster --config k8s/local/kind-config.yaml
kind load docker-image ciudad-analitica:local `
  --name ciudad-analitica
```

Después de crear `ciudad-analitica-secrets` desde las credenciales locales:

```powershell
kubectl apply -k k8s/overlays/local
kubectl rollout status deployment/ciudad-analitica `
  -n ciudad-analitica --timeout=10m
kubectl port-forward service/ciudad-analitica 8501:80 `
  -n ciudad-analitica
```

La aplicación queda disponible en `http://localhost:8501`. El port-forward
debe permanecer en ejecución mientras se utiliza la aplicación.

## Secretos

Creá un archivo local que no será versionado:

```powershell
Copy-Item k8s/secrets.env.example k8s/secrets.env
```

Completá las credenciales y desplegá:

```powershell
.\scripts\deploy-k8s.ps1 `
  -Image ghcr.io/organizacion/repositorio@sha256:<digest> `
  -SecretsFile k8s/secrets.env
```

Antes de producción, reemplazá `ciudad-analitica.example.com` en
`k8s/overlays/production/ingress.yaml` por el dominio real.

El script:

1. valida la referencia de imagen;
2. crea o actualiza el Secret sin imprimir credenciales;
3. renderiza Kustomize con la imagen indicada;
4. aplica los objetos;
5. espera que finalice el rollout.

## Verificación

```powershell
.\scripts\validate-k8s.ps1
kubectl get pods,pvc,service,ingress -n ciudad-analitica
kubectl logs deployment/ciudad-analitica -n ciudad-analitica
kubectl port-forward service/ciudad-analitica 8501:80 `
  -n ciudad-analitica
```

La comprobación local queda disponible en `http://localhost:8501`.

## CD automático

Configurá en el environment de GitHub `production`:

- `KUBE_CONFIG_B64`: kubeconfig de una identidad de despliegue, codificado en
  Base64 y limitado al namespace;
- `K8S_HOST`: dominio público sin protocolo.

El Secret `ciudad-analitica-secrets` y el TLS deben aprovisionarse previamente
en el cluster. Al publicar una etiqueta `vX.Y.Z`, CD despliega la imagen por
digest y espera el rollout. Si los secretos de CD no existen, la imagen se
publica pero el despliegue se omite explícitamente.

## Operación

Realizá snapshots periódicos de los tres PVC. Para rollback:

```powershell
kubectl rollout undo deployment/ciudad-analitica `
  -n ciudad-analitica
```

Con estrategia `Recreate` habrá una interrupción breve durante la actualización.
Alta disponibilidad requiere migrar SQLite y Chroma a servicios compartidos.
