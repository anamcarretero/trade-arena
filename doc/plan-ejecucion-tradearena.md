# Plan de ejecución: TradeArena

## 1. Objetivo y límites del producto

Transformar el ranking actual en una aplicación de competiciones privadas de
inversión simulada. Cada participante opera exclusivamente con saldo virtual:
no hay integración con brókeres, dinero real, retiradas, botes ni premios de
valor económico. La suscripción compra capacidad de organización del software,
nunca una participación ni un resultado económico.

La primera versión se centrará en acciones y ETF cotizados en Estados Unidos,
valorados en USD. El producto se diseñará para incorporar otros mercados,
monedas e idiomas, pero no los incluirá en el motor inicial.

## 2. Decisiones de producto cerradas

### Competiciones y acceso

- Ligas privadas, accesibles por invitación; no habrá ligas públicas en el MVP.
- El creador elige libremente fecha y hora de inicio y final. Al comenzar se
  bloquean calendario y reglas de la competición.
- Se permiten incorporaciones tardías: la persona empieza con el capital
  inicial al entrar, su retorno se calcula desde esa fecha y aparece de
  inmediato en la clasificación con un indicador visible de incorporación.
- El administrador puede expulsar miembros y revocar invitaciones. Si expulsa
  a alguien durante una competición, se conserva su historial pero deja de
  figurar en el ranking activo.
- El ranking se ordena por rentabilidad porcentual, no por importe ganado.
- La edad mínima es de 18 años.
- El lanzamiento comercial empieza en la Unión Europea, con foco en España.
  La arquitectura queda preparada para otras jurisdicciones; inicialmente la
  interfaz estará en español e inglés.

### Operativa simulada

- Solo acciones y ETF estadounidenses en USD en la primera versión.
- Precios retrasados 15 minutos y el mismo retraso para todos los participantes.
- Se admiten órdenes a mercado y límite; quedan fuera stop-loss, stop-limit,
  ventas en corto, margen y apalancamiento.
- Una orden permite elegir sesión regular o incluir premercado y postmercado.
- Las órdenes fuera de su ventana permitida quedan pendientes.
- Las ejecuciones son completas o permanecen pendientes; no habrá ejecuciones
  parciales ni simulación de libro de órdenes o liquidez.
- Solo se negocian unidades completas.
- Dividendos y *splits* se aplican automáticamente.
- Comisión por ejecución: 0,99 USD en sesión regular y 2,99 USD en horario
  ampliado. Las órdenes no ejecutadas no cobran comisión.

### Planes y monetización

| Plan | Precio | Límites confirmados |
|---|---:|---|
| Free | 0 EUR | Una liga activa, hasta 2 jugadores, 1.000 EUR virtuales por persona y duración máxima de 6 semanas. |
| Friends | 4,99 EUR/mes | Lo paga el creador; hasta 5 jugadores, competiciones de hasta un año y capital virtual configurable por el creador. |
| Club | 9,99 EUR/mes | Lo paga el creador; hasta 20 jugadores y hasta 5 ligas activas. |

Al terminar un plan de pago, se conserva el acceso de lectura y las
competiciones en curso pueden finalizar. Se bloquean nuevas ligas, miembros o
competiciones que excedan el plan aplicable. No se borra historial ni se
expulsa automáticamente a participantes.

### Proveedores y avisos

- Usar datos gratuitos solo durante desarrollo y beta cerrada. Antes de abrir
  el producto al público, contratar un proveedor con licencia comercial y
  cotizaciones retrasadas 15 minutos.
- Autenticación inicial mediante enlace seguro por email y Google; preparar la
  incorporación de Apple para las aplicaciones móviles.
- Los avisos iniciales serán solo dentro de la aplicación: invitaciones,
  cambios de miembros, inicio y fin de competición, estados de órdenes,
  ejecuciones límite y cambios relevantes de suscripción. No se enviará email
  en esta primera versión.

## 3. Principios de arquitectura obligatorios

Se construirá un monolito modular, suficiente para las primeras centenas o
miles de personas usuarias. Cada responsabilidad se aislará tras contratos
internos estables: el dominio no debe depender de proveedores concretos.

- Autenticación, datos de mercado, facturación, almacenamiento, correo,
  notificaciones y cola se implementarán mediante adaptadores.
- Sustituir un proveedor supone cambiar su adaptador y sus pruebas de contrato,
  no reescribir ligas, órdenes, carteras ni rankings.
- Separar por responsabilidad: dominio, aplicación/casos de uso, puertos,
  adaptadores de infraestructura y presentación.
- API REST versionada y documentada con OpenAPI.
- PostgreSQL como fuente de verdad; los workers ejecutan precios, órdenes,
  valoraciones y rankings fuera de las peticiones web.
- Comenzar con una web responsive/PWA y compartir contrato API, tipos y diseño
  con las futuras aplicaciones Android e iOS.

Arquitectura de referencia:

```text
PWA web ──────┐
              ├─ API versionada ─ PostgreSQL
Apps móviles ─┘        │
                         ├─ identidad (adaptador)
                         ├─ facturación (adaptador)
                         ├─ datos de mercado (adaptador)
                         ├─ cola y workers
                         └─ notificaciones (adaptador)
```

## 4. Modelo de datos mínimo

- Usuarios, perfiles, consentimiento, sesiones y auditoría de accesos.
- Ligas, miembros, roles e invitaciones con caducidad y revocación.
- Competiciones y una instantánea inmutable de sus reglas.
- Carteras virtuales, cuentas de efectivo, órdenes, ejecuciones y libro mayor
  inmutable.
- Instrumentos, precios históricos, calendarios de mercado y eventos
  corporativos.
- Snapshots de valoración y ranking reproducibles.
- Suscripciones, derechos de plan y eventos de facturación.
- Notificaciones internas y su estado de lectura.

Los límites de planes, altas, invitaciones y creación de competiciones se
validarán transaccionalmente en el servidor para evitar carreras de concurrencia.

## 5. Fases de ejecución

### Fase 0 — Especificación y cumplimiento

1. Convertir las decisiones anteriores en reglas versionadas del producto.
2. Definir formalmente precios, redondeos, zonas horarias, calendario de
   mercado, expiración de órdenes, dividendos, *splits*, suspensiones y
   tratamiento de datos ausentes.
3. Seleccionar proveedores con contratos compatibles con los adaptadores:
   identidad, precios, pagos, hosting y cola.
4. Preparar términos, privacidad, política de edad y revisión legal para el
   lanzamiento UE/España.

**Salida:** especificación de reglas, contratos de proveedor y backlog
priorizado.

### Fase 1 — Núcleo financiero reproducible

1. Extraer la lógica financiera actual de CSV, artefactos estáticos y GitHub
   Pages hacia el dominio independiente.
2. Implementar cartera virtual, libro mayor, órdenes, ejecuciones y comisiones.
3. Añadir un adaptador de precios de prueba y *fixtures* deterministas.
4. Cubrir con pruebas rendimiento, comisiones, redondeos, sesiones, órdenes
   límite, dividendos y *splits*.
5. Definir snapshots de cartera y ranking reproducibles.

**Criterio de aceptación:** con la misma secuencia de órdenes, eventos y
precios, el resultado es idéntico en cada ejecución.

### Fase 2 — Backend, cuentas y autorización

1. Crear el esquema PostgreSQL y las migraciones.
2. Implementar acceso por enlace seguro de email y Google detrás de un puerto
   de identidad.
3. Añadir perfiles, borrado de cuenta y exportación de datos.
4. Implementar ligas privadas, miembros, roles e invitaciones.
5. Aplicar autorización estricta por pertenencia y límites Free en servidor.

**Criterio de aceptación:** nadie puede leer, modificar o unirse a recursos de
otra liga sin autorización, incluso invocando la API directamente.

### Fase 3 — PWA MVP

1. Registro, incorporación y selección de idioma.
2. Crear liga, invitar, aceptar y gestionar miembros.
3. Crear competición y confirmar una instantánea de reglas.
4. Consultar cartera, enviar órdenes e inspeccionar historial.
5. Mostrar ranking, evolución, fecha de incorporación y reglas visibles.
6. Añadir centro de avisos interno, privacidad y eliminación de cuenta.

**Criterio de aceptación:** dos personas pueden crear una liga, competir hasta
el final y consultar un ranking consistente desde la PWA.

### Fase 4 — Mercado y trabajos en segundo plano

1. Integrar el proveedor autorizado mediante su adaptador.
2. Ingerir precios, controlar calidad y almacenar trazabilidad.
3. Ejecutar workers idempotentes con cola, reintentos y alertas.
4. Programar ejecución de órdenes, valoración y snapshots de ranking.
5. Gestionar fallos temporales de mercado sin duplicar ejecuciones ni corromper
   el ranking.

**Criterio de aceptación:** una interrupción temporal del proveedor no pierde
órdenes ni genera una operación doble.

### Fase 5 — Monetización

1. Implementar derechos de producto y límites por plan.
2. Añadir checkout web, portal de facturación y webhooks firmados e
   idempotentes.
3. Implementar upgrade, cancelación y degradación sin pérdida de datos.
4. Antes de vender capacidades de pago en apps móviles, integrar las compras
   nativas requeridas por cada tienda.

**Criterio de aceptación:** el plan efectivo deriva exclusivamente de eventos
de facturación validados por el servidor.

### Fase 6 — Aplicaciones móviles

1. Crear cliente Expo para iPhone y Android.
2. Compartir cliente API, modelos y sistema de diseño con la PWA.
3. Cubrir acceso, ligas, ranking, cartera y órdenes.
4. Mantener notificaciones push como ampliación posterior a los avisos internos.

### Fase 7 — Migración y retirada del flujo anterior

1. Mantener el ranking histórico separado durante la estabilización.
2. No migrar perfiles ni datos financieros sin consentimiento explícito.
3. Retirar gradualmente CSV, correo operativo, GitHub Pages y los flujos del
   repositorio cuando el nuevo producto sea estable.

## 6. Orden inmediato de trabajo

1. Cerrar la especificación de Fase 0 y registrar las reglas como pruebas.
2. Extraer y probar el núcleo financiero.
3. Crear base de datos, autenticación y autorización.
4. Implementar ligas, invitaciones y límites Free.
5. Construir la PWA MVP.
6. Activar workers de precios, ejecución y rankings.
7. Añadir facturación.
8. Construir los clientes móviles.
9. Ejecutar pruebas de seguridad, carga, accesibilidad y revisión legal antes
   de abrir pagos al público.

## 7. Riesgos que deben verificarse antes de lanzar

- Licencia del proveedor para mostrar y redistribuir cotizaciones a usuarios.
- Cumplimiento de privacidad, consumo, fiscalidad y pagos en cada región de
  lanzamiento.
- Reglas de compra dentro de las tiendas móviles para funciones de pago.
- Idempotencia, auditoría y recuperación ante fallos de los workers.
- Accesibilidad, seguridad de sesiones y aislamiento entre ligas.
