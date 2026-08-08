# Casos de uso y flujos operativos

## Actores

| Actor | Objetivo | Permisos o secretos necesarios |
|---|---|---|
| Jugador | aportar/actualizar extracto y consultar clasificación | solo su correo registrado en la vía recomendada |
| Administrador de la liga | registrar jugadores, configurar secretos y supervisar automatizaciones | administración de GitHub y del buzón |
| Visitante público | consultar la clasificación y fichas | ninguno |
| GitHub Actions | ingestar, calcular y publicar | secretos y permisos `contents: write` del repositorio |

Los actores anteriores pertenecen al ranking histórico. En TradeArena v1 se
añaden participante autenticado, propietario y administrador de liga. Sus
recursos son privados y solo se exponen por `/api/v1` tras validar sesión y
membresía activa.

## 0. Flujos del producto nuevo hasta TA-039

1. Identidad verifica un enlace de email de un solo uso o claims Google con
   emisor, audiencia y email verificado; después se emite una sesión propia.
2. La persona mayor de edad completa nombre, idioma y consentimiento. Desde la
   PWA puede exportar sus propios datos o borrar la cuenta; el borrado exige
   confirmación, revoca todas las sesiones y anonimiza sin destruir la auditoría
   financiera.
3. Free permite crear una liga activa con capital virtual inicial fijo de
   3.000 USD por competición. El creador es propietario y puede invitar un
   segundo miembro. La aplicación genera un enlace para copiar y compartir;
   todavía no envía la invitación por correo. La invitación ocupa plaza, está
   ligada al email, caduca y puede revocarse.
4. Solo propietario/administrador invita o expulsa. La persona expulsada deja
   de tener acceso; su historial se conserva para auditoría.
5. Cada acceso directo como `GET /api/v1/leagues/{id}` vuelve a comprobar la
   pertenencia. Una cuenta externa recibe `404`, también al intentar mutaciones,
   para evitar enumerar ligas privadas.
6. Al abrir un enlace de invitación, la persona inicia sesión con el email
   invitado y lo acepta. Si el enlace no es válido, ha caducado, fue revocado o
   pertenece a otro email, la API responde `404` sin revelar la liga y la PWA
   muestra: «No puedes acceder a esta liga con esta invitación. Comprueba que
   has iniciado sesión con el correo invitado o solicita un enlace nuevo».

TA-031 incorpora la PWA para acceso, perfil e idioma. El contrato HTTP está en
`tradearena/presentation/openapi.yaml`; FastAPI incluye sondas `/health/live`
y `/health/ready`, intercambio Auth0 exclusivo del BFF y comprobación
automática de rutas/`operationId`. Las pruebas de abuso directo siguen en
`tests/tradearena/test_authorization.py` y verifican que la incorporación del
BFF no cambia el `404` de ligas ajenas.

### Ligas e invitaciones en la PWA

1. La portada autenticada lista únicamente las ligas de la sesión y las
   invitaciones pendientes ligadas a su email verificado.
2. Una persona sin liga propia crea una liga Free. FastAPI bloquea la cuenta y
   vuelve a comprobar dentro de la transacción que no posea otra liga activa.
3. El detalle presenta dos plazas: miembro activo, invitación pendiente o
   plaza disponible. Solo propietario o administrador ve los emails y acciones
   de administración.
4. Al invitar, el backend normaliza el email, bloquea la liga, reserva la plaza
   durante siete días y devuelve el identificador opaco. La PWA construye un
   enlace copiable; no envía correo.
5. La persona invitada abre el enlace, inicia sesión con el email indicado y
   acepta. FastAPI bloquea invitación y liga antes de convertir la reserva en
   membresía. Un enlace ajeno o no utilizable produce el mismo `404` y mensaje.
6. Revocar conserva la fila de invitación y expulsar fija `removed_at`; ambas
   acciones añaden auditoría y liberan la plaza sin borrar el historial.

### Acceso Auth0, perfil e idioma en la PWA

1. La persona elige ES o EN y pulsa acceso. El BFF genera `state`, `nonce` y
   PKCE; solo guarda la transacción cifrada en una cookie `HttpOnly` temporal.
2. Auth0 Universal Login ofrece email y Google. El callback se ejecuta en
   servidor, comprueba `state` e intercambia el código sin exponer tokens.
3. FastAPI recibe la aserción mediante el canal autenticado BFF↔API, valida
   criptografía, emisor, audiencia, nonce y email verificado, enlaza o crea la
   cuenta y emite una sesión propia opaca.
4. El BFF cifra esa sesión en cookie `HttpOnly`; el navegador solo conoce el
   estado visual. Las llamadas a `/api/v1/me` y perfil salen desde Next.js.
5. Una cuenta sin perfil completa nombre, fecha de nacimiento, consentimiento
   e idioma. FastAPI vuelve a imponer idioma permitido, nombre y edad mínima de
   18 años, aunque se manipule el formulario.
6. Al cerrar sesión, el BFF revoca el registro servidor, borra la cookie y
   termina la sesión de Auth0. Cambiar `/es` por `/en` adapta la interfaz; al
   guardar perfil, la preferencia queda persistida en la cuenta.

### Pricing público de TA-033

1. Cualquier visitante puede abrir `/{locale}/pricing` y acceder desde la
   navegación pública sin iniciar sesión.
2. La página presenta Free con una liga activa, dos plazas y 3.000 USD de
   capital virtual inicial por competición, y permite continuar al acceso o a
   la aplicación si ya existe una sesión `HttpOnly` válida para el BFF.
3. Friends y Club se muestran para anticipar la evolución del producto, pero
   con «Próximamente»/«Coming soon» y sin una acción de compra habilitada.
   Friends comunica hasta cinco jugadores, competiciones de hasta un año y
   capital virtual inicial configurable; Club comunica hasta veinte jugadores
   y hasta cinco ligas activas.
4. TA-033 no crea suscripciones, cobros ni derechos nuevos; esas capacidades
   siguen perteneciendo a la Fase 5.

### Competiciones y `rules_snapshot` de TA-034

1. Propietario o administrador abre el detalle de una liga privada y crea un
   borrador de competición con nombre, fecha de inicio y fecha de fin. Un
   miembro puede consultar los borradores, pero no crearlos ni iniciarlos.
2. Mientras el estado es `draft`, `rules_snapshot` permanece vacío. El
   calendario debe incluir zona horaria y el fin ser posterior al inicio; la
   API vuelve a validar ambas condiciones aunque se manipule el formulario.
3. Al pulsar «Iniciar competición»/«Start competition», el backend autentica
   la sesión, comprueba de nuevo la membresía y el rol y bloquea las filas de
   liga y competición dentro de la transacción.
4. En ese instante copia calendario XNYS, zona `America/New_York` y reglas v1 a
   `rules_snapshot`. Para Free fija siempre `3000.00 USD` de capital virtual
   inicial por competición; el formulario no admite otro importe.
5. El snapshot queda inmutable: una segunda petición de inicio se rechaza y
   PostgreSQL impide sustituirlo incluso fuera del caso de uso. Cambiar las
   reglas generales más adelante no altera una competición ya iniciada.
6. La PWA confirma de forma visible en español o inglés que calendario y reglas
   se copiaron de forma inmutable y muestra el capital y calendario fijados.
7. Listar, consultar, crear o iniciar mediante una liga ajena devuelve `404`.
   También responde `404` si el id de competición pertenece a otra liga, sin
   revelar cuál de los dos recursos existe.

TA-034 no crea participantes, carteras, órdenes, ejecuciones, historial ni
ranking y tampoco incorpora participantes tardíos. Esos flujos empiezan en
TA-035; notificaciones, exportación, borrado y facturación siguen diferidos.

### Cartera, órdenes e incorporación tardía de TA-035

1. Al iniciar una competición, el backend incorpora a cada miembro activo y
   crea su cartera. El importe se lee de `rules_snapshot`; Free concede
   exactamente `3000.00 USD`. Para estos participantes iniciales, `joined_at`
   es el comienzo del calendario aunque el borrador se active más tarde; así
   pueden declarar operaciones desde la fecha competitiva fijada.
2. Si una persona acepta la invitación después del inicio, membresía,
   participación y cartera se crean en la misma transacción. Recibe los
   `3000.00 USD` completos y aparece con «Incorporación tardía»/«Late entry».
3. La PWA envía una compra o venta de una cantidad positiva con hasta ocho
   decimales, de mercado o límite,
   para sesión regular o regular más ampliada. La Server Action transmite los
   campos y una clave idempotente; FastAPI vuelve a validar sesión,
   pertenencia, calendario y reglas.
4. El backend consulta únicamente fixtures del puerto de mercado en esta fase.
   Ordena cotizaciones e ignora cualquiera anterior a la orden. El formulario
   admite una comisión opcional no negativa. Una ejecución siempre cubre toda
   la cantidad y usa esa comisión; si se omitió, carga `1.15 USD` en regular o
   `2.99 USD` en ampliada, según el snapshot.
5. Si falta efectivo o posición, la orden se rechaza sin ejecución ni comisión.
   No existe corto, margen ni ejecución parcial. Una orden pendiente
   es GTC hasta ejecución, cancelación, fin o suspensión definitiva.
6. La cartera devuelve efectivo, posiciones, valoración, retorno, órdenes y
   ejecuciones. El ranking reproduce las carteras con los mismos fixtures,
   desempata de forma estable, persiste su hash y marca incorporaciones tardías.
7. Una liga, competición, cartera u orden ajena responde `404`. Expulsar corta
   el acceso, pero conserva participación, órdenes, ejecuciones y ledger. El
   navegador no recibe sesión interna, tokens, secretos ni credenciales.

### Operaciones declaradas y correcciones de la ampliación TA-035

1. Un participante registra desde la PWA una ejecución simulada ya realizada
   mediante fecha/hora con Madrid por defecto o UTC, ticker, compra/venta,
   cantidad de hasta ocho decimales, precio por acción, importe total, comisión
   opcional, USD, FX 1 y clave idempotente.
   No se crea primero una orden pendiente ni se envía nada al mercado.
   Precio e importe admiten coma o punto decimal; el backend los normaliza
   antes de aplicar las reglas financieras.
2. FastAPI vuelve a autenticar y Python oculta con `404` ligas, competiciones,
   carteras u operaciones ajenas. La competición debe estar activa; la fecha no
   puede ser futura, queda dentro del calendario fijado y no precede a la
   incorporación. TA-037 admite altas retroactivas: Python reproduce los
   eventos y vuelve a validar saldo y posición en la fecha declarada.
3. Si la comisión queda vacía, la PWA sugiere en su campo la diferencia entre
   bruto y total. El backend vuelve a calcularla con `Decimal`: en compra es
   total menos cantidad × precio y en venta es cantidad × precio menos total.
   Si se proporciona una comisión, debe ser no negativa y coincidir al céntimo.
   USD/FX 1, saldo y posición se validan antes de mutar nada.
4. El éxito persiste en la misma transacción una orden ya `filled`, ejecución
   completa `source=reported`, ledger balanceado y auditoría. Repetir la misma
   clave y payload devuelve la cartera existente sin duplicar ningún registro.
5. El historial etiqueta `fixture` para ejecuciones de mercado y `reported`
   para declaraciones del usuario. El cálculo de TypeScript solo completa el
   campo como ayuda; Python es la autoridad sobre comisión, total, saldo,
   posición y rentabilidad.
6. Corregir una declaración crea una orden, ejecución y asiento inversos con
   `correction_of`; el original permanece visible. Una operación ya compensada
   no admite una segunda corrección, y nunca existe edición o borrado
   destructivo del historial financiero.

TA-035 no incorpora notificaciones, exportación o borrado desde la PWA,
facturación, Stripe, mercado licenciado, jobs programados ni staging.

### Notificaciones, exportación y borrado de TA-036

1. La persona abre «Notificaciones»/«Notifications» desde la PWA. FastAPI lista
   únicamente sus filas, ordenadas de más reciente a más antigua, con estado
   leído/no leído. No se expone `user_id` ni contenido sensible del payload.
2. «Marcar como leída» vuelve a autenticar en el backend y fija `read_at` solo
   si la notificación pertenece a la sesión. Repetir la petición devuelve la
   misma fecha sin una segunda mutación. Una notificación ajena o inexistente
   produce `404`.
3. En «Cuenta y privacidad»/«Account and privacy», descargar la exportación
   hace que el BFF solicite `GET /api/v1/me` con la sesión `HttpOnly` y entregue
   un JSON de esquema 1 sin caché. Contiene solo cuenta, perfil, membresías,
   invitaciones recibidas, notificaciones, auditoría relacionada y el historial
   financiero completo de las carteras propias, incluido ledger. No contiene
   el sujeto de la identidad externa, sesiones, tokens, secretos, credenciales, rankings
   compartidos ni datos de otro participante.
4. La exportación no incorpora una hora variable de generación y ordena sus
   colecciones, por lo que el mismo estado produce el mismo documento.
5. Para borrar, la persona debe activar una confirmación explícita. La Server
   Action la transmite, pero Python vuelve a exigir el booleano verdadero; una
   llamada manipulada sin confirmación se rechaza sin cambios.
6. El borrado se ejecuta en una transacción: revoca todas las sesiones, elimina
   identidades y perfil, anonimiza el email de cuenta e invitaciones, borra las
   notificaciones privadas y retira membresías activas. Conserva UUID internos,
   auditoría, participación, carteras, órdenes, ejecuciones y ledger.
7. La cookie `HttpOnly` se elimina en el BFF tras el éxito. La cuenta borrada no
   puede reutilizar ninguna sesión ni acceder a ligas, competiciones, carteras,
   órdenes, operaciones o notificaciones. Los recursos privados ajenos siguen
   respondiendo `404`.

TA-036 no incorpora el trabajo general WCAG 2.2 AA de TA-038, infraestructura
cloud, mercado licenciado, jobs, brokers, Friends, Club, Stripe ni facturación.

### Dashboard de competición de TA-037

1. Un miembro abre una tarjeta de competición y navega a su detalle. FastAPI
   vuelve a comprobar sesión, membresía activa, liga y pertenencia de la
   competición; cualquier combinación ajena responde `404`. Un borrador devuelve
   identidad y `data_status=empty` sin crear cartera ni snapshot.
2. Para cada participante se generan jornadas reales XNYS desde `joined_at`.
   Los cierres usan las 16:00 de Nueva York y la sesión actual aparece
   provisional únicamente desde la apertura de las 09:30; antes se mantiene el
   cierre anterior. Fin de semana y festivo no crean puntos.
3. La proyección reproduce ejecuciones, comisiones y movimientos
   compensatorios. Una cotización ausente no se rellena: la jornada permanece
   visible pero incompleta y ningún retorno parcial se etiqueta como definitivo.
4. La pantalla presenta líder, gap, series acumuladas, mejor jornada, ganadores
   mensuales/diarios, resultados, estadísticas, rachas, badges, portfolios en
   pesos con `CASH`, ocho operaciones saneadas e insights deterministas. Un
   jugador o una jornada se despliega para mostrar su detalle porcentual.
5. Los expulsados dejan de participar en la clasificación viva y conservan su
   historia. Una cuenta eliminada aparece como participante anónimo. Los
   empates se ordenan de manera estable por `user_id`.
6. De otros jugadores se ven nombre, porcentajes, ticker, compra/venta o
   corrección, origen, fechas, estadísticas y badges. Nunca se ven cantidades,
   precio, total, comisión, efectivo/equity absolutos, ledger, órdenes o claves
   idempotentes. La sección «Mi cartera y operaciones» mantiene los importes
   propios y los formularios ya autorizados.
7. Registrar o compensar una operación revalida el detalle y reconstruye los
   puntos derivados. No modifica ni elimina la ejecución o el ledger original.
8. Los «Insights de liga» son reglas locales estables sobre liderazgo,
   distancia, jornadas y rachas. No se presentan como IA, no envían portfolios
   a terceros y no contienen consejos ni predicciones.

TA-037 no importa CSV/PDF, no consulta el ranking histórico ni sus datos
cifrados y no sincroniza brokers. En desarrollo local se puede activar Yahoo
con `MARKET_DATA_PROVIDER=yahoo`: se consulta una ventana de cierres por
símbolo a través de `MarketDataPort`, y cualquier fallo deja las jornadas
afectadas incompletas. Esta configuración no se utiliza en despliegues públicos.
Las fichas enriquecidas de
ticker, históricos, consenso neutral y récord de activo esperan a la Fase 4 y a
una licencia confirmada.

### Accesibilidad y recorrido E2E de TA-038

1. Una persona que navega por teclado encuentra primero «Saltar al contenido
   principal»/«Skip to main content». Tras seguir un enlace interno, el foco se
   restaura en el `h1` de destino; los controles conservan un indicador visible
   y un área táctil suficiente.
2. Cada ruta localizada actualiza `lang` a `es` o `en`. Landmarks,
   encabezados, etiquetas, ayudas, estados, gráficas y detalles desplegables
   tienen nombre o alternativa textual equivalente en el idioma elegido.
3. La validación nativa lleva el foco al primer campo obligatorio incorrecto.
   Los errores se anuncian de forma asertiva y las confirmaciones de forma
   cortés; carga, fallo de API, datos incompletos y cotización ausente tienen un
   mensaje perceptible que no depende exclusivamente del color o movimiento.
4. Con movimiento reducido, la PWA elimina desplazamiento suave y reduce
   transiciones y animaciones. A 375 y 414 px los recorridos críticos refluyen
   sin desplazamiento horizontal.
5. El E2E abre dos contextos aislados. El propietario crea la liga, invita al
   segundo email y este acepta; después crea e inicia una competición. El
   propietario envía una orden con fixture y el segundo jugador declara una
   operación simulada. Ambos consultan dashboard, ranking, cartera propia y
   actividad en ES/EN.
6. El escenario usa importes y comisiones señuelo diferentes para cada
   participante. Comprueba expresamente que la pantalla y exportación de una
   sesión no contienen cantidades, precios, importes, comisiones, efectivo,
   patrimonio, órdenes, ledger ni identificadores financieros de la otra. El
   dashboard compartido conserva únicamente nombre, porcentajes, pesos y
   operaciones saneadas; los importes solo aparecen en la cartera propia
   autorizada y las salidas públicas siguen respetando `show_amounts`.
7. Una tercera sesión ajena no puede abrir la liga ni una invitación no ligada
   a su email. La PWA mantiene el mensaje uniforme de recurso privado sin
   revelar si existe. También se prueban carga diferida, error recuperable,
   dashboard incompleto y lista de cotizaciones ausentes.

La suite `pnpm test:e2e` incluye el recorrido funcional y los análisis axe. Se
puede ejecutar solo la auditoría automática con `pnpm test:a11y`. La cobertura
automatizada complementa la revisión semántica, de teclado, foco, contraste,
movimiento, táctil y responsive; no se presenta como sustituto de una auditoría
asistida completa. TA-038 no introduce ninguna capacidad de TA-039.

Si una navegación documental pierde la red, el service worker presenta el
documento offline precargado. No intercepta las peticiones RSC ni otros recursos
internos de Next.js y nunca guarda pantallas privadas. Si también falta el
fallback, responde `503` sin producir un error de red sintético. En desarrollo
local la PWA retira workers y cachés persistentes antes de continuar, por lo que
un worker de una ejecución anterior no puede bloquear una ruta dinámica.

Para ejecutar el backend contra PostgreSQL se aplican primero las migraciones
con `DATABASE_URL=... python3 -m tradearena migrate` y se arranca después la API
con `python3 -m tradearena serve`. Liveness solo
comprueba el proceso; readiness ejecuta una consulta contra PostgreSQL y
responde `503` si no está disponible. Las pruebas de integración usan
exclusivamente `TEST_DATABASE_URL`, crean un esquema aislado y comprobable, y
lo eliminan al terminar.

### Flujo de desarrollo y preview de Fase 3

1. Cada pull request instala Python 3.12 y las versiones exactas de
   `requirements.txt`, levanta PostgreSQL 16 aislado, prueba migraciones sobre
   esquema vacío y versión anterior, ejecuta Python, ranking offline, OpenAPI,
   lint, tipos, unitarias web, build, Playwright, axe, Docker/Compose e IaC.
   No requiere extractos reales ni secretos.
2. La consolidación inicial se fusiona desde `codex/baseline-tradearena`; el
   trabajo TA-030 comienza después desde el `main` actualizado en otra rama.
3. Un PR de interfaz obtiene una preview Vercel que consume fixtures o el API
   integrado de staging mediante el BFF; nunca abre una conexión del navegador
   a PostgreSQL.
4. Si el PR cambia backend, persistencia o migraciones y están configurados
   `NEON_PROJECT_ID`/`NEON_API_KEY`, CI crea una rama Neon efímera con
   caducidad, aplica migraciones, ejecuta integración y la elimina en `always()`.
   Sin credenciales, esta ampliación queda omitida de forma visible y sigue
   siendo obligatorio PostgreSQL 16 aislado.
5. No se crea una API Cloud Run por PR. Tras fusionar en `main`, se despliega
   staging, se ejecutan smoke tests y solo entonces el cambio puede promoverse.
6. Producción sigue bloqueada hasta superar revisión legal, licencia de mercado,
   DPA, restauración y seguridad. El ranking histórico continúa en GitHub Pages
   durante toda esta transición.

### Entrega y operación de staging de TA-039

1. `scripts/staging/bootstrap.sh plan` usa credenciales del entorno y genera un
   plan Terraform sin crear recursos. `apply` exige frase explícita porque los
   proveedores pueden tener coste.
2. Después del apply, el operador carga valores en los nombres de Secret
   Manager y el custom environment Vercel creados. Los valores no se imprimen,
   versionan ni guardan en Terraform. Auth0 autoriza el origen HTTPS estable;
   el repositorio no crea dominios.
3. Tras un merge a `main`, GitHub obtiene GCP por OIDC restringido, publica el
   backend por digest, ejecuta primero la migración, despliega la API y verifica
   readiness, despliega después la PWA en `staging` y termina con smoke tests.
4. Un fallo en cualquier etapa deja el workflow fallido. API y PWA pueden
   volver a digest/deployment anterior compatible; el esquema no se baja. Las
   contracciones usan expand/contract en un cambio posterior.
5. `backup.sh` genera un dump privado verificable; `restore-drill.sh` exige una
   base aislada distinta y vuelve a migrarla. `diagnose.sh` muestra estado,
   ejecuciones y logs recientes sin recuperar secretos.
6. `retire.sh` solo planifica por defecto. Aplicar exige confirmación, backup
   comprobado y desactivar deliberadamente la protección del servicio; después
   se revocan tokens externos según el runbook.

TA-039 no añade outbox, jobs financieros, Massive, Stripe, brokers,
importaciones ni producción. El código puede validarse localmente, pero staging
no se declara desplegado hasta ejecutar smoke y restauración reales.

### Instalar o actualizar TradeArena

1. El operador parte de un clon y copia `.env.example` a `.env`, sin versionar
   secretos.
2. `scripts/install-compose.sh` valida Docker y Compose, construye la imagen y
   espera a PostgreSQL 16.
3. El servicio finito `migrate` aplica las migraciones pendientes. Si falla, la
   API nueva no arranca.
4. API y PWA/BFF se ejecutan sin privilegios, PostgreSQL permanece en una red
   privada y el volumen conserva los datos entre reinicios.
5. `scripts/verify-deployment.sh` exige liveness, readiness, OpenAPI, salud web,
   ambas portadas de idioma y manifest antes de considerar terminada la instalación.
6. En otro servidor o proveedor se usa la misma imagen y la secuencia
   migrar→servir→verificar. Sus diferencias, secretos, IaC, backup,
   restauración y rollback deben añadirse al repositorio antes de declararlo
   soportado.

El procedimiento completo y los comandos de diagnóstico viven en
`doc/instalacion-despliegue.md`.

## 1. Alta de un jugador y carga por email

Es el flujo preferente porque no concede acceso al repositorio.

1. El administrador registra al jugador en la variable de Actions
   `PLAYER_EMAILS`, con el mapa `id -> {email, name, currency, show_amounts}`.
2. El jugador exporta el CSV desde Revolut y lo envía como adjunto al buzón
   privado desde esa dirección registrada.
3. `inbox.yml` se activa por el timbre de Gmail (`repository_dispatch`) o
   manualmente y ejecuta `python -m trader inbox`.
4. `inbox.py` lee mensajes no vistos, comprueba que la dirección pertenece al
   mapa y valida `Authentication-Results`: acepta DMARC aprobado o DKIM
   aprobado alineado con el dominio del remitente.
5. Extrae el primer adjunto CSV, lo parsea para comprobar que haya operaciones
   Revolut reconocibles, cifra su contenido con `TRADER_KEY` y actualiza
   `players/<id>/trades.csv.enc`. Si no existe, crea también `player.json`.
6. Si cambió `players/`, el workflow recalcula y publica el ranking. El último
   extracto recibido sustituye el anterior; no constituye un historial de
   cargas.

Resultados de rechazo habituales: remitente no registrado, cabecera de
autenticación ausente/no válida, adjunto no CSV o CSV sin eventos reconocibles.
Todos se marcan como vistos salvo al ejecutar `--dry-run`, por lo que el
administrador debe revisar el log del workflow y corregir el origen antes de
reenviar el correo.

## 2. Alta o actualización por web/CLI

Es una alternativa avanzada para quien dispone de acceso al repositorio.

- **Web:** `docs/subir.html` cifra el archivo en el navegador y lo sube con un
  token GitHub de permisos Contents. Tras ello dispara `extracto-subido` para
  que corra `ranking.yml`.
- **CLI:** el jugador crea `players/<id>/player.json`, ejecuta
  `python -m trader encrypt extracto.csv --out players/<id>/trades.csv.enc` y
  abre un PR o publica el fichero cifrado siguiendo el proceso autorizado.

En ambos casos la persona debe usar la frase compartida correcta. Un cifrado
con otra frase se conserva pero no se puede calcular: el ranking lo lista en
`pending.json` y el workflow abre o actualiza la issue “Extractos sin
descifrar”.

Para el push directo, `PLAYER_OWNERS` asocia el id a un usuario GitHub. El
guardián exime a administradores y bots; para el resto revierte un cambio que
salga de `players/<id>/`, afecte a un id no registrado o pertenezca a otra
persona. No usar esta vía para otorgar acceso amplio a usuarios no confiables.

## 3. Recalcular la competición

El ranking se actualiza al cambiar `players/**` o `trader/**`, mediante el
evento `extracto-subido`, y bajo demanda desde Actions. El administrador puede
reproducirlo localmente:

```bash
python -m trader ranking --refresh
```

El comando hace lo siguiente:

1. Descubre jugadores y descifra sus extractos usando `TRADER_KEY` o la clave
   específica disponible.
2. Normaliza CSV a eventos y busca precios de cierre. `--refresh` intenta
   actualizar Yahoo; si la caché cubre el rango y Yahoo falla, conserva la
   caché.
3. Reconstruye cada cartera, rebasa el retorno al inicio de la competición y
   omite jugadores sin operaciones legibles.
4. Calcula posiciones/pesos, contribuciones por ticker, consenso de analistas
   opcional e insignias incrementales.
5. Genera `docs/ranking.md`, `docs/index.html`, `data/public/*.json`,
   `data/badges.json` y `pending.json` (este último está ignorado por Git).

Para una prueba completamente aislada de la red y de extractos reales:

```bash
python3 -m trader ranking --players-dir examples/players \
  --prices-dir examples/prices --offline
```

## 4. Consultar la clasificación pública

El visitante abre GitHub Pages, cuyo contenido proviene de `docs/index.html`.
No hay solicitudes a un backend propio: la página contiene su payload y usa
precios, pesos y porcentajes ya preparados. Puede consultar:

- tabla y gráfica de rentabilidad acumulada, jornadas y ganadores diarios;
- ficha de un jugador con racha, mejor/peor día, cartera por pesos y sugerencia
  informativa basada en consenso;
- ficha de un ticker con reparto en la liga, poseedores por peso, mini-gráfica,
  consenso de Yahoo, empresas relacionadas y enlaces de noticias;
- operaciones recientes sin cantidades ni importes e insignias de la liga.

Las fichas se presentan como diálogo en escritorio y hoja inferior deslizable
en móvil. Los logos se solicitan a logo.dev en el navegador y tienen respaldo
visual si el servicio no responde. Las recomendaciones de analistas son datos
informativos de terceros, no asesoramiento de inversión.

## 5. Política de privacidad por jugador

Al dar de alta o editar `player.json`, el ajuste decisivo es:

```json
{ "show_amounts": false }
```

Con `false` se muestran únicamente retornos porcentuales; no se exponen
valor de inicio/fin, flujos ni P&L. Con `true`, esos campos aparecen tanto en
el JSON público como en las vistas generadas. Los tickers, pesos de cartera,
operaciones recientes y contribuciones porcentuales se publican como parte de
la experiencia web; por ello `show_amounts: false` protege importes, no vuelve
anónima una estrategia.

## 6. Insignias e hitos

En cada ejecución se buscan cinco familias de logros: campeón mensual, cinco
jornadas consecutivas en verde, hitos de +5/+10/+25 %, dos/tres meses
positivos consecutivos y récord de mayor subida diaria de un valor. Las
insignias ganadas se añaden a `data/badges.json` y no se revocan; el récord sí
puede sustituirse y mantiene hasta diez entradas de historial.

Al corregir datos históricos, revisa cuidadosamente ese fichero: regenerar
los cálculos no elimina premios anteriores por diseño. Si la regla de negocio
exige rectificación, debe ser una decisión explícita y auditada.

## 7. Diagnóstico rápido

| Síntoma | Comprobación | Acción habitual |
|---|---|---|
| Jugador ausente | logs de `ranking`, issue de extractos pendientes | confirmar `TRADER_KEY` y volver a cifrar/subir el CSV |
| Error de precio | `data/prices/<ticker>.csv`, símbolo del extracto | ejecutar sin `--offline`; confirmar que Yahoo conoce el ticker |
| CSV no incorporado por email | log de `inbox.yml` | revisar registro en `PLAYER_EMAILS`, remitente y DMARC/DKIM |
| Importes visibles indebidamente | `players/<id>/player.json` y `data/public/<id>.json` | fijar `show_amounts: false` y regenerar/publicar |
| La ficha de ticker es pobre | `trader/tickers.py` y caché de analistas | añadir metadatos del ticker; la ausencia de analistas es admisible |
| Cambio de jugador revertido | log/issue de `guard.yml` | registrar correctamente el id y el usuario en `PLAYER_OWNERS` |

Antes de modificar la lógica financiera, ejecuta la suite de `tests/`. Los
tests cubren parsing, cifrado, cartera, precios, informes, inbox, badges y el
payload/web; añade una prueba al mismo módulo para cada regla nueva o regresión.
