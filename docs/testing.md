# Pruebas

La suite valida compilación, persistencia y recuperación RAG. Se ejecuta con
Python 3.12 y las dependencias de
`requirements.txt`; no necesita claves de OpenAI, Hugging Face ni LangSmith.

## Ejecución local

Desde la raíz del repositorio:

```powershell
python -m compileall -q .
python tests/test_persistence.py
python tests/test_retrieval_policy.py
python tests/test_rag_retrieval.py
python tests/test_api.py
.\scripts\validate-k8s.ps1
```

Cada script finaliza con código distinto de cero ante un fallo y elimina los
archivos temporales que crea. No deben ejecutarse en paralelo: las pruebas RAG
y de persistencia comparten la configuración del proyecto y pueden acceder a
los mismos almacenes locales.

## Alcance

| Prueba | Verifica |
|---|---|
| `test_persistence.py` | Historial persistente de conversaciones del agente único |
| `test_retrieval_policy.py` | Disponibilidad exclusiva de `knowledge_base` y política web opcional |
| `test_rag_retrieval.py` | Recuperación del índice de `knowledge_base`, límites y fuentes esperadas |
| `test_api.py` | Contrato OpenAPI, validaciones y declaración de fuentes de FastAPI |
| `validate-k8s.ps1` | Renderizado y validaciones estáticas de manifiestos base y overlays |

Las pruebas RAG fuerzan el modo offline y usan las colecciones Chroma
versionadas. Si esas colecciones se reconstruyen, hay que ejecutar nuevamente
la suite para confirmar que las fuentes y umbrales siguen siendo válidos.

## Automatización

CI ejecuta las cuatro pruebas Python, compila el proyecto, renderiza Kubernetes y
construye la imagen. CD repite la compilación y las cuatro pruebas antes de
publicar una imagen de release.
