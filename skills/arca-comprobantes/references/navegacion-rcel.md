# Navegacion de RCEL

## Principios de browser

- Usar el ciclo `open` -> `snapshot -i` -> actuar -> esperar -> volver a capturar.
- Considerar obsoletos los `@refs` despues de cualquier cambio de pagina.
- RCEL contiene HTML antiguo que a veces no aparece en el arbol accesible. Si el snapshot esta vacio, usar `read`, selectores CSS estables o una inspeccion DOM acotada con `eval`; no hacer clic por coordenadas ni por posicion.
- No imprimir valores de inputs de CUIT o clave en snapshots, logs o respuestas.
- Mantener una sola sesion efimera para login, RCEL y descarga. Cerrar con `agent-browser --session "$SESSION" close`.

## Login

1. Abrir `https://auth.afip.gob.ar/contribuyente_/login.xhtml`.
2. Cargar `ARCA_CUIT` en el campo de CUIT y avanzar.
3. Volver a capturar la pagina; cargar `ARCA_PASSWORD` en `TU CLAVE` y pulsar `Ingresar`.
4. Esperar el portal `https://portalcf.cloud.afip.gob.ar/portal/app/`.
5. Abrir `Comprobantes en linea`. Normalmente crea una pestaña en `https://fe.afip.gob.ar/rcel/jsp/index_bis.jsp`; listar pestañas, cambiar a la nueva y volver a inspeccionar.
6. Ante captcha, segundo factor o desafio no automatizable, pedir intervencion humana sin solicitar el codigo por chat.

No pasar secretos como literales en comandos. Expandirlos desde el entorno dentro de la invocacion local y silenciar la salida del comando que completa el campo.

## Empresa representada

La pantalla `Seleccione la Empresa a representar` puede renderizar opciones como `input[type=button]` que no aparecen en el snapshot. Inspeccionar sus `value` y comparar nombres normalizados.

- Si el pedido dice `desde X`, seleccionar la coincidencia inequívoca con X.
- En otro caso, consultar `ARCA_CUIT` en ARCADB y hacer coincidir su `denominacion`; tambien puede usarse la identidad autenticada que muestra RCEL.
- Si las opciones no incluyen CUIT y dos nombres son plausibles, detenerse y preguntar.

Despues de seleccionar, comprobar el encabezado `Representando a` antes de seguir.

## Menu principal

Rutas y selectores verificados en RCEL 4.9.9:

- Generar: `#btn_gen_cmp` -> `buscarPtosVtas.do`.
- Pre-comprobantes: `#btn_pre_cmp` -> `pcBuscarPreComprobantes.do`.
- Consultas: `#btn_consultas` -> `filtrarComprobantesGenerados.do`.

Tratar estos selectores como ayudas, no como contrato eterno: confirmar tambien el texto visible y la URL.

## Factura C

1. En Generar, seleccionar un `#puntodeventa` y esperar a que se repueble `#universocomprobante`. Probar puntos hasta hallar `Factura C`; no asumir el primero.
2. Seleccionar `Factura C` y continuar.
3. En `DATOS DE EMISION (PASO 1 DE 4)`:
   - elegir Productos, Servicios o ambos en `#idconcepto`;
   - completar fecha y, para Servicios, periodo desde/hasta y vencimiento;
   - si el comprobante queda en USD, marcar `#monedaextranjera`, seleccionar `Dolar Estadounidense` y verificar `#tipocambio`;
   - seleccionar actividad asociada solo cuando RCEL la exija o corresponda al servicio.
4. En datos del receptor, elegir condicion IVA y tipo de documento; cargar CUIT/CUIL/DNI, razon social y condicion de venta. Verificar los datos autocompletados por ARCA.
5. En detalle, usar cantidad `1` por defecto, unidad apropiada, descripcion concreta y precio unitario final. Factura C no discrimina IVA.
6. Continuar a `genComResumenDatos.do` y comparar todo el resumen con la intencion preparada.

No accionar `#btngenerar` ni un boton `Confirmar Datos` sin la confirmacion final requerida por `SKILL.md`.

## Factura E

1. Recorrer puntos de venta hasta que `#universocomprobante` ofrezca `Factura de Exportacion E`.
2. Usar USD salvo instruccion expresa compatible. Completar pais, identificacion tributaria o documento extranjero, domicilio, idioma/condicion de venta y datos de exportacion exigidos por la pantalla.
3. No inventar identificadores extranjeros ni datos aduaneros. Pedir cualquier campo obligatorio que no pueda obtenerse del pedido, ARCADB o historial.
4. Llegar a revision, validar receptor, moneda USD, importe y punto de venta, y aplicar la misma confirmacion final.

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
