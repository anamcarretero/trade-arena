# Instalación y despliegue de TradeArena

## Principio de portabilidad

El repositorio debe contener la documentación, configuración y scripts
necesarios para instalar, actualizar, verificar y recuperar TradeArena en cada
entorno soportado. Ningún despliegue puede depender de pasos manuales no
documentados en una consola de proveedor. Al incorporar un proveedor o una
plataforma se versionan en el mismo cambio su infraestructura como código,
variables, comandos, verificación, rollback y procedimiento de recuperación.

Actualmente existen estas formas reproducibles:

| Entorno | Artefactos canónicos | Estado |
|---|---|---|
| Local o servidor con Docker | `Dockerfile`, `Dockerfile.web`, `compose.yaml`, `.env.example`, `scripts/install-compose.sh` y `scripts/verify-deployment.sh` | API, PostgreSQL y PWA/BFF ejecutables |
| Staging gestionado | `infra/staging/`, `.github/workflows/staging.yml` y `scripts/staging/` | automatización versionada; no desplegado ni comprobado sin credenciales |
| Plataforma OCI genérica con PostgreSQL administrado | misma imagen, comandos `serve`/`migrate` y esta guía | portable, no un entorno declarado operativo |

TA-039 define Cloud Run, Neon y Vercel para staging. Producción permanece
cerrada: no hay módulo, workflow, target ni promoción de producción.

## Requisitos

- Git.
- Docker Engine con Docker Compose v2.
- `curl` para los smoke tests.
- Al menos 4 GB de RAM disponibles para Docker.
- Una aplicación **Regular Web Application** en el tenant Auth0 europeo con
  `http://localhost:3000/auth/callback` como callback permitido y
  `http://localhost:3000/` como logout URL permitido.

No es necesario instalar Python ni PostgreSQL en el host para ejecutar la
aplicación. PostgreSQL no se publica fuera de la red privada de Compose.

## Instalación con Docker Compose

Desde un clon limpio:

```bash
cp .env.example .env
openssl rand -hex 32
```

Copia el valor generado en `POSTGRES_PASSWORD` dentro de `.env`. Genera además
dos valores independientes:

```bash
openssl rand -hex 32
openssl rand -base64 32 | tr '+/' '-_' | tr -d '='
```

El primero se usa en `BFF_SHARED_SECRET`; el segundo, que debe representar
exactamente 32 bytes en base64url, en `SESSION_ENCRYPTION_KEY`. Completa el
dominio, client ID y client secret de Auth0. El fichero `.env`
está ignorado por Git y nunca debe versionarse. La contraseña debe ser URL-safe
porque forma parte del DSN interno.

Instala o actualiza:

```bash
./scripts/install-compose.sh
```

El script valida la configuración y ejecuta esta secuencia:

1. construye la imagen OCI que comparten migración/API y la imagen separada web;
2. espera a PostgreSQL 16;
3. aplica las migraciones pendientes mediante un contenedor finito;
4. arranca la API solo si la migración terminó correctamente y después el BFF;
5. comprueba liveness, readiness, OpenAPI, web ES/EN y manifest PWA.

La PWA queda en `http://localhost:3000`; la API queda en
`http://127.0.0.1:8080` y Swagger en `http://127.0.0.1:8080/docs`. El navegador
solo necesita la PWA: el puerto de API se publica en localhost para diagnóstico,
pero ningún token se entrega al cliente. Para revisar estado y logs:

```bash
docker compose ps
docker compose logs --follow api
docker compose logs --follow web
docker compose logs postgres migrate api web
```

Para detener sin borrar datos:

```bash
docker compose down
```

El volumen `tradearena_postgres-data` conserva PostgreSQL. El comando
`docker compose down --volumes` lo borra de forma irreversible y solo debe
usarse en un entorno desechable y con confirmación explícita.

## Configuración

| Variable | Obligatoria | Uso |
|---|---|---|
| `POSTGRES_PASSWORD` | sí | secreto local de PostgreSQL; URL-safe y nunca versionado |
| `POSTGRES_USER` | no | usuario, por defecto `tradearena` |
| `POSTGRES_DB` | no | base, por defecto `tradearena` |
| `TRADEARENA_IMAGE` | no | nombre/etiqueta OCI, por defecto `tradearena:local` |
| `TRADEARENA_BIND_ADDRESS` | no | interfaz de la API; por defecto solo localhost |
| `TRADEARENA_PORT` | no | puerto publicado; por defecto `8080` |
| `DATABASE_URL` | sí fuera de Compose | DSN PostgreSQL que consumen API y migraciones |
| `PORT` | no | puerto interno de la API; Cloud Run lo inyecta |
| `AUTH0_DOMAIN` | sí | dominio del tenant europeo, sin protocolo; API construye issuer/JWKS y BFF endpoints OIDC |
| `AUTH0_CLIENT_ID` | sí | audiencia OIDC compartida por API y BFF; no es un secreto |
| `AUTH0_CLIENT_SECRET` | sí, solo BFF | secreto para canjear el código; nunca usa prefijo `NEXT_PUBLIC_` |
| `APP_BASE_URL` | sí | origen canónico de redirects y cookies del BFF, `http://localhost:3000` en local; evita publicar el `HOSTNAME` interno y activa cookies `Secure`/`__Host-` cuando usa HTTPS |
| `API_BASE_URL` | sí en web fuera de Compose | URL servidor-a-servidor de FastAPI; Compose fija `http://api:8080` |
| `BFF_SHARED_SECRET` | sí | secreto independiente para `POST /api/v1/auth/session`; presente solo en API y BFF |
| `SESSION_ENCRYPTION_KEY` | sí, solo BFF | 32 bytes base64url para A256GCM de cookies de sesión/transacción |
| `TRADEARENA_WEB_IMAGE` | no | imagen PWA/BFF, por defecto `tradearena-web:local` |
| `TRADEARENA_WEB_BIND_ADDRESS` | no | interfaz web, por defecto localhost |
| `TRADEARENA_WEB_PORT` | no | puerto web, por defecto `3000` |

En staging o producción, `DATABASE_URL`, `AUTH0_CLIENT_SECRET`,
`BFF_SHARED_SECRET` y `SESSION_ENCRYPTION_KEY` proceden del gestor de secretos.
No se copian a imagen, repositorio, log ni variable pública de frontend. API y
BFF reciben el mismo `BFF_SHARED_SECRET`; solo el BFF recibe el client secret y
la clave de cookie. La rotación de la clave de cookie cierra todas las sesiones
web activas, aunque las sesiones opacas sigan revocables en servidor.

## Verificación del flujo Auth0 local

La configuración indicada por el tenant de desarrollo ya admite las URLs
locales. Tras `./scripts/install-compose.sh`:

1. abre `http://localhost:3000/es` o `/en` y elige acceso;
2. confirma que Universal Login vuelve a `/auth/callback` y que una cuenta
   nueva termina en el formulario de perfil;
3. guarda una fecha adulta, consentimiento e idioma y comprueba el panel;
4. revisa DevTools: la cookie de sesión es `HttpOnly` y ningún ID/access token,
   sesión opaca, `AUTH0_CLIENT_SECRET` o `BFF_SHARED_SECRET` aparece en JS,
   Local Storage, Session Storage o respuestas al navegador;
5. cierra sesión y comprueba que volver directamente a `/es/app` inicia un
   acceso nuevo.

Los tests automatizados sustituyen Auth0 por aserciones criptográficas locales;
no usan red ni credenciales reales. Verifican firma/audiencia/emisor/nonce,
canal BFF, sesión revocada y el `404` de autorización entre ligas. El smoke test
de Compose no inicia Universal Login para evitar depender del tenant en CI.

## Servidor o plataforma OCI

El mismo digest de backend se usa para dos procesos separados:

```bash
python -m tradearena migrate
python -m tradearena serve
```

La secuencia de despliegue es siempre:

1. copia de seguridad y comprobación de restauración según el entorno;
2. ejecución finita de `migrate` con `DATABASE_URL` privada;
3. despliegue de `serve` con la misma versión de imagen;
4. despliegue de `Dockerfile.web` con secretos solo de servidor;
5. verificación con
   `scripts/verify-deployment.sh https://api.example https://app.example`;
6. promoción después de readiness correcto.

En un servidor expuesto a Internet, la API se coloca detrás de un proxy o
balanceador TLS. PostgreSQL nunca se publica directamente. El proceso se
ejecuta sin privilegios y solo recibe acceso de red y secretos imprescindibles.

## Copia y restauración en Compose

Crea primero un directorio ignorado por Git:

```bash
mkdir -p backups
docker compose exec -T postgres sh -c \
  'pg_dump --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --format=custom' \
  > "backups/tradearena-$(date +%Y%m%d-%H%M%S).dump"
```

Las restauraciones sobrescriben estado y deben ensayarse en una base aislada
antes de producción. Ejemplo sobre una base vacía deliberadamente creada:

```bash
docker compose exec -T postgres sh -c \
  'createdb --username "$POSTGRES_USER" tradearena_restore_test'
docker compose exec -T postgres sh -c \
  'pg_restore --username "$POSTGRES_USER" --dbname tradearena_restore_test --clean --if-exists' \
  < backups/archivo.dump
```

La copia no se considera válida hasta verificar que la base restaurada acepta
migraciones y que la API supera readiness. En servicios administrados se usa el
mecanismo nativo de backup/PITR y se documentan aquí sus comandos o IaC.

## Actualización, rollback y diagnóstico

- Las migraciones son compatibles hacia delante. Un rollback de aplicación
  reutiliza el digest anterior solo si sigue siendo compatible con el esquema.
- Los cambios destructivos usan expand/contract en versiones separadas; no se
  revierte una migración destructiva improvisando SQL.
- `GET /health/live` confirma proceso; `GET /health/ready` confirma PostgreSQL.
- `docker compose logs api migrate postgres` es la primera fuente de diagnóstico.
- Antes de promover una versión se ejecutan suite, migraciones sobre esquema
  vacío/anterior, smoke tests y restauración cuando corresponda.

## Staging gestionado de TA-039

### Contrato y requisitos

`infra/staging/` usa Terraform >=1.11 y fija proveedores Google, Neon y Vercel.
Define Artifact Registry; Cloud Run Service en `europe-west3` con mínimo cero;
un Cloud Run Job de migración que reutiliza `Dockerfile`; IAM/OIDC limitado al
repositorio y `main`; nombres de Secret Manager; Neon
`aws-eu-central-1`; proyecto y custom environment Vercel; y la API/identidad de
Scheduler sin targets. No contiene jobs financieros, Massive ni producción.

Se necesitan, proporcionados por el operador y nunca versionados:

- un proyecto GCP dedicado, ADC para bootstrap y bucket GCS privado/versionado
  para el estado;
- `NEON_API_KEY` y `VERCEL_API_TOKEN` con alcance del proyecto/equipo;
- `infra/staging/terraform.tfvars` y `backend.hcl`, ambos ignorados;
- los cuatro valores runtime: `DATABASE_URL`, `BFF_SHARED_SECRET`,
  `AUTH0_CLIENT_SECRET` y `SESSION_ENCRYPTION_KEY`;
- un origen HTTPS estable de staging ya autorizado en Auth0;
- un environment GitHub `staging` con variables `GCP_PROJECT_ID`,
  `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_DEPLOYER_SERVICE_ACCOUNT`,
  `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` y secreto `VERCEL_TOKEN`;
- para integración Neon de PR, variable `NEON_PROJECT_ID` y secreto
  `NEON_API_KEY` del repositorio.

Los runbooks de copia y restauración requieren clientes PostgreSQL 16
compatibles (`pg_dump`, `pg_restore`, `psql`); CI ensaya la secuencia contra dos
bases aisladas de su PostgreSQL 16 de servicio.

No se debe ejecutar `terraform apply` hasta autorizar expresamente recursos y
posible coste. Un plan local no es un despliegue.

### Bootstrap e instalación

```bash
cp infra/staging/terraform.tfvars.example infra/staging/terraform.tfvars
cp infra/staging/backend.hcl.example infra/staging/backend.hcl
terraform -chdir=infra/staging init -backend-config=backend.hcl
./scripts/staging/bootstrap.sh plan
CONFIRM_STAGING_APPLY=TA-039-STAGING ./scripts/staging/bootstrap.sh apply
```

El primer comando operativo siempre es `plan`. Tras el apply, añade versiones
de secretos sin imprimir valores, por ejemplo:

```bash
GCP_PROJECT_ID=... NEW_DATABASE_URL='...' \
  ./scripts/staging/rotate-secret.sh \
  tradearena-staging-database-url NEW_DATABASE_URL
```

El primer apply mantiene `deploy_runtime=false`: crea cimientos y contenedores
de secretos, pero no intenta arrancar Cloud Run sin imagen/valores. Publica la
imagen canónica, copia su digest a `api_image`, cambia
`deploy_runtime=true` y repite plan/apply:

```bash
GCP_PROJECT_ID=... ./scripts/staging/publish-image.sh
./scripts/staging/bootstrap.sh plan
CONFIRM_STAGING_APPLY=TA-039-STAGING ./scripts/staging/bootstrap.sh apply
```

Para `BFF_SHARED_SECRET`, `AUTH0_CLIENT_SECRET` y
`SESSION_ENCRYPTION_KEY`, usa el tercer argumento para sincronizar el contrato
correspondiente del custom environment Vercel. La rotación de la clave de cookie
cierra sesiones web. Verifica la versión nueva antes de deshabilitar la anterior.

### Actualización y despliegue

Cada merge a `main` ejecuta `.github/workflows/staging.yml` con esta secuencia:

1. OIDC GitHub→GCP sin clave persistente;
2. build de `Dockerfile` y push a Artifact Registry por digest;
3. actualización/ejecución de `tradearena-migrate-staging` y espera de éxito;
4. actualización del servicio API al mismo digest y readiness;
5. despliegue de `web/` mediante Vercel CLI al target `staging`;
6. smoke de API y PWA con `scripts/verify-deployment.sh`.

La misma secuencia se puede ejecutar deliberadamente con
`scripts/staging/update.sh`; no usa `--prod`. La preview de cada PR es solo la
PWA de Vercel. No hay API Cloud Run ni entorno full-stack permanente por PR.
Un cambio backend/migración puede usar una rama Neon efímera en
`.github/workflows/neon-pr.yml`; se elimina en `always()` y tiene caducidad.

### Verificación y smoke tests

```bash
./scripts/staging/verify.sh https://API-STAGING https://PWA-STAGING
```

Se comprueban liveness, readiness, OpenAPI, salud web, portadas ES/EN y
manifest. Solo un run remoto exitoso permite afirmar «staging desplegado».
Terraform `fmt`/`validate`, CI local o dry-run deben describirse como validación
local o plan, nunca como prueba de staging.

### Backup y restauración ensayable

```bash
DATABASE_URL='...' ./scripts/staging/backup.sh
RESTORE_DATABASE_URL='...' \
  ./scripts/staging/restore-drill.sh backups/archivo.dump --confirm-isolated
```

El dump es sensible, usa permisos privados y `backups/` está ignorado. La URL
de restauración debe corresponder a una base aislada y desechable; el script se
niega si coincide con `DATABASE_URL`. La restauración válida vuelve a aplicar
migraciones y consulta `schema_migrations`. Neon PITR/retención complementa,
pero no sustituye, este ensayo portable.

### Rollback compatible

```bash
GCP_PROJECT_ID=... \
PREVIOUS_BACKEND_IMAGE='...@sha256:...' \
PREVIOUS_VERCEL_DEPLOYMENT='https://...' \
VERCEL_TOKEN='...' ./scripts/staging/rollback.sh
```

El rollback mueve la API al digest anterior y vuelve a desplegar el deployment
PWA anterior dentro del target `staging`; nunca invoca promoción o rollback de
producción. No ejecuta SQL descendente: el binario previo debe tolerar el esquema expandido. Una migración
destructiva requiere expand/contract en cambios separados: expandir, desplegar
lectores/escritores compatibles, retirar uso, y contraer en una entrega futura.

La secuencia futura de producción, todavía sin automatización ni autorización,
será siempre: migraciones compatibles→API→PWA. Nunca PWA antes de API ni una
contracción junto al despliegue que deja de usar los campos.

### Diagnóstico, rotación y retirada

```bash
GCP_PROJECT_ID=... ./scripts/staging/diagnose.sh
./scripts/staging/retire.sh plan
CONFIRM_STAGING_RETIRE=RETIRE-TA-STAGING ./scripts/staging/retire.sh apply
```

`diagnose.sh` muestra estado, últimas migraciones ejecutadas y logs recientes;
no recupera valores de Secret Manager. Antes de retirar: congela despliegues,
crea/verifica backup, ensaya restauración, cambia
`cloud_run_deletion_protection=false` mediante un apply revisado, genera el plan
de destrucción y obtiene aprobación. Después revoca tokens Neon/Vercel, elimina
versiones de secretos según retención y conserva evidencia/backup cifrado. El
script solo planifica salvo confirmación literal.

### Estado real de TA-039

En esta entrega se han validado código, formato, sintaxis, tests y dry-runs que
no necesitan credenciales. No se han creado recursos, cargado secretos,
desplegado staging, ejecutado smoke remoto ni ensayado restauración Neon. Esos
bloqueos deben aparecer en la PR y en el primer run autorizado.

## Obligación para entornos futuros

Cada nuevo entorno o servidor debe añadir al repositorio, antes de considerarse
soportado:

1. infraestructura y configuración versionadas;
2. inventario de variables y secretos, sin valores reales;
3. comandos idempotentes de instalación y migración;
4. health checks y smoke tests automatizados;
5. estrategia de persistencia, backup, restauración y rollback;
6. permisos mínimos, red privada y terminación TLS;
7. procedimiento de actualización y retirada del entorno.

Si alguno de estos elementos solo existe en una consola externa, el entorno no
está terminado.
