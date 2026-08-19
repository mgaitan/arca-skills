# Navegacion de RCEL

## Principios de browser

- Usar el ciclo `open` -> `snapshot -i` -> actuar -> esperar -> volver a capturar.
- Considerar obsoletos los `@refs` despues de cualquier cambio de pagina.
- RCEL contiene HTML antiguo que a veces no aparece en el arbol accesible. Si el snapshot esta vacio, usar `read`, selectores CSS estables o una inspeccion DOM acotada con `eval`; no hacer clic por coordenadas ni por posicion.
- No imprimir valores de inputs de CUIT o clave en snapshots, logs o respuestas.
- Mantener una sola sesion efimera para login, RCEL y descarga. Cerrar con `agent-browser --session "$SESSION" close`.
- Despues de cada `select`, `click` o submit que repueble la pagina, tomar un snapshot nuevo. Un `@ref` puede quedar obsoleto aunque la URL no cambie.
- En formularios con datepicker, mascara o AJAX, verificar el valor real con `get value` o un selector CSS despues de `fill`. Un comando que devuelve `Done` no garantiza que el valor haya quedado en el input.

## Login

1. Resolver la identidad segun [autenticacion.md](autenticacion.md).
2. Iniciar una sesion efimera con `uv run scripts/arca_auth.py login --profile <alias> --session <sesion>`; omitir `--profile` cuando corresponda usar el default.
3. Validar el portal `https://portalcf.cloud.afip.gob.ar/portal/app/`; no confiar solamente en el `loggedIn` interno de `auth login`.
4. Abrir `Comprobantes en linea`. Normalmente crea una pestaña en `https://fe.afip.gob.ar/rcel/jsp/index_bis.jsp`; listar pestañas, cambiar a la nueva y volver a inspeccionar.
5. Ante captcha, segundo factor o desafio no automatizable, pedir intervencion humana sin solicitar el codigo por chat.

No pasar secretos como literales en comandos. El auth vault o el perfil temporal creado desde `.env` deben completar la clave sin exponerla al agente.

## Empresa representada

La pantalla `Seleccione la Empresa a representar` puede renderizar opciones como `input[type=button]` que no aparecen en el snapshot. Inspeccionar sus `value` y comparar nombres normalizados.

- Si el pedido dice `desde X`, seleccionar la coincidencia inequívoca con X.
- En otro caso, consultar el CUIT autenticado en ARCADB y hacer coincidir su `denominacion`; tambien puede usarse la identidad autenticada que muestra RCEL.
- Si las opciones no incluyen CUIT y dos nombres son plausibles, detenerse y preguntar.

Despues de seleccionar, comprobar el encabezado `Representando a` antes de seguir.

## Menu principal

Rutas y selectores verificados en RCEL 4.9.9:

- Generar: `#btn_gen_cmp` -> `buscarPtosVtas.do`.
- Pre-comprobantes: `#btn_pre_cmp` -> `pcBuscarPreComprobantes.do`.
- Consultas: `#btn_consultas` -> `filtrarComprobantesGenerados.do`.

Tratar estos selectores como ayudas, no como contrato eterno: confirmar tambien el texto visible y la URL.

## Factura C

Para el caso estandar, usar primero el fast path documentado en `SKILL.md`. Las instrucciones siguientes son el fallback interactivo.

1. En Generar, enumerar los puntos disponibles en `#puntodeventa`, seleccionar uno y esperar a que se repueble `#universocomprobante`. Inspeccionar el texto de sus opciones y probar los puntos hasta hallar `Factura C`; no asumir el primero ni fijar un numero de punto.
2. Seleccionar `Factura C` y continuar.
3. En `DATOS DE EMISION (PASO 1 DE 4)`:
   - elegir Productos, Servicios o ambos en `#idconcepto`;
   - completar fecha y, para Servicios, periodo desde/hasta y vencimiento;
   - si el comprobante queda en USD, marcar `#monedaextranjera`, seleccionar `Dolar Estadounidense` y verificar `#tipocambio`;
   - seleccionar actividad asociada solo cuando RCEL la exija o corresponda al servicio.
4. En datos del receptor, elegir condicion IVA y tipo de documento; cargar CUIT/CUIL/DNI, razon social y condicion de venta. Verificar los datos autocompletados por ARCA.
5. En detalle, usar cantidad `1` por defecto, unidad apropiada, descripcion concreta y precio unitario final. Factura C no discrimina IVA.
6. Continuar a `genComResumenDatos.do` y comparar todo el resumen con la intencion preparada.

Detalles verificados que evitan exploracion innecesaria:

- Paso 1: `#idconcepto`, `#fc`, `#fsd`, `#fsh`, `#vencimientopago`.
- Paso 2: `#idivareceptor`, `#idtipodocreceptor`, `#nrodocreceptor`, `#domicilioreceptorcombo` y checkboxes `formaDePago`.
- Paso 3: `#detalle_descripcion1`, `#detalle_cantidad1`, `#detalle_medida1`, `#detalle_precio1`, `#imptotal`.
- Paso 4: URL `genComResumenDatos.do` y boton final `#btngenerar`.
- La opcion `unidades` comparte valor HTML con `seleccionar...`; elegirla por texto/indice visible, no solamente por `value=7`.
- `Imprimir...` inicia una descarga. Capturarla con `agent-browser download`; navegar a su URL puede devolver `ERR_ABORTED` aun cuando el PDF sea valido.

No accionar `#btngenerar`, `Confirmar Datos` ni el `Confirmar` de un modal sin la confirmacion final requerida por `SKILL.md`.

## Factura E

1. Recorrer los puntos disponibles y seleccionar el primero que, tras repoblar `#universocomprobante`, ofrezca por texto `Factura de Exportacion E`. Registrar el punto elegido en la intencion; nunca copiar un numero de otra factura o de un ejemplo.
2. En el paso 1, elegir `Servicios` cuando la operacion sea un servicio, marcar moneda extranjera y elegir `Dolar Estadounidense` si corresponde. Verificar `#tipocambio` renderizado por ARCA. La casilla visible `#cancelacionMonedaExtranjera` puede aparecer como `El pago se realiza en la misma moneda`; no escribir sobre su input hidden equivalente.
3. Distinguir fecha de emision de fecha de pago. Completar `#fc` y `#vencimientopago` por separado y verificar ambos valores. Si RCEL rechaza una fecha de pago anterior a la actual, no cambiarla silenciosamente: informar la restriccion, preparar un nuevo resumen con la fecha valida y pedir confirmacion de la modificacion.
4. En el paso 2, seleccionar primero el pais en `#destino` y esperar la validacion AJAX. Luego completar y verificar `#nrodocreceptor` (CUIT pais), `#nrodocextranjeroreceptor` (ID impositivo o documento extranjero), `#razonsocialreceptor`, `#domicilioreceptor` y `#descripcionformadepago`. La seleccion del pais puede limpiar o completar campos; por eso el nombre y el resto de los datos se cargan despues.
5. En el paso 3, cargar una linea con `#detalle_descripcion1`, `#detalle_cantidad1`, `#detalle_medida1` y `#detalle_precio1`, y comprobar `#imptotal`. Para servicios, dejar la unidad sin seleccionar solo si el historial oficial o RCEL lo permite; no reemplazarla automaticamente por `unidades`.
6. No inventar identificadores extranjeros, incoterms ni datos aduaneros. Pedir cualquier campo obligatorio que no pueda obtenerse del pedido, la captura, ARCADB o el historial oficial.
7. Llegar a revision, validar receptor, fechas, moneda, cotizacion, importe, descripcion y punto de venta, y aplicar la confirmacion final en cada modal que pueda producir CAE.

## Nota de Credito para anular

1. Empezar desde `Consultas`, abrir el comprobante original y registrar tipo, punto de venta, numero, receptor, fecha, moneda, tipo de cambio, total y estado.
2. Revisar resultados posteriores para detectar una Nota de Credito ya asociada. No duplicar una anulacion total.
3. Volver a `Generar`, elegir el punto de venta original y el tipo compatible que ofrece RCEL:
   - Factura C -> Nota de Credito C.
   - Factura de Exportacion E -> Nota de Credito por Operaciones con el Exterior E.
4. Seleccionar el comprobante asociado o completar sus datos exactamente como aparecen en el original. Para Factura E, aplicar el tipo de cambio del comprobante asociado.
5. Para anulacion total, copiar receptor, moneda e importe total. Usar una descripcion clara como `Anulacion total de Factura C 00002-00000123` sin inventar un motivo adicional.
6. En la revision final, validar que el resumen diga Nota de Credito, muestre el comprobante asociado correcto y no cambie moneda o total.
7. Pedir confirmacion explicita antes de generar. Descargar luego el PDF de la Nota de Credito en la misma carpeta del cliente.

No usar la Nota de Credito como mecanismo de edicion. La factura original permanece emitida y la Nota de Credito documenta su ajuste o anulacion.

## Borradores

`Pre-Comprobantes` lista estados `Pendiente`, `Generado` y `Todos`, con numero de transaccion, receptor, importe, fecha y acciones. RCEL informa que elimina automaticamente los pre-comprobantes luego de 30 dias.

Cuando la pantalla de carga permita guardar sin emitir, usar esa accion para un borrador. Confirmar luego que aparece como `Pendiente`. No describir como borrador un formulario que solo quedo abierto en el navegador.
