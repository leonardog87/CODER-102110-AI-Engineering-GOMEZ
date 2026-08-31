param(
    [Parameter(Mandatory = $true)]
    [string]$Image,

    [string]$SecretsFile = "k8s/secrets.env",

    [string]$Overlay = "k8s/overlays/production"
)

$ErrorActionPreference = "Stop"
$namespace = "chatbot"
$deployment = "chatbot"

if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
    throw "kubectl no está instalado o no se encuentra en PATH."
}

if (-not (Test-Path -LiteralPath $SecretsFile -PathType Leaf)) {
    throw "No existe $SecretsFile. Copiá k8s/secrets.env.example y completalo."
}

if ($Image -notmatch "^[^/]+/[^/]+/.+(@sha256:[a-f0-9]{64}|:[A-Za-z0-9._-]+)$") {
    throw "La imagen debe incluir registro, repositorio y tag o digest."
}

$workspace = (Resolve-Path -LiteralPath ".").Path
$sourceOverlay = (Resolve-Path -LiteralPath $Overlay).Path
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) (
    "chatbot-k8s-" + [guid]::NewGuid().ToString("N")
)

try {
    New-Item -ItemType Directory -Path $tempRoot | Out-Null
    Copy-Item -LiteralPath (Join-Path $workspace "k8s") `
        -Destination $tempRoot -Recurse

    $tempK8s = Join-Path $tempRoot "k8s"
    $tempOverlay = Join-Path $tempK8s (
        [System.IO.Path]::GetRelativePath(
            (Join-Path $workspace "k8s"),
            $sourceOverlay
        )
    )

    Push-Location $tempOverlay
    try {
        kubectl kustomize edit set image "chatbot=$Image"
    }
    finally {
        Pop-Location
    }

    kubectl apply -f (Join-Path $workspace "k8s/base/namespace.yaml")
    kubectl -n $namespace create secret generic chatbot-secrets `
        "--from-env-file=$SecretsFile" `
        --dry-run=client -o yaml |
        kubectl apply -f -
    kubectl apply -k $tempOverlay
    # Los cambios de Secret no modifican el PodTemplate del Deployment.
    # Reiniciar garantiza que los Pods lean las credenciales actualizadas.
    kubectl rollout restart "deployment/$deployment" -n $namespace
    kubectl rollout status "deployment/$deployment" `
        -n $namespace --timeout=10m
}
finally {
    $resolvedTemp = [System.IO.Path]::GetFullPath($tempRoot)
    $systemTemp = [System.IO.Path]::GetFullPath(
        [System.IO.Path]::GetTempPath()
    )
    if (
        (Test-Path -LiteralPath $resolvedTemp) -and
        $resolvedTemp.StartsWith(
            $systemTemp,
            [System.StringComparison]::OrdinalIgnoreCase
        )
    ) {
        Remove-Item -LiteralPath $resolvedTemp -Recurse -Force
    }
}
