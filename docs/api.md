# API HTTP

FastAPI se ejecuta con `uvicorn api:app --host 0.0.0.0 --port 8000`. El contrato
OpenAPI está en `/openapi.json` y la documentación interactiva en `/docs`.

| Método | Ruta | Uso |
|---|---|---|
| `GET` | `/health` | Salud y disponibilidad de `repositorios` |
| `POST` | `/api/chat` | Consulta o modificación mediante LangGraph |
| `GET` | `/api/history?limit=100` | Historial persistido, de 1 a 500 registros |
| `DELETE` | `/api/history` | Limpieza explícita del historial completo |

```powershell
$body = @{ message = "Explicá el proceso de cambio de email" } | ConvertTo-Json
Invoke-RestMethod http://localhost:8000/api/chat `
  -Method Post -ContentType application/json -Body $body
```

`POST /api/chat` acepta `conversation_history`, con hasta 20 mensajes de roles
`user` o `assistant`. La respuesta contiene `answer`, archivos en `sources` y
metadatos en `audit`. Los errores de entrada son `422`; una falla del agente
responde `503` y una falla de persistencia, `500`.

Configurá CORS mediante `API_CORS_ORIGINS`, separando orígenes con `;`.
