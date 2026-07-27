# Servidor MCP del Agente Corporativo IA

El repositorio expone un servidor interoperable mediante el SDK oficial de
Model Context Protocol. Soporta `stdio`, SSE y Streamable HTTP.

## Seguridad por instancia

El rol queda fijado al iniciar el proceso y no forma parte de los argumentos
enviados por el cliente:

- `Invitado`: solo descubre `consultar_permisos`.
- `Empleado`: descubre `consultar_empleados`, sin salarios ni estadísticas.
- `Administrador`: descubre `consultar_empleados` con acceso completo.

Para una instalación remota, cada rol debe ejecutarse como una instancia
independiente y protegerse en el proxy o plataforma de identidad. No se debe
publicar una instancia Administrador sin autenticación de infraestructura.

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
AGENT_MCP_ADMINISTRADOR_URL=http://127.0.0.1:8001/mcp
```

Sin esas variables, utiliza automáticamente un servidor local por `stdio`.

## Herramientas y recursos

- `consultar_permisos`: rol y alcance de la instancia.
- `consultar_empleados`: filtros por DNI, nombre, apellido, área y puesto.
- `schema://empleados`: esquema visible según el rol.

El parámetro `limit` admite de 1 a 100 resultados.

## Verificación

```powershell
python test_mcp_protocol.py
```

La prueba usa el cliente del SDK oficial, negocia el protocolo, descubre las
herramientas y valida el aislamiento salarial de los tres roles.
