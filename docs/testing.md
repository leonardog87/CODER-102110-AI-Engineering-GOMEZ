# Pruebas

La suite valida compilación, persistencia y flujo del agente sobre el repositorio real. Se ejecuta con Python 3.12 y las dependencias de `requirements.txt`; no necesita claves de OpenAI ni LangSmith para la validación básica.

## Ejecución local

Desde la raíz del repositorio:

```powershell
python -m compileall -q .
python tests/test_persistence.py
python tests/test_api.py
python tests/test_project_agents.py
```

Cada script finaliza con código distinto de cero ante un fallo. No deben ejecutarse en paralelo si se comparte la base SQLite de la aplicación.

## Alcance

| Prueba | Verifica |
|---|---|
| `test_persistence.py` | Historial persistente del agente único |
| `test_api.py` | Contrato FastAPI y fuente declarada `repositorios` |
| `test_project_agents.py` | Enrutamiento al proyecto real y lectura del repositorio |

## Automatización

CI ejecuta la validación Python y construye la imagen, además de realizar una comprobación estática de los manifiestos de Kubernetes.
