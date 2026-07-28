# Métricas y monitoreo

## Métricas de calidad

Los experimentos de LangSmith producen feedback por ejemplo:

| Métrica | Significado | Objetivo inicial |
|---|---|---|
| `trajectory_correctness` | Decisiones, herramientas y resultados correctos | ≥ 95% |
| `trajectory_efficiency` | Trayectoria sin pasos o llamadas redundantes | ≥ 90% |
| `answer_relevance` | La respuesta final atiende la consulta | ≥ 95% |

Los objetivos deben calcularse sobre un dataset versionado y revisarse por rol.
Una release no debería promoverse si cualquiera cae más de cinco puntos
porcentuales respecto de la versión estable.

## Indicadores operativos

LangSmith permite inspeccionar latencia, errores, modelos, tokens, herramientas
y trazas. Kubernetes aporta estado de Pods y consumo de recursos.

| Indicador | Fuente | Alerta inicial |
|---|---|---|
| Disponibilidad | readiness probe | Pod no listo durante 5 minutos |
| Reinicios | `kube_pod_container_status_restarts_total` | más de 2 en 15 minutos |
| CPU | métricas del contenedor | más de 85% del límite durante 10 minutos |
| Memoria | métricas del contenedor | más de 85% del límite durante 10 minutos |
| PVC | kubelet/CSI | más de 80% ocupado |
| Error de ejecución | trazas LangSmith | más de 5% en 15 minutos |
| Latencia extremo a extremo | trazas LangSmith | p95 superior a 30 segundos |
| Error MCP | tool runs de LangSmith | más de 2% en 15 minutos |

Las métricas `kube_*` requieren Metrics Server y, para series y alertas
históricas, una instalación como Prometheus/Grafana o el servicio administrado
del proveedor Kubernetes.

## Paneles mínimos

El tablero de producción debe mostrar:

1. solicitudes, errores y p50/p95 de latencia;
2. uso de modelos y tokens;
3. llamadas y errores por herramienta MCP;
4. scores de los tres evaluadores;
5. salud, reinicios, CPU, memoria y ocupación de PVC;
6. segmentación por versión de imagen y rol.

## Trazabilidad de releases

La imagen se despliega por digest. La etiqueta y el SHA de Git permiten
relacionar un cambio de métricas con una versión exacta. Se recomienda agregar
el digest o SHA como metadata de proyecto/experimento en LangSmith durante
cada release.
