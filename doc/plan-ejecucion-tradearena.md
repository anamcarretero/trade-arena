# Plan definitivo de ejecución de TradeArena

## 1. Estado y arquitectura objetivo

TradeArena evoluciona como un monolito modular con el dominio financiero
Python independiente. Las Fases 0–2 están terminadas: existen reglas v1,
dominio reproducible, casos de uso de cuentas y ligas, API FastAPI,
persistencia PostgreSQL, migraciones e imagen OCI verificadas. TA-030 está
terminado. TA-031 completa acceso, perfil y PWA; TA-032 añade creación de liga,
invitaciones mediante enlace y administración de miembros; TA-033 incorpora la
página pública de planes y TA-034 la creación e inicio de competiciones con
`rules_snapshot` inmutable y TA-035 completa cartera, órdenes, ejecución con
fixtures, historial, ranking e incorporación tardía, incluida su ampliación de
cantidades fraccionadas, ejecuciones simuladas declaradas y correcciones
compensatorias. La siguiente entrega es TA-036.

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
- Las cantidades de acciones son decimales positivas con hasta ocho decimales.
  No hay ejecución parcial: una orden, aunque sea fraccionada, se ejecuta por
  toda su cantidad o no se ejecuta.
- El registro manual representa una ejecución simulada declarada dentro de
  TradeArena, no la importación ni custodia de operaciones reales de un broker.
  En v1 solo admite USD y `FX Rate = 1`; el backend conserva los campos
  declarados para validación y auditoría, pero aplica exclusivamente las reglas
  financieras de `rules_snapshot`.
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
3. Implementar alta, perfil, edad, consentimiento, ligas, invitaciones mediante
   enlace copiable y miembros. La exportación y borrado desde la PWA, así como
   el envío de correo, quedan fuera de esta fase.
4. Añadir E2E de dos personas y de acceso directo a una liga ajena.

**Salida:** dos cuentas pueden crear y gestionar una liga privada desde la PWA
sin exponer secretos ni confiar autorización al cliente.

### Fase 3.3 — TA-033: página pública de planes

1. Añadir a la PWA una ruta pública responsive ES/EN para consultar los planes,
   accesible desde la navegación pública sin iniciar sesión.
2. Presentar Free con sus límites vigentes y una llamada a la acción que lleve
   al acceso o a la aplicación según el estado de sesión.
3. Mostrar Friends y Club como planes futuros con la indicación visible
   «Próximamente»/«Coming soon», sin precios inventados, compra ni activación de
   derechos.
4. Mantener el sistema visual de TradeArena, accesibilidad base y pruebas de
   navegación, contenido bilingüe y responsive móvil sin scroll horizontal.

**Salida:** cualquier visitante puede comparar el plan Free con Friends y Club,
entender cuáles están disponibles y cuáles llegarán más adelante, sin que esta
tarea introduzca Stripe, suscripciones ni permisos de pago.

### Fase 3.4 — TA-034–TA-035: competiciones, cartera y ranking

1. Extender migraciones, servicios y OpenAPI para competiciones,
   `rules_snapshot`, participantes tardíos, carteras, órdenes, ejecuciones,
   historial y ranking.
2. Implementar en la PWA creación y comienzo de competición, envío y
   cancelación de órdenes, cartera, historial y ranking.
3. Mantener inmutables las reglas tras el inicio y responder `404` a recursos
   de ligas ajenas.

**Salida:** dos participantes completan una competición con fixtures de precio
deterministas y obtienen el mismo ranking reproducible.

### Ampliación TA-035 — fracciones y ejecuciones registradas manualmente

**Estado:** completada con las migraciones 006, 007 y 008, API/BFF/PWA bilingüe y pruebas
reproducibles en memoria y PostgreSQL 16.

1. Sustituir cantidades enteras por cantidades decimales positivas de hasta
   ocho decimales en dominio, aplicación, puertos, MemoryStore, PostgresStore,
   migraciones, API/OpenAPI y cliente generado. Mantener prohibidos corto,
   margen y ejecución parcial.
2. Añadir un caso de uso y endpoint separado `.../reported-trades` para
   registrar una ejecución simulada ya realizada con `Date`, `Ticker`, `Type`,
   `Quantity`, `Price per share`, `Total Amount`, `Currency` y `FX Rate`, más
   una clave idempotente. No modelarla como una orden pendiente enviada al
   mercado.
3. Validar en backend que la liga, competición y cartera pertenecen a la
   sesión; que la competición está activa; que la fecha no es futura, está
   dentro del calendario inmutable y no precede a la incorporación del
   participante; y que los registros se introducen cronológicamente respecto
   al último evento de la cartera.
4. En v1 exigir `Currency = USD` y `FX Rate = 1`. Admitir una comisión opcional
   tanto en órdenes como en operaciones declaradas. Una orden sin comisión usa
   al ejecutarse el respaldo del snapshot. En una declaración sin comisión,
   inferirla del bruto y `Total Amount`; si se proporciona, comprobar al céntimo
   la suma para compra o resta para venta. Rechazar sin mutaciones si falta
   saldo, posición o coherencia.
5. Crear atómicamente una orden ya ejecutada, una ejecución completa con
   `source=reported`, apuntes balanceados de ledger y auditoría. Una repetición
   con la misma clave por cartera devuelve el mismo resultado sin duplicar
   orden, ejecución, ledger, snapshot ni ranking.
6. No permitir edición o borrado destructivo de una ejecución financiera. Una
   corrección posterior usa un evento compensatorio explícito y auditable.
7. Añadir a la PWA un formulario responsive ES/EN y distinguir en cartera e
   historial las ejecuciones `fixture` y `reported`. TypeScript solo recoge y
   presenta datos y puede sugerir la diferencia aritmética en el campo de
   comisión; saldo, posición, validación financiera, redondeo y rentabilidad
   continúan en Python.
8. Añadir pruebas de dominio y aplicación, contrato MemoryStore/PostgresStore,
   migración desde `005_trading_ranking`, autorización `404`, precisión de
   fracciones, redondeos, orden temporal, saldo/posición, ledger, idempotencia,
   historial y ranking. Cubrir mediante E2E dos participantes combinando una
   orden con fixture y una ejecución registrada manualmente.

**Salida:** dos participantes pueden operar con acciones enteras o
fraccionadas y combinar órdenes normales con ejecuciones simuladas registradas
manualmente, obteniendo la misma cartera y ranking al reproducir las mismas
entradas, con el origen de cada ejecución claramente visible.

Quedan fuera la importación CSV, sincronización con brokers, operaciones reales
multidivisa, edición destructiva, mercado licenciado, jobs y conciliación
bancaria.

### Fase 3.5 — TA-036–TA-037: cierre funcional y accesibilidad de la PWA

1. Incorporar el centro de notificaciones y los flujos de exportación y
   borrado de cuenta ya soportados por la aplicación.
2. Completar accesibilidad WCAG 2.2 AA y E2E de dos participantes sobre los
   recorridos críticos.

**Salida:** la PWA cubre los flujos previstos para beta y supera la validación
de accesibilidad y los recorridos E2E antes del despliegue integrado.

### Fase 3.6 — TA-038: infraestructura y entrega continua

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
- Pruebas de cantidades fraccionadas hasta ocho decimales, redondeo monetario y
  ejecución completa sin rellenos parciales.
- Pruebas de ejecuciones registradas manualmente: fecha y orden cronológico,
  USD/FX, coherencia del total, saldo/posición, origen, compensación e
  idempotencia por cartera.
- Mismas pruebas de contrato para memoria y PostgreSQL.
- Integración con PostgreSQL real, concurrencia de límites Free y rollback.
- Validación de OpenAPI y del cliente TypeScript generado.
- E2E de acceso, invitación, competición, orden, ejecución y ranking con dos
  participantes.
- Pruebas negativas de autorización, edad, sesión revocada, invitación ajena,
  caducada o revocada y privacidad; esos enlaces responden `404` sin revelar la
  liga y la PWA muestra un mensaje comprensible, no el código HTTP.
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
4. TA-033, página pública de planes;
5. TA-034–TA-035, competiciones, cartera y ranking;
6. ampliación TA-035, fracciones y ejecuciones registradas manualmente;
7. TA-036–TA-037, cierre funcional y accesibilidad de la PWA;
8. TA-038, infraestructura y staging;
9. mercado y jobs;
10. Stripe y preparación de beta.

Cada `/goal` debe expresar resultado, límites y verificación, y referenciar
este documento en vez de copiar toda la especificación. TA-032 conserva los
artefactos de instalación, el BFF y el sistema visual de TA-031. El siguiente
objetivo es TA-036. No activa notificaciones, exportación, borrado desde
la PWA, importación de brokers, Friends, Club ni facturación.

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
