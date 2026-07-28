$ErrorActionPreference = "Stop"

if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
    throw "kubectl no está instalado o no se encuentra en PATH."
}

kubectl kustomize k8s/base | Out-Null
kubectl kustomize k8s/overlays/production | Out-Null
Write-Output "Manifiestos Kubernetes válidos."
