# Presentación: Agente Corporativo IA

## 1. Problema

Las organizaciones necesitan consultar documentación y datos estructurados sin
entregar a todos los usuarios el mismo nivel de acceso. Agente Corporativo IA
demuestra cómo combinar recuperación documental, herramientas y autorización
en un flujo multiagente observable.

## 2. Solución

- Streamlit ofrece la experiencia conversacional.
- LangGraph dirige la solicitud según el rol y controla reintentos.
- LangChain conecta modelos, contexto y herramientas.
- Dos pipelines RAG consultan conocimiento general y manuales complejos.
- MCP desacopla el agente del acceso a SQLite.
- LangSmith registra y evalúa las trayectorias.
- Docker, CI/CD y Kubernetes permiten construir y desplegar el sistema.

## 3. Demostración sugerida

1. Invitado: preguntar por datos de empleados y mostrar el rechazo.
2. Empleado: consultar empleados de Infraestructura y verificar que no aparecen
   salarios.
3. Empleado: solicitar salarios y mostrar el rechazo explícito.
4. Administrador: repetir la consulta y mostrar datos completos.
5. Consultar un manual complejo y enseñar la fuente RAG recuperada.
6. Abrir la traza y los resultados de evaluación en LangSmith.
7. Mostrar el Pod saludable, los PVC y el Service en Kubernetes.

Las preguntas exactas están en el README principal.

Resultados registrados para la entrega:

- 6 casos ejecutados y 0 errores estructurales;
- `routing_correctness`: 1.000;
- `authorization_compliance`: 1.000;
- `completion_success`: 1.000.

Las métricas juzgadas por LLM quedaron pendientes porque el endpoint local del
modelo no estaba activo. Esta limitación está documentada, sin presentar scores
inexistentes, en `docs/evaluation-results.md`.

## 4. Qué está implementado

- manager determinista y tres especialistas;
- ciclo de evaluación con retry acotado;
- recuperación, ranking y dos colecciones Chroma;
- MCP local y remoto con herramientas distintas por rol;
- sanitización salarial en la capa de datos;
- trazas y tres evaluadores de calidad;
- pruebas de persistencia, autorización e integración MCP;
- imagen no root, probes, PVC, NetworkPolicy e Ingress;
- CI, publicación en GHCR y despliegue por digest.

## 5. Qué es demostrativo

| Componente actual | Motivo |
|---|---|
| Selector manual de rol | Permite enseñar rápidamente los tres recorridos |
| SQLite local | Simplifica instalación y persistencia en una sola réplica |
| Chroma embebido | Evita depender de otro servicio durante la demostración |
| Secret nativo | Permite ejecutar Kubernetes localmente |
| Una réplica con `Recreate` | Evita múltiples escritores sobre volúmenes locales |
| Fallback offline | Mantiene pruebas y demostración cuando el LLM no responde |

Estas decisiones son explícitas y no deben presentarse como controles
empresariales definitivos.

## 6. Evolución para producción

```text
Selector manual de rol
  -> SSO/OIDC + token firmado + permisos por identidad

Secret local/Kubernetes
  -> Vault o Secret Manager + External Secrets + rotación

SQLite
  -> PostgreSQL administrado con backups y alta disponibilidad

Chroma local
  -> servicio vectorial compartido o PostgreSQL con pgvector

Una réplica
  -> múltiples réplicas + RollingUpdate + autoscaling

Métricas documentadas
  -> Prometheus/Grafana + alertas y SLO
```

El identificador del usuario debe proceder de un token validado; PostgreSQL
puede relacionarlo con roles y capacidades. Las claves de proveedores no deben
guardarse en una tabla común, sino en un gestor de secretos.

## 7. Evidencia

- pruebas de persistencia y autorización: `tests/`;
- manifiestos renderizados: `scripts/validate-k8s.ps1`;
- evidencia Kubernetes: `docs/evidence/README.md`;
- evaluación LangSmith: `docs/evaluation-results.md`;
- arquitectura completa: `docs/architecture.md`.

## 8. Conclusión

El proyecto cumple el objetivo de demostrar una arquitectura de agentes
modular, segura por diseño, evaluable y desplegable. La presentación distingue
las decisiones adecuadas para una demo académica de los cambios necesarios
para operar con identidad, datos y disponibilidad empresariales.
