# Normativas de Acceso a Bases de Datos

## Objetivo

Definir reglas para consultar, administrar y proteger información sensible.

## Reglas de acceso

- El acceso a datos críticos requiere autorización explícita.
- Toda consulta debe limitarse al mínimo necesario.
- Los identificadores deben validarse antes de una búsqueda.
- Las entradas del usuario deben validarse para evitar inyecciones.

## Información sensible

Incluye datos identificatorios, contratos, montos, claves, tokens e información
privada de operación.

## Buenas prácticas

1. Registrar toda consulta administrativa.
2. Enmascarar valores sensibles.
3. Evitar listas completas cuando se solicita un identificador puntual.
4. Separar el acceso de soporte del acceso administrativo.
5. Rechazar consultas ambiguas o fuera de alcance.

## Política de respuesta

Si una consulta excede el alcance permitido, el sistema debe responder con una
negativa segura y sugerir el canal correcto.
