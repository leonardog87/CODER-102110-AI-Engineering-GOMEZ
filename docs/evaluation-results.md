# Resultados de evaluación

## Ejecución registrada

Fecha: **2026-07-29**.

Dataset LangSmith:

- nombre actual: `chatBot-trajectory`;
- ID: `94a3895f-c3f4-4d9f-babc-91ab3022f5c2`;
- casos: 6;
- cobertura histórica: los antiguos roles; estos resultados deben regenerarse para `chatBot`.

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

- esta ejecución corresponde a la arquitectura anterior y no valida el agente único;
- las próximas ejecuciones deben comprobar el nodo `chatBot` y el uso exclusivo de `knowledge_base`;
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
  --dataset chatBot-trajectory `
  --experiment-prefix entrega-final-estructural `
  --skip-llm-judges

# Requiere un modelo objetivo y juez disponible:
python -m trajectory_evaluation.trajectory_accuracy `
  --dataset chatBot-trajectory `
  --experiment-prefix entrega-final-llm
```

Para resumir los scores descargados desde LangSmith:

```powershell
python -m trajectory_evaluation.report_experiment `
  --experiment entrega-final-estructural-2026-07-29-c026600d
```

## Criterio de aceptación

La evidencia histórica no valida la arquitectura actual. Para declarar completa la
evaluación de calidad, las tres métricas basadas en juez deben ejecutarse con un
proveedor disponible y compararse con los objetivos definidos en
`docs/metrics.md`.
