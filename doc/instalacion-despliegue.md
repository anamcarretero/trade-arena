# Instalación y despliegue de TradeArena

## Principio de portabilidad

El repositorio debe contener la documentación, configuración y scripts
necesarios para instalar, actualizar, verificar y recuperar TradeArena en cada
entorno soportado. Ningún despliegue puede depender de pasos manuales no
documentados en una consola de proveedor. Al incorporar un proveedor o una
plataforma se versionan en el mismo cambio su infraestructura como código,
variables, comandos, verificación, rollback y procedimiento de recuperación.

Actualmente se soportan dos formas reproducibles:

| Entorno | Artefactos canónicos | Estado |
|---|---|---|
| Local o servidor con Docker | `Dockerfile`, `compose.yaml`, `.env.example`, `scripts/install-compose.sh` y `scripts/verify-deployment.sh` | ejecutable |
| Plataforma de contenedores OCI con PostgreSQL administrado | misma imagen, comandos `serve`/`migrate` y esta guía | portable; la infraestructura específica llega en TA-037 |

La plataforma objetivo sigue siendo Cloud Run y Neon. Hasta que TA-037 añada
su infraestructura como código no se considera un despliegue de producción
reproducible, aunque la imagen sea compatible.

## Requisitos

- Git.
- Docker Engine con Docker Compose v2.
- `curl` para los smoke tests.
- Al menos 4 GB de RAM disponibles para Docker.

No es necesario instalar Python ni PostgreSQL en el host para ejecutar la
aplicación. PostgreSQL no se publica fuera de la red privada de Compose.

## Instalación con Docker Compose

Desde un clon limpio:

```bash
cp .env.example .env
openssl rand -hex 32
```

Copia el valor generado en `POSTGRES_PASSWORD` dentro de `.env`. Ese fichero
está ignorado por Git y nunca debe versionarse. La contraseña debe ser URL-safe
porque forma parte del DSN interno.

Instala o actualiza:

```bash
./scripts/install-compose.sh
```

El script valida la configuración y ejecuta esta secuencia:

1. construye una sola imagen OCI que comparten migración y API;
2. espera a PostgreSQL 16;
3. aplica las migraciones pendientes mediante un contenedor finito;
4. arranca la API solo si la migración terminó correctamente;
5. comprueba liveness, readiness y OpenAPI.

La API queda por defecto en `http://127.0.0.1:8080`; Swagger está en
`http://127.0.0.1:8080/docs`. Para revisar estado y logs:

```bash
docker compose ps
docker compose logs --follow api
docker compose logs postgres migrate
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

En staging o producción, `DATABASE_URL` procede del gestor de secretos del
proveedor. No se copia a una imagen, repositorio, log ni variable pública de
frontend.

## Servidor o plataforma OCI

El mismo digest de imagen se usa para dos procesos separados:

```bash
python -m tradearena migrate
python -m tradearena serve
```

La secuencia de despliegue es siempre:

1. copia de seguridad y comprobación de restauración según el entorno;
2. ejecución finita de `migrate` con `DATABASE_URL` privada;
3. despliegue de `serve` con la misma versión de imagen;
4. verificación con `scripts/verify-deployment.sh https://api.example`;
5. promoción de los consumidores después de readiness correcto.

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
