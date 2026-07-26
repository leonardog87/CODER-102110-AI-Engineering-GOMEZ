# Manual de Políticas de Seguridad en la Nube (AWS)

## Objetivo

Establecer lineamientos mínimos para operar infraestructura en AWS sin exponer
información sensible ni configuraciones críticas.

## Principios generales

- Aplicar el principio de privilegio mínimo en IAM.
- Utilizar MFA para accesos administrativos.
- Mantener separación entre desarrollo, prueba y producción.
- Registrar eventos relevantes en CloudTrail y centralizar logs.
- Evitar credenciales embebidas en código fuente.

## Controles obligatorios

1. Las claves de acceso no deben compartirse.
2. Los buckets S3 con datos internos deben ser privados por defecto.
3. Las instancias EC2 sensibles deben usar grupos de seguridad restrictivos.
4. Las bases de datos deben usar cifrado en reposo y en tránsito.
5. Los secretos deben almacenarse en un gestor dedicado.

## Respuesta ante incidentes

- Rotar credenciales afectadas.
- Revisar logs de acceso.
- Registrar hora, alcance y sistemas impactados.
- Notificar al responsable de seguridad.

## Auditoría

- Revisar permisos IAM cada 30 días.
- Validar que no existan roles con acceso excesivo.
- Verificar que todo recurso expuesto a Internet esté justificado.
