# Plan definitivo de ejecución de TradeArena

## 1. Estado y arquitectura objetivo

TradeArena evoluciona como un monolito modular con el dominio financiero
Python independiente. Las Fases 0–2 están terminadas: existen reglas v1,
dominio reproducible, casos de uso de cuentas y ligas, API FastAPI,
persistencia PostgreSQL, migraciones e imagen OCI verificadas. TA-030 está
terminado y el siguiente trabajo es TA-031: acceso, perfil y PWA.

```text
Next.js PWA/BFF — Vercel
        │
FastAPI — Cloud Run Service
        │
PostgreSQL — Neon Frankfurt
        │
Cloud Run Jobs — precios, órdenes, valoraciones y rankings
```

La plataforma prevista usa Vercel, Neon y Google Cloud. Se mantienen Auth0 EU
para identidad, Massive para datos de mercado sujetos a licencia y Stripe para
facturación. El ranking histórico de `trader/`, sus datos cifrados y GitHub
Pages seguirán funcionando hasta la retirada deliberada de la Fase 7.

## 2. Decisiones técnicas cerradas

- `web/`: Next.js, TypeScript, App Router, PWA responsive ES/EN y `pnpm`.
- `tradearena/`: dominio, aplicación, puertos, adaptadores y presentación
  FastAPI. Las reglas financieras no se duplican en TypeScript.
- El plan Free ofrece una liga activa, dos plazas y capital virtual inicial
  fijo de 3.000 USD por competición.
- El repositorio es la fuente canónica para instalar y operar TradeArena en
  cualquier entorno soportado. Cada plataforma incorpora documentación,
  configuración, infraestructura como código, migración, health checks,
  backup, restauración y rollback versionados; no se aceptan pasos esenciales
  que solo existan en una consola externa.
- PostgreSQL 16 mediante `psycopg` 3. Los servicios síncronos se exponen con
  rutas síncronas de FastAPI para no introducir una reescritura asíncrona.
- `Store` evolucionará a una unidad de trabajo con repositorios tipados.
  `MemoryStore` y `PostgresStore` pasarán las mismas pruebas de contrato.
- Las migraciones SQL son incrementales y se aplican con
  `python3 -m tradearena migrate`. No se introduce Alembic mientras el esquema
  sea pequeño y las migraciones existentes sigan siendo SQL explícito.
- La PWA funciona como BFF: mantiene una sesión cifrada `HttpOnly` y llama a
  Cloud Run desde servidor. El navegador nunca recibe credenciales de Neon ni
  el token interno de la API.
- Auth0 Universal Login proporciona email y Google. La API valida la aserción,
  enlaza la identidad local y emite la sesión opaca y revocable de TradeArena.
- Producción y staging usan Neon `aws-eu-central-1` y Cloud Run
  `europe-west3`, ambos en Frankfurt. Los secretos viven en Secret Manager y
  GitHub Actions usa OIDC, no claves persistentes de GCP.
- FastAPI se ejecuta como Cloud Run Service con escala a cero. Precios,
  órdenes, eventos corporativos, valoración y rankings se ejecutan como Cloud
  Run Jobs independientes, finitos e idempotentes, activados por Cloud
  Scheduler. No habrá worker pools permanentes en el MVP.
- Cada PR de interfaz recibe una preview de Vercel. Los PR que cambien backend,
  persistencia o migraciones crean una rama Neon efímera para CI, aplican las
  migraciones y la eliminan al cerrar el PR. No se despliega una API por PR.
- Staging integrado se actualiza después de fusionar en `main`. Producción
  requiere promoción explícita y todas las puertas legales y operativas.

## 3. Secuencia de implementación

### Fase 3.0 — Consolidación y línea base

1. Mantener este documento como único plan canónico y retirar planes antiguos.
2. Actualizar arquitectura, casos de uso, proveedores, cumplimiento y backlog
   cuando cambie una decisión de infraestructura o producto.
3. Fijar Python y todas las dependencias; hacer reproducibles local y CI.
4. Mantener intactos `trader/`, los extractos cifrados y los artefactos
   generados.
5. Ejecutar en cada pull request un CI mínimo sin secretos ni red: suite Python
   completa y ranking histórico offline con datos ficticios.

**Salida:** pruebas Python y ranking histórico offline ejecutables desde un
entorno limpio tanto localmente como en PR, sin decisiones documentales
contradictorias.

### Fase 3.1 — TA-030: PostgreSQL y FastAPI reales

1. Introducir unidad de trabajo y repositorios; impedir que los servicios
   accedan a diccionarios internos del adaptador.
2. Implementar `PostgresStore`, transacciones y bloqueo concurrente de límites
   Free, con pruebas contra PostgreSQL 16.
3. Envolver el dispatcher en FastAPI y completar validación, autenticación,
   errores, `/health/live` y `/health/ready`.
4. Comprobar automáticamente la coherencia entre `openapi.yaml` y la
   aplicación.
5. Añadir imagen OCI sin privilegios y comandos separados para API y
   migraciones.

**Salida:** API v1 ejecutable con persistencia real, autorización entre ligas,
OpenAPI coherente y suite completa verde.

La instalación genérica resultante se conserva en `Dockerfile`, `compose.yaml`,
`.env.example`, `scripts/install-compose.sh`,
`scripts/verify-deployment.sh` y `doc/instalacion-despliegue.md`.

### Fase 3.2 — PWA: acceso, perfil y ligas

1. Crear Next.js/PWA con tokens de diseño, accesibilidad base,
   internacionalización ES/EN y cliente generado desde OpenAPI.
2. Integrar Auth0 mediante el BFF y sesión `HttpOnly`.
3. Implementar alta, perfil, edad, consentimiento, ligas, invitaciones,
   miembros, exportación y borrado.
4. Añadir E2E de dos personas y de acceso directo a una liga ajena.

**Salida:** dos cuentas pueden crear y gestionar una liga privada desde la PWA
sin exponer secretos ni confiar autorización al cliente.

### Fase 3.3 — Competiciones, cartera y ranking

1. Extender migraciones, servicios y OpenAPI para competiciones,
   `rules_snapshot`, participantes tardíos, carteras, órdenes, ejecuciones,
   historial y ranking.
2. Implementar en la PWA creación y comienzo de competición, envío y
   cancelación de órdenes, cartera, historial y ranking.
3. Mantener inmutables las reglas tras el inicio y responder `404` a recursos
   de ligas ajenas.

**Salida:** dos participantes completan una competición con fixtures de precio
deterministas y obtienen el mismo ranking reproducible.

### Fase 3.4 — Infraestructura y entrega continua

1. Definir como código Artifact Registry, Cloud Run, Scheduler, IAM, Secret
   Manager, Neon y la configuración necesaria de Vercel.
2. CI por PR: Python, TypeScript, lint, unitarias, contrato OpenAPI,
   PostgreSQL aislado y E2E cuando corresponda.
3. Tras cada merge: migración compatible hacia delante, API staging, PWA
   staging y smoke tests.
4. En producción, aplicar primero migraciones compatibles, desplegar API y
   promover después la PWA. Las migraciones destructivas usan expand/contract
   en cambios separados.
5. Mantener en el repositorio runbooks ejecutables de instalación,
   actualización, verificación, backup, restauración, rollback y retirada para
   cada entorno soportado.

**Salida:** staging reproducible y procedimiento probado de despliegue y
rollback; producción continúa cerrada.

### Fase 4 — Mercado y trabajos en segundo plano

1. Mantener fixtures durante desarrollo. Yahoo no se usa en TradeArena nuevo.
2. Integrar Massive únicamente después de confirmar por escrito la licencia
   de visualización y retraso uniforme.
3. Añadir outbox PostgreSQL y jobs separados para precios/calendario,
   ejecución, eventos corporativos, valoración y rankings.
4. Reclamar trabajo con bloqueo seguro, clave de idempotencia, reintentos
   limitados, métricas y auditoría.
5. Ante datos ausentes, dejar la orden pendiente y no fabricar precios ni
   snapshots.

**Salida:** una interrupción o repetición no pierde trabajo ni duplica
ejecuciones, apuntes o snapshots.

### Fase 5 — Facturación y beta

1. Activar derechos Friends/Club y límites transaccionales.
2. Integrar Stripe Checkout, portal y webhooks firmados e idempotentes.
3. Completar observabilidad, rate limits, seguridad de sesión, CORS/CSRF,
   carga, restauración, accesibilidad WCAG 2.2 AA y respuesta a incidentes.
4. Bloquear pagos y apertura pública hasta disponer de licencia de mercado,
   DPA, DPIA/ROPA, textos ES/EN y aprobación legal para España/UE.

### Fases 6–7 — Móvil y retirada del legado

1. Crear Expo/iOS/Android solo después de estabilizar la beta web.
2. No migrar extractos, operaciones ni importes reales. Como máximo, migrar
   porcentajes históricos con consentimiento explícito.
3. Retirar `trader/`, IMAP y GitHub Pages solo mediante un proyecto separado
   cuando el producto nuevo sea estable.

## 4. Verificación y aceptación

- Pruebas unitarias deterministas de dinero, órdenes, ledger, eventos y ranking.
- Mismas pruebas de contrato para memoria y PostgreSQL.
- Integración con PostgreSQL real, concurrencia de límites Free y rollback.
- Validación de OpenAPI y del cliente TypeScript generado.
- E2E de acceso, invitación, competición, orden, ejecución y ranking con dos
  participantes.
- Pruebas negativas de autorización, edad, sesión revocada, invitación ajena y
  privacidad.
- Repetir o interrumpir jobs no duplica ejecuciones, ledger ni snapshots.
- Migraciones verificadas sobre esquema vacío y sobre la versión anterior.
- Smoke tests de staging y restauración ensayada antes de beta.
- Instalación reproducible desde un clon limpio en cada entorno soportado,
  usando solo artefactos e instrucciones versionados en el repositorio.
- En cada fase deben pasar `python3 -m pytest tests/ -q`, el ranking histórico
  offline y, cuando exista, la verificación completa de la PWA.
- Todo cambio de rutas, contratos, despliegue, secretos, privacidad o reglas
  financieras actualiza en el mismo cambio `doc/arquitectura.md` y
  `doc/casos-de-uso.md`.

## 5. Ejecución con el modo objetivo de Codex

Se usa un objetivo por bloque anterior, nunca un único objetivo para todo el
producto. Cada objetivo se ejecuta en una rama `codex/<objetivo>` o worktree
independiente, termina con pruebas y documentación, y se fusiona antes de
abrir el siguiente. Dos objetivos no deben editar simultáneamente los mismos
archivos.

La consolidación y línea base se entrega primero mediante una rama con nombre
estable, `codex/baseline-tradearena`, y un PR hacia `main`. TA-030 comienza
después del merge, desde el `main` actualizado y en una rama nueva; no se
acumula sobre una rama de salvaguarda o de trabajo previo.

Secuencia recomendada:

1. consolidación y entorno reproducible;
2. TA-030, PostgreSQL y FastAPI;
3. PWA de acceso, perfil y ligas;
4. competiciones, cartera y ranking;
5. infraestructura y staging;
6. mercado y jobs;
7. Stripe y preparación de beta.

Cada `/goal` debe expresar resultado, límites y verificación, y referenciar
este documento en vez de copiar toda la especificación. El siguiente objetivo
es TA-031 y debe conservar los artefactos de instalación y ampliar la guía si
introduce nuevos procesos, variables o dependencias operativas.

```text
/goal Implementa TA-031 conforme a doc/plan-ejecucion-tradearena.md: PWA
responsive ES/EN, acceso Auth0 mediante BFF, perfil y sesión HttpOnly. Conserva
la autorización 404 entre ligas y actualiza instalación, variables, OpenAPI,
pruebas y documentación operativa en el mismo cambio.
```

## 6. Supuestos y puertas

- Este documento sustituye los dos planes anteriores.
- Vercel, Neon y Google Cloud son la plataforma de despliegue; Auth0, Massive
  y Stripe se mantienen.
- Las previews iniciales son PWA en Vercel más PostgreSQL aislado en CI, no
  entornos full-stack por PR.
- Se priorizan servicios con escala a cero y jobs programados frente a workers
  permanentes.
- Las reglas v1, precios comerciales y alcance España/UE permanecen como están
  en la especificación versionada.
- El legado continúa operativo y separado hasta la Fase 7.
- Un entorno no se considera soportado hasta que pueda instalarse, verificarse,
  actualizarse y recuperarse con artefactos versionados del repositorio.
