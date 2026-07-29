# Evidencia de ejecución

## Kubernetes local

Fecha de ejecución: **2026-07-29 14:01:34 -03:00**.

Entorno:

- Docker Engine `29.4.3`;
- kind `v0.31.0`;
- Kubernetes `v1.35.0`;
- contexto `kind-agente-corporativo-ia`;
- imagen `agente-corporativo-ia:local`.

Procedimiento ejecutado:

```powershell
docker build -t agente-corporativo-ia:local .
.\.local-tools\kind.exe create cluster `
  --config k8s/local/kind-config.yaml
.\.local-tools\kind.exe load docker-image `
  agente-corporativo-ia:local `
  --name agente-corporativo-ia
kubectl apply -f k8s/base/namespace.yaml
kubectl -n agente-corporativo-ia create secret generic `
  agente-corporativo-ia-secrets `
  --from-env-file=k8s/secrets.env `
  --dry-run=client -o yaml |
  kubectl apply -f -
kubectl apply -k k8s/overlays/local
kubectl rollout status deployment/agente-corporativo-ia `
  -n agente-corporativo-ia --timeout=10m
```

Resultado del rollout:

```text
deployment "agente-corporativo-ia" successfully rolled out
```

Estado observado:

```text
RESOURCE                               READY/STATUS
Deployment agente-corporativo-ia       1/1 Available
Pod agente-corporativo-ia-*            1/1 Running, 0 restarts
Service agente-corporativo-ia          ClusterIP, port 80/TCP
PVC app-data                           Bound, 2Gi, RWO
PVC complex-chroma                     Bound, 5Gi, RWO
PVC simple-chroma                      Bound, 5Gi, RWO
NetworkPolicy                          Created
ConfigMap                              Created, 15 entries
Secret                                 Created, type Opaque
```

La imagen reportada por el Deployment fue
`agente-corporativo-ia:local`, con una réplica lista y disponible.

Verificación HTTP mediante port-forward temporal:

```text
GET http://127.0.0.1:18501/_stcore/health
HTTP 200
Body: ok
```

Los eventos confirmaron:

- aprovisionamiento correcto de los tres volúmenes;
- asignación del Pod al nodo de control;
- imagen local disponible en el nodo;
- contenedor creado e iniciado.

Los logs de arranque confirmaron que Streamlit/Uvicorn quedó escuchando en
`0.0.0.0:8501`.

## Alcance de esta evidencia

La prueba demuestra build, carga de imagen, creación de recursos, persistencia,
rollout, probes y respuesta HTTP en un clúster local limpio. No demuestra el
Ingress de producción, el certificado TLS, alta disponibilidad ni un proveedor
de almacenamiento administrado.

No se guardaron valores de secretos en este documento. Solo se verificó que el
objeto Kubernetes existe.
