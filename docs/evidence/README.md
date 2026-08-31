# Evidencia de ejecución

## Kubernetes local

Fecha de ejecución: **2026-07-29 14:01:34 -03:00**.

Entorno:

- Docker Engine `29.4.3`;
- kind `v0.31.0`;
- Kubernetes `v1.35.0`;
- contexto `kind-chatbot`;
- imagen `chatbot:local`.

Procedimiento ejecutado:

```powershell
docker build -t chatbot:local .
.\.local-tools\kind.exe create cluster `
  --config k8s/local/kind-config.yaml
.\.local-tools\kind.exe load docker-image `
  chatbot:local `
  --name chatbot
kubectl apply -f k8s/base/namespace.yaml
kubectl -n chatbot create secret generic `
  chatbot-secrets `
  --from-env-file=k8s/secrets.env `
  --dry-run=client -o yaml |
  kubectl apply -f -
kubectl apply -k k8s/overlays/local
kubectl rollout status deployment/chatbot `
  -n chatbot --timeout=10m
```

Resultado del rollout:

```text
deployment "chatbot" successfully rolled out
```

Estado observado:

```text
RESOURCE                               READY/STATUS
Deployment chatbot       1/1 Available
Pod chatbot-*            1/1 Running, 0 restarts
Service chatbot          ClusterIP, port 80/TCP
PVC app-data                           Bound, 2Gi, RWO
PVC knowledge-chroma                   Bound, 5Gi, RWO
NetworkPolicy                          Created
ConfigMap                              Created, 15 entries
Secret                                 Created, type Opaque
```

La imagen reportada por el Deployment fue
`chatbot:local`, con una réplica lista y disponible.

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
