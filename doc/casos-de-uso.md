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

## 0. Flujos del producto nuevo hasta Fase 2

1. Identidad verifica un enlace de email de un solo uso o claims Google con
   emisor, audiencia y email verificado; después se emite una sesión propia.
2. La persona mayor de edad completa nombre, idioma y consentimiento. Puede
   exportar sus propios datos o borrar la cuenta; el borrado revoca sesiones y
   anonimiza sin destruir la auditoría financiera.
3. Free permite crear una liga activa con capital virtual inicial fijo de
   3.000 USD por competición. El creador es propietario y puede invitar un
   segundo miembro. La invitación ocupa plaza, está ligada al email, caduca y
   puede revocarse.
4. Solo propietario/administrador invita o expulsa. La persona expulsada deja
   de tener acceso; su historial se conserva para auditoría.
5. Cada acceso directo como `GET /api/v1/leagues/{id}` vuelve a comprobar la
   pertenencia. Una cuenta externa recibe `404`, también al intentar mutaciones,
   para evitar enumerar ligas privadas.

La PWA todavía no forma parte de estas fases. El contrato HTTP está en
`tradearena/presentation/openapi.yaml`; TA-030 lo sirve mediante FastAPI,
incluye sondas `/health/live` y `/health/ready`, y comprueba automáticamente
que rutas y `operationId` coincidan. Las pruebas de abuso directo siguen en
`tests/tradearena/test_authorization.py`.

Para ejecutar el backend contra PostgreSQL se aplican primero las migraciones
con `DATABASE_URL=... python3 -m tradearena migrate` y se arranca después la API
con `python3 -m tradearena serve`. Liveness solo
comprueba el proceso; readiness ejecuta una consulta contra PostgreSQL y
responde `503` si no está disponible. Las pruebas de integración usan
exclusivamente `TEST_DATABASE_URL`, crean un esquema aislado y comprobable, y
lo eliminan al terminar.

### Flujo de desarrollo y preview de Fase 3

1. Cada pull request instala Python 3.12 y las versiones exactas de
   `requirements.txt`, levanta PostgreSQL 16 aislado, aplica las migraciones,
   ejecuta toda la suite Python, construye y verifica la instalación Compose
   desde cero, y genera el ranking histórico offline con datos ficticios en
   salidas temporales. No requiere extractos reales ni secretos.
2. La consolidación inicial se fusiona desde `codex/baseline-tradearena`; el
   trabajo TA-030 comienza después desde el `main` actualizado en otra rama.
3. Un PR de interfaz obtiene una preview Vercel que consume fixtures o el API
   integrado de staging mediante el BFF; nunca abre una conexión del navegador
   a PostgreSQL.
4. Si el PR cambia backend, persistencia o migraciones, CI crea una rama Neon
   efímera, aplica todas las migraciones, ejecuta las pruebas de integración y
   elimina la rama al cerrar el PR.
5. No se crea una API Cloud Run por PR. Tras fusionar en `main`, se despliega
   staging, se ejecutan smoke tests y solo entonces el cambio puede promoverse.
6. Producción sigue bloqueada hasta superar revisión legal, licencia de mercado,
   DPA, restauración y seguridad. El ranking histórico continúa en GitHub Pages
   durante toda esta transición.

### Instalar o actualizar TradeArena

1. El operador parte de un clon y copia `.env.example` a `.env`, sin versionar
   secretos.
2. `scripts/install-compose.sh` valida Docker y Compose, construye la imagen y
   espera a PostgreSQL 16.
3. El servicio finito `migrate` aplica las migraciones pendientes. Si falla, la
   API nueva no arranca.
4. La API se ejecuta sin privilegios, PostgreSQL permanece en una red privada y
   el volumen conserva los datos entre reinicios.
5. `scripts/verify-deployment.sh` exige respuestas correctas de liveness,
   readiness y OpenAPI antes de considerar terminada la instalación.
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
3. `inbox.yml` se activa por el timbre de Gmail (`repository_dispatch`) o por
   el cron de respaldo y ejecuta `python -m trader inbox`.
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

El ranking se actualiza automáticamente en horario de mercado estadounidense,
después del cierre, al cambiar `players/**` o `trader/**`, y bajo demanda desde
Actions. El administrador puede reproducirlo localmente:

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
