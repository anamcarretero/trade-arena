# Backlog priorizado de TradeArena

## Terminado — Fases 0–2

- TA-001 reglas v1 y casos límite financieros versionados.
- TA-002 puertos y selección técnica de proveedores con puertas contractuales.
- TA-003 paquete de términos, privacidad y edad preparado para revisión legal.
- TA-010 cartera USD, órdenes, ejecuciones completas, comisiones y ledger.
- TA-011 dividendos, *splits*, snapshots y ranking reproducibles.
- TA-020 migración PostgreSQL inicial para el modelo mínimo completo.
- TA-021 identidad por enlace firmado de un solo uso y claims Google detrás de
  puerto; sesiones propias revocables.
- TA-022 perfil, edad, exportación y borrado de cuenta.
- TA-023 ligas privadas, roles, invitación/caducidad/revocación y expulsión.
- TA-024 autorización por pertenencia y límites Free en transacción y API v1.
- TA-025 plan canónico, Python 3.12 y dependencias reproducibles en local y CI.

## Terminado — Fase 3

1. TA-030 servidor ASGI y adaptador PostgreSQL con pruebas de integración y
   políticas de bloqueo concurrente. Implementados FastAPI, health checks,
   coherencia de rutas con OpenAPI, unidad de trabajo, repositorios equivalentes
   en memoria/PostgreSQL, migraciones incrementales e imagen OCI sin
   privilegios. Verificados migración, rollback, concurrencia, contenedor y API
   contra PostgreSQL 16 real; CI reproduce la misma integración.

## Completado — Fase 3

1. TA-031 PWA responsive bilingüe: acceso Auth0 mediante BFF, perfil, selección
   de idioma, sesión cifrada `HttpOnly`, cliente OpenAPI y Compose local.
2. TA-032 ligas privadas en la PWA: listado, creación y detalle, dos plazas
   Free, invitaciones mediante enlace copiable, aceptación, revocación y
   expulsión con autorización y límites transaccionales en backend.

## Siguiente — Fase 3

1. TA-033 página pública responsive ES/EN de planes: Free disponible y
   Friends/Club visibles como «Próximamente», sin pagos ni derechos nuevos.
2. TA-034 competición y confirmación visible de `rules_snapshot`.
3. TA-035 cartera, orden, historial, ranking y marca de incorporación tardía.
4. TA-036 centro de notificaciones, exportación y borrado desde la PWA.
5. TA-037 accesibilidad WCAG 2.2 AA y pruebas E2E de dos participantes.
6. TA-038 staging reproducible: Vercel, Neon Frankfurt, Cloud Run Frankfurt,
   Secret Manager y GitHub OIDC; ramas Neon efímeras para integración en PR.

## Fases 4–7

- Integrar datos licenciados y calendario; outbox PostgreSQL y Cloud Run Jobs
  idempotentes para ejecución, valoración y ranking, con Scheduler, reintentos
  y alertas.
- Activar Stripe, derechos por eventos validados y compras nativas cuando
  proceda.
- Crear clientes Expo compartiendo OpenAPI, tipos y diseño.
- Migrar únicamente con consentimiento y retirar el ranking histórico cuando
  el producto nuevo sea estable.

## Backlog de cumplimiento previo a beta/pagos

- Asesoría legal UE/España, DPIA/ROPA, DPA y política de conservación.
- Contrato de mercado y clasificación de usuarios profesionales/no
  profesionales.
- Modelado de amenazas, pentest, rate limits, CSRF/CORS, rotación y sesiones.
- Pruebas de carga, restauración, observabilidad y respuesta a incidentes.
- Textos legales ES/EN, consentimiento versionado y mecanismo de reclamación.
