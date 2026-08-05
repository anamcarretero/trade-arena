# Plan de ejecución: plataforma privada de inversión simulada

## 1. Límites de producto

El producto será una competición privada de inversión **simulada**. No
ejecutará operaciones con dinero real, no custodiará fondos, no admitirá
premios, botes ni transferencias entre participantes, y no ofrecerá
asesoramiento financiero personalizado.

La privacidad será el comportamiento por defecto: las ligas serán privadas y
las personas podrán competir mediante alias.

### Planes iniciales

| Plan | Capacidad | Precio orientativo |
|---|---:|---:|
| Free | Una liga privada activa, hasta 2 personas, capital virtual fijo de 1.000 € | Gratis |
| Friends | Hasta 10 personas | 4,99 €/mes al organizador |
| Club | Hasta 30 personas y cinco ligas activas | 9,99 €/mes al organizador |

Los planes de pago tendrán opción anual. La capacidad se factura al
organizador, no a cada participante.

## 2. Reglas iniciales de competición

Antes de comenzar, las reglas se fijan y quedan inmutables para esa
competición:

- moneda base EUR;
- capital virtual inicial definido por la competición;
- operaciones simuladas ejecutadas al cierre diario o, si no existe, al
  siguiente cierre disponible;
- precios reproducibles y conservados con su procedencia;
- clasificación por rentabilidad ponderada en el tiempo (*time-weighted
  return*);
- identidad pública mediante alias privados.

Quedan fuera del alcance inicial los instrumentos o reglas que requieran una
valoración no reproducible, el dinero real, la custodia, los premios y las
recomendaciones individualizadas.

## 3. Arquitectura objetivo

Se construirá un monolito modular:

- API REST documentada con OpenAPI en FastAPI;
- PostgreSQL como base de datos transaccional;
- cola de trabajos para precios, valoración, rankings y procesos asíncronos;
- reutilización del motor financiero Python actual, aislado y probado como
  núcleo de dominio;
- proveedor de datos de mercado con licencia adecuada;
- web en Next.js;
- aplicaciones Expo/React Native en una fase posterior, compartiendo API,
  tipos y *design tokens* con la web.

La separación prioritaria es entre dominio financiero, persistencia, API,
trabajos de fondo e interfaces; no es necesario dividir en microservicios en
la primera versión.

## 4. Modelo de datos inicial

El diseño incluirá, como mínimo, las siguientes entidades:

- `users`
- `leagues`
- `league_members`
- `competitions`
- `portfolios`
- `orders`
- `ledger_entries`
- `instruments`
- `market_prices`
- `valuation_snapshots`
- `ranking_snapshots`
- `subscriptions` y `billing_events`
- `audit_events`

Las órdenes y apuntes de libro mayor permitirán reconstruir una cartera y su
valoración. Los *snapshots* conservarán resultados publicados y facilitarán
la auditoría y el diagnóstico de una clasificación.

## 5. Identidad, autorización y facturación

La autenticación combinará enlace mágico por correo con Apple y Google. La
autorización de pertenencia a una liga se verificará siempre en servidor; no
se confiará en el estado del cliente. Las invitaciones serán de un solo uso y
con caducidad.

Los límites de cada plan se aplicarán transaccionalmente al crear ligas,
invitar miembros o activar competiciones, para evitar exceder capacidad por
condiciones de carrera.

Stripe será la fuente de verdad para suscripciones web: Checkout, portal de
cliente y *webhooks* firmados. La facturación móvil mediante StoreKit y Google
Play Billing se incorporará después; sus eventos se validarán en servidor y
se normalizarán con el mismo estado de suscripción.

## 6. Experiencia de usuario mínima

La primera experiencia web cubrirá:

1. Registro e inicio de sesión.
2. Creación de liga o acceso mediante invitación.
3. Configuración de una competición y confirmación de reglas inmutables.
4. Operaciones simuladas.
5. Ranking y evolución de la competición.
6. Privacidad, cuenta, plan y facturación.

La interfaz debe explicar de forma visible que se trata de una simulación y
evitar lenguaje que sugiera ejecución real, consejo financiero o premio
económico.

## 7. Seguridad, privacidad y cumplimiento

- Minimizar los datos personales recogidos y mantener las ligas privadas por
  defecto.
- Mantener trazabilidad de acciones críticas mediante `audit_events`.
- Definir políticas de retención, eliminación y exportación de datos.
- Usar únicamente datos de mercado con licencia compatible con el producto.
- No importar extractos ni operaciones financieras reales en el MVP.
- Completar revisión legal para España/EEE antes del lanzamiento comercial,
  incluyendo privacidad, consumo, fiscalidad aplicable, comunicaciones y la
  delimitación expresa frente a servicios de inversión.

El alcance inicial se limitará a personas adultas en España/EEE y a ligas
privadas.

## 8. Migración desde Trade Arena

La solución actual basada en GitHub, IMAP y ranking estático seguirá operando
como legado durante la transición. Se separará progresivamente el cálculo
financiero de la salida a archivos, conservando el repositorio actual como
referencia operativa mientras se valida el nuevo sistema.

No se migrarán extractos reales. Solo podrán migrarse porcentajes históricos
con consentimiento explícito de cada persona, sin importes, operaciones ni
otros datos de cartera.

## 9. Orden de implementación

El *backlog* se ejecutará en este orden, respetando dependencias:

1. Decisiones de producto y cumplimiento.
2. Aislar y probar el motor financiero existente.
3. Backend, base de datos, autenticación, ligas, invitaciones y límites Free.
4. Web principal.
5. Trabajadores, precios y valoraciones.
6. Stripe.
7. Beta cerrada, carga, seguridad y revisión legal.
8. Aplicaciones Expo y facturación móvil.
9. Migración y retirada progresiva del legado.

### Dependencias operativas

- No abrir beta comercial ni facturación antes de cerrar límites de producto,
  datos licenciados y revisión legal.
- No publicar rankings antes de que la valoración sea reproducible, auditable
  y cubierta por pruebas.
- No retirar el flujo heredado antes de validar migración consentida y la
  continuidad de cálculos.

## 10. Criterios de aceptación

La primera versión estará lista para beta cuando:

- impida por diseño premios, transferencias, custodia y operaciones reales;
- haga cumplir los límites Free y de pago de forma transaccional;
- aplique autorización de membresía en todas las rutas protegidas;
- genere invitaciones de un uso y caducidad verificables;
- conserve precios, valoraciones y rankings reproducibles y auditables;
- calcule la rentabilidad ponderada en el tiempo conforme a las reglas de la
  competición;
- exponga una API REST documentada y una web que cubra alta, liga,
  competición, operaciones simuladas, ranking, privacidad y facturación;
- procese los webhooks de Stripe con verificación de firma e idempotencia;
- tenga pruebas unitarias del motor, pruebas de integración de API y base de
  datos, pruebas de autorización y límites, y pruebas operativas de colas,
  reintentos y recuperación;
- disponga de observabilidad: registros estructurados, métricas de API,
  trabajos, valoración y facturación, alertas de fallos y trazas/auditoría de
  acciones críticas;
- complete la revisión de seguridad, carga y legal para España/EEE.

## 11. Decisiones abiertas

Antes de comprometer el lanzamiento deben aprobarse explícitamente:

1. Confirmación de que no habrá premios ni transferencias entre participantes.
2. Alcance geográfico: España/EEE, personas adultas y solo ligas privadas.
3. Mercado inicial: instrumentos EUR exclusivamente o instrumentos de EE. UU.
   con conversión EUR/USD y reglas de tipo de cambio reproducibles.
4. Precios definitivos, valor anual y condiciones de Friends y Club.
5. Tratamiento del legado y consentimiento para migrar, como máximo,
   porcentajes históricos.
