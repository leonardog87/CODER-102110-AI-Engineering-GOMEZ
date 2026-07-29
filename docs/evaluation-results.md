# Resultados de evaluación

## Ejecución registrada

Fecha: **2026-07-29**.

Dataset LangSmith:

- nombre: `agente-corporativo-ia-trajectory`;
- ID: `94a3895f-c3f4-4d9f-babc-91ab3022f5c2`;
- casos: 6;
- cobertura: Invitado, Empleado y Administrador.

Experimento válido:

- nombre: `entrega-final-estructural-2026-07-29-c026600d`;
- casos ejecutados: 6;
- errores de ejecución: 0;
- [ver experimento en LangSmith](https://smith.langchain.com/o/7ca2fdc7-d045-4ab0-9c72-9996964097ad/datasets/94a3895f-c3f4-4d9f-babc-91ab3022f5c2/compare?selectedSessions=8ec2e925-5e44-49e3-8fbb-fe86f35453e8).

## Scores reales

| Métrica | Promedio | Casos aprobados |
|---|---:|---:|
| `routing_correctness` | 1.000 | 6/6 |
| `authorization_compliance` | 1.000 | 6/6 |
| `completion_success` | 1.000 | 6/6 |

Interpretación:

- el manager seleccionó el especialista correcto en todos los casos;
- no se detectaron herramientas de empleados para Invitado ni campos
  salariales para Empleado;
- todas las ejecuciones terminaron con una respuesta no vacía y decisión
  `end`.

## Condición del modelo durante la prueba

El endpoint configurado en `OPENAI_API_BASE` apuntaba a un servidor local en el
puerto `1234`, pero ese servidor no estaba activo. La aplicación utilizó su
fallback offline y aun así completó los seis recorridos estructurales.

También se intentó ejecutar:

- `trajectory_correctness`;
- `trajectory_efficiency`;
- `answer_relevance`.

Esos tres jueces requieren un LLM disponible y no produjeron scores válidos por
el rechazo de conexión del endpoint local. Por lo tanto, no se presentan como
resultados aprobados. Deben repetirse con LM Studio u otro endpoint compatible
activo.

## Reproducción

```powershell
python -m trajectory_evaluation.create_dataset

# Disponible aun sin modelo juez:
python -m trajectory_evaluation.trajectory_accuracy `
  --dataset agente-corporativo-ia-trajectory `
  --experiment-prefix entrega-final-estructural `
  --skip-llm-judges

# Requiere un modelo objetivo y juez disponible:
python -m trajectory_evaluation.trajectory_accuracy `
  --dataset agente-corporativo-ia-trajectory `
  --experiment-prefix entrega-final-llm
```

Para resumir los scores descargados desde LangSmith:

```powershell
python -m trajectory_evaluation.report_experiment `
  --experiment entrega-final-estructural-2026-07-29-c026600d
```

## Criterio de aceptación

La evidencia actual valida enrutamiento, autorización y finalización del grafo.
No valida todavía la calidad semántica del LLM. Para declarar completa la
evaluación de calidad, las tres métricas basadas en juez deben ejecutarse con un
proveedor disponible y compararse con los objetivos definidos en
`docs/metrics.md`.
