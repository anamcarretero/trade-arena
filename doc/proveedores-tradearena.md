# Selección de proveedores y contratos internos

La selección técnica queda cerrada para desarrollar las fases 0–2. La
activación pública sigue condicionada a DPA, revisión legal y, para mercado, un
contrato firmado que permita mostrar datos a usuarios finales.

| Responsabilidad | Selección | Puerto y condición |
|---|---|---|
| Identidad | Auth0 EU, email sin contraseña y Google OIDC | `IdentityPort`; Apple se añadirá con el mismo `IdentityAssertion`. El adaptador local HMAC sirve solo desarrollo. |
| Mercado | Massive Stocks Business con el *feed* licenciado que autorice display y retraso uniforme | `MarketDataPort` en Fase 4. No se usarán planes personales ni Yahoo en el producto nuevo. Go-live bloqueado hasta confirmación escrita de redistribución, mercados, sesiones y usuarios no profesionales. |
| Facturación | Stripe Billing y Customer Portal | `BillingPort` en Fase 5; los derechos derivarán de webhooks firmados e idempotentes, nunca del cliente. |
| Hosting y PostgreSQL | Render, región Frankfurt | Web, worker y PostgreSQL en la misma región/red privada; plan de pago con recuperación a punto en el tiempo antes de beta con datos personales. |
| Cola | Tabla *outbox* PostgreSQL y worker Render inicialmente | `QueuePort`; evita otro almacén en el MVP. Migrable a cola gestionada si carga o latencia lo exige. |
| Email | Plantillas de Auth0 solo para acceso | `IdentityPort`; no se usa para avisos de producto en v1. |
| Notificaciones | Base de datos y centro interno | `NotificationPort` en Fase 3; sin push ni email en v1. |

Fuentes de decisión consultadas el 4 de agosto de 2026:

- Auth0 documenta el inicio passwordless por enlace o código:
  <https://auth0.com/docs/api/authentication/passwordless/get-code-or-link>.
- Massive diferencia los planes Business y las ampliaciones con licencia de
  bolsa; sus términos prohíben redistribuir fuera de lo contratado:
  <https://massive.com/changelog> y
  <https://massive.com/terms/market_data_terms.pdf>.
- Stripe prescribe gestionar suscripciones desde webhooks y verificar su
  origen: <https://docs.stripe.com/billing/subscriptions/webhooks>.
- Render ofrece Frankfurt, workers y PostgreSQL con PITR en planes de pago:
  <https://render.com/docs/regions>,
  <https://render.com/docs/background-workers> y
  <https://render.com/docs/postgresql-backups>.

## Contratos de los puertos

Identidad normaliza `provider`, `subject`, `email` y `email_verified`; ninguna
liga conoce tokens de Auth0 o Google. Mercado entregará instrumento, precio
decimal, instante observado, sesión, instante mínimo de publicación, origen y
calidad. Facturación entregará un id global de evento, firma verificada, dueño,
producto, estado y periodo. Cola exigirá clave de idempotencia, disponibilidad,
número de intento y acuse transaccional. Los adaptadores tienen pruebas de
contrato antes de sustituirse.

## Puertas obligatorias de lanzamiento

1. DPA, subencargados, residencia/transferencias y plazos de borrado aprobados.
2. Contrato de mercado que autorice explícitamente la visualización prevista.
3. Términos, privacidad, cookies, consumo, fiscalidad y política de 18 años
   revisados por asesoría para España/UE.
4. Prueba de restauración, rotación de secretos y respuesta a incidentes.
5. Evaluación de impacto de privacidad y registro de actividades completados.
