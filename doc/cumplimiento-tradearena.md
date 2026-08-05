# Paquete de cumplimiento para revisión — TradeArena v1

Documento de trabajo, no texto legal aprobado. Su objetivo es entregar a
asesoría un alcance concreto y evitar que la beta pública o los pagos se
activen sin revisión UE/España.

## Ficha del servicio para términos

- Servicio: organización de competiciones privadas de inversión simulada.
- No ejecuta inversiones, custodia dinero, conecta con brókeres, permite
  retiradas ni concede premios de valor económico.
- La suscripción paga capacidad del software. El ranking es informativo y no
  constituye asesoramiento ni recomendación financiera.
- Requisitos: persona física de al menos 18 años, cuenta individual, uso lícito
  y aceptación de reglas visibles de cada competición.
- Conductas prohibidas propuestas: suplantación, compartir sesión, acceso a
  ligas ajenas, automatización abusiva, manipulación del servicio y uso de
  datos de mercado fuera de la interfaz autorizada.
- Suspensión: por seguridad, fraude o incumplimiento, con canal de reclamación.
  La terminación de un plan conserva lectura e historial y deja acabar las
  competiciones en curso según la política comercial cerrada.
- Responsabilidad a revisar: disponibilidad, errores/retrasos de mercado,
  pérdida limitada a importes pagados dentro de lo admisible por consumo y
  exclusiones que no afecten derechos imperativos.

## Información para política de privacidad

| Finalidad | Datos | Base propuesta a validar | Conservación propuesta |
|---|---|---|---|
| Cuenta y acceso | email, proveedor/subject, sesión, auditoría e IP en infraestructura | contrato y seguridad/interés legítimo | sesión hasta caducidad; auditoría 12 meses |
| Elegibilidad | fecha de nacimiento y versión de términos aceptada | contrato/obligación aplicable | mientras exista la cuenta; después solo prueba mínima de aceptación |
| Liga y competición | perfil, membresías, invitaciones, órdenes y resultados simulados | ejecución del servicio | vida de cuenta/competición; exportable y sujeto a política de borrado |
| Facturación futura | cliente, plan, estado, ids de evento; no tarjeta | contrato y obligaciones fiscales | plazos fiscales aplicables |
| Operación y seguridad | logs, eventos de acceso, incidencias | interés legítimo | ventana definida por riesgo y minimización |

Encargados previstos: Auth0, Render, Stripe y proveedor de mercado. Antes de
producción se documentarán entidad contratante, región, subencargados,
transferencias internacionales, DPA, medidas y procedimiento de derechos. No
se usarán datos financieros reales del ranking histórico para crear cuentas
sin consentimiento explícito.

Derechos que debe explicar la política: acceso/exportación, rectificación,
borrado, limitación, oposición, portabilidad cuando proceda y reclamación ante
la AEPD. La aplicación ya reserva exportación propia y borrado con revocación
de sesiones; deben probarse también copias de seguridad y sistemas de terceros.

## Política de edad

TradeArena v1 es exclusivamente para mayores de 18 años. El servidor valida la
fecha de nacimiento antes de completar el perfil; la interfaz no puede omitir
ni alterar esa comprobación. No se diseña para menores ni se permite
consentimiento parental como alternativa. Soporte debe disponer de un flujo
para bloquear y borrar una cuenta cuando exista evidencia razonable de minoría
de edad, conservando únicamente lo exigido por seguridad o ley.

## Decisiones que debe firmar asesoría

1. Calificación regulatoria exacta de la simulación y de sus mensajes en cada
   mercado de lanzamiento, incluida publicidad comparativa y gamificación.
2. Términos de consumo, renovación/cancelación, desistimiento, IVA y precios.
3. Bases jurídicas, conservación, transferencias y necesidad/alcance de DPIA.
4. Redacción de avisos de mercado y límites de responsabilidad compatibles con
   el contrato del proveedor y normativa imperativa.
5. Política de edad, mecanismo proporcional de verificación y respuesta a
   cuentas de menores.
6. Requisitos de cookies/analítica y consentimiento; por defecto no se añadirá
   analítica publicitaria.
7. Compras dentro de Apple/Google antes de ofrecer planes en aplicaciones.

## Criterio de salida legal

Pagos y apertura pública permanecen bloqueados hasta que versiones ES/EN de
términos y privacidad tengan propietario, versión, fecha de vigencia y firma de
asesoría; los DPA estén archivados; la licencia de mercado esté firmada; y el
registro de actividades, DPIA si procede y proceso de derechos se hayan
ensayado. La aprobación se registrará como decisión versionada, no solo como
mensaje o reunión.
