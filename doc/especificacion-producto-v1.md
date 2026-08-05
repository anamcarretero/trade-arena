# Especificación versionada de reglas — TradeArena v1

Estado: cerrada para las fases 0–2. Versión de reglas: `v1`. Jurisdicción de
lanzamiento prevista: UE, inicialmente España. Esta especificación describe
una simulación educativa sin dinero, premios, retiradas ni conexión a bróker.

## Convenciones financieras

- La moneda es USD. El efectivo se redondea a 2 decimales y los precios a 4,
  en ambos casos con `ROUND_HALF_EVEN`. No se admiten `float` en el dominio.
- Solo se aceptan acciones y ETF estadounidenses activos y unidades enteras.
- Una cartera nace con un único abono de capital virtual. Su retorno es
  `(valor actual / capital inicial) - 1`; el ranking ordena ese porcentaje y
  desempata por el identificador estable del usuario.
- Cada ejecución crea un asiento inmutable y balanceado. La comisión es 0,99
  USD en sesión regular o 2,99 USD en sesión ampliada.
- Una orden es de mercado o límite y opta expresamente por sesión regular o
  por regular más ampliada. Nunca hay ejecución parcial, corto, margen ni
  cantidad fraccionaria.
- Una orden de mercado pendiente cruza con la primera cotización elegible. Una
  límite de compra cruza cuando el precio es menor o igual al límite; una de
  venta, cuando es mayor o igual. Sin saldo o posición suficiente se rechaza
  sin comisión. Una cotización anterior a la orden nunca puede ejecutarla.
- Las órdenes v1 son `GTC` hasta ejecución, cancelación, final de competición o
  suspensión definitiva del instrumento. El cierre o una sesión no autorizada
  solo las deja pendientes.

## Tiempo, mercado y datos ausentes

- Toda fecha persistida es `timestamptz` y todo evento del dominio exige zona
  horaria. El calendario canónico es `America/New_York`; la interfaz traduce a
  la zona de la persona usuaria.
- Las ventanas regulares y ampliadas proceden del calendario versionado del
  proveedor; no se codifican horas fijas porque festivos y medias sesiones
  cambian. Una suspensión no ejecuta órdenes.
- Producción mostrará la misma fuente con al menos 15 minutos de retraso a
  todos. `observed_at`, proveedor y `delayed_until` se guardan para auditoría.
- Ante precio ausente no se inventa ni interpola: la orden sigue pendiente y
  no se emite snapshot nuevo. Workers posteriores reintentan idempotentemente.
- Un dividendo abona `importe por acción × unidades` a quienes posean las
  acciones según el evento normalizado del proveedor. Un *split* multiplica
  unidades por su razón sin alterar efectivo. Si produce fracción, el evento
  queda bloqueado para revisión: v1 no liquida fracciones.

## Competiciones, privacidad y planes

- Las ligas son privadas. Todas las consultas y mutaciones validan una
  membresía activa; una persona ajena recibe `404` para no revelar existencia.
- Propietario y administrador invitan, revocan y expulsan. La invitación está
  ligada al email, caduca y solo se consume una vez. Una expulsión conserva el
  historial financiero y excluye del ranking activo.
- Al empezar, calendario y reglas se copian a `rules_snapshot`. Una entrada
  tardía recibe el capital inicial completo y queda marcada en el ranking.
- Free permite una liga activa del creador y dos plazas, contando propietario,
  miembros e invitaciones pendientes. Cada competición Free usa un capital
  virtual inicial fijo de 3.000 USD. Las comprobaciones son transaccionales.
- Friends y Club mantienen los límites y política de degradación definidos en
  el plan de ejecución; se activarán en la Fase 5.
- La fecha de nacimiento se valida en servidor y solo mayores de 18 años pueden
  completar el perfil. El borrado anonimiza la
  cuenta, revoca sesiones y membresías activas y conserva auditoría financiera.
  La exportación de datos solo puede solicitarla la propia cuenta.

## Evidencia ejecutable

Las reglas financieras se fijan en `tests/tradearena/test_trading.py`; identidad
en `test_identity.py`; límites, invitaciones y aislamiento de API en
`test_authorization.py`. Los snapshots incluyen un SHA-256 de su representación
canónica, por lo que una repetición con las mismas entradas es comparable byte
a byte.
