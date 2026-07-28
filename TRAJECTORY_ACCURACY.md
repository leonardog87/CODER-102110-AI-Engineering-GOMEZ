# Trajectory Accuracy con LangSmith

El proyecto usa el evaluador de trayectorias de AgentEvals y divide
`Trajectory Accuracy` en dos métricas independientes:

- `trajectory_correctness`: verifica la lógica de las decisiones, la selección
  y argumentos de herramientas, el uso fiel de sus resultados y que la
  trayectoria resuelva correctamente la solicitud.
- `trajectory_efficiency`: verifica que no haya llamadas redundantes, reintentos
  innecesarios, trabajo repetido ni desvíos, sin penalizar los pasos requeridos.

Ambas métricas revisan la secuencia completa de mensajes, decisiones y llamadas
a herramientas, no solamente la respuesta final.

El experimento también incluye `answer_relevance`, la métrica oficial de
OpenEvals que compara la última consulta del usuario con la respuesta final
visible del agente. No requiere una respuesta de referencia.

## Dataset

Creá o seleccioná en LangSmith un dataset con este formato de entrada:

```json
{
  "messages": [
    {"role": "user", "content": "¿Cuántos empleados hay?"}
  ],
  "rol_usuario": "Administrador"
}
```

También se admite `{"question": "...", "rol_usuario": "Invitado"}`.

Para evaluar contra una trayectoria esperada, guardala en los outputs de
referencia bajo la clave `messages` y agregá `--with-reference` al comando.

## Ejecución

Instalá las dependencias y verificá que `LANGSMITH_API_KEY` esté configurada:

```powershell
python -m pip install -r requirements.txt
python -m trajectory_evaluation.trajectory_accuracy `
  --dataset ciudad-analitica-trajectory
```

Con referencia y un modelo de juez explícito:

```powershell
python -m trajectory_evaluation.trajectory_accuracy `
  --dataset ciudad-analitica-trajectory `
  --with-reference `
  --judge-model openai:o3-mini
```

Sin `--judge-model`, los evaluadores reutilizan el proveedor y modelo
configurados por el proyecto. Los resultados aparecen dentro del mismo
experimento de LangSmith como feedback `trajectory_correctness` y
`trajectory_efficiency`, junto con `answer_relevance`.
