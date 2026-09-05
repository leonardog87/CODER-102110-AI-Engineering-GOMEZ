# Servidor MCP del Agente Corporativo IA

El repositorio expone un servidor interoperable mediante el SDK oficial de
Model Context Protocol. Soporta `stdio`, SSE y Streamable HTTP.

## Seguridad por instancia

El rol queda fijado al iniciar el proceso y no forma parte de los argumentos
enviados por el cliente:

- `Invitado`: solo descubre `consultar_permisos`.
- `Empleado`: descubre consulta, conteo y distribución, siempre sin salarios.

Para una instalación remota, cada rol debe ejecutarse como una instancia
independiente y protegerse en el proxy o plataforma de identidad. No se debe

## Transporte stdio

```powershell
python mcp_server.py --role Empleado --transport stdio
```

El archivo `mcp_servers.example.json` contiene configuraciones listas para
clientes compatibles con la convención `mcpServers`.

## Streamable HTTP

```powershell
python mcp_server.py `
  --role Empleado `
  --transport streamable-http `
  --host 127.0.0.1 `
  --port 8000
```

Endpoint:

```text
http://127.0.0.1:8000/mcp
```

La aplicación puede consumir una instancia HTTP configurando:

```env
AGENT_MCP_EMPLEADO_URL=http://127.0.0.1:8000/mcp
```

Sin esas variables, utiliza automáticamente un servidor local por `stdio`.

## Herramientas y recursos

- `consultar_permisos`: rol y alcance de la instancia.
- `consultar_empleados`: filtros por DNI, nombre, apellido, área y puesto.
- `contar_empleados`: conteo exacto por área o puesto.
- `distribucion_empleados`: cantidades y porcentajes agrupados por área/puesto.
- `schema://empleados`: esquema visible según el rol.

El parámetro `limit` admite de 1 a 100 resultados.

## Verificación

```powershell
python tests/test_mcp_protocol.py
```

La prueba usa el cliente del SDK oficial, negocia el protocolo, descubre las
herramientas y valida el aislamiento salarial de los tres roles.

Las herramientas LangChain locales agregan `consultar_politica_aplicable`,
`combinar_politica_con_area_*` y `verificar_respuesta_con_fuentes`. Las
variantes de combinación respetan el rol de la instancia MCP.
