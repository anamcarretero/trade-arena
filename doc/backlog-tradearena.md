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

## Siguiente — Fase 3

1. TA-030 servidor ASGI y adaptador PostgreSQL con pruebas de integración y
   políticas de bloqueo concurrente.
2. TA-031 PWA responsive bilingüe: acceso, perfil y selección de idioma.
3. TA-032 creación de liga, invitaciones y administración de miembros.
4. TA-033 competición y confirmación visible de `rules_snapshot`.
5. TA-034 cartera, orden, historial, ranking y marca de incorporación tardía.
6. TA-035 centro de notificaciones, exportación y borrado desde la PWA.
7. TA-036 accesibilidad WCAG 2.2 AA y pruebas E2E de dos participantes.

## Fases 4–7

- Integrar datos licenciados y calendario; outbox/workers idempotentes;
  ejecución, valoración y ranking con reintentos y alertas.
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
