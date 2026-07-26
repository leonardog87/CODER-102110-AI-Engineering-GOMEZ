# Guía de Resolución de Problemas Comunes de Red

## Objetivo

Ayudar a soporte a identificar fallas de conectividad, latencia y DNS.

## Síntomas frecuentes

- El usuario no navega en Internet.
- La VPN conecta pero no accede a recursos internos.
- La aplicación responde lentamente o con timeouts.
- No se resuelven nombres DNS.

## Diagnóstico

1. Confirmar que el enlace físico esté activo.
2. Verificar IP, máscara, gateway y DNS.
3. Probar conectividad con el gateway y una IP externa.
4. Probar resolución DNS.
5. Revisar proxy, firewall local y políticas de seguridad.
6. Evaluar saturación, pérdida de paquetes y latencia.

## Problemas habituales

- DNS incorrecto: corregir la configuración y volver a probar.
- VPN sin acceso interno: revisar rutas, split tunneling y autenticación.
- Timeouts: verificar jitter, congestión y balanceadores.
- Puerto bloqueado: comprobar firewall y ACL de red.

## Evidencias recomendadas

- Configuración IP.
- Resultados de ping y tracert.
- Estado de la VPN.
- Segmento afectado.
