---
name: arca-comprobantes
description: "Interactuar con ARCA/AFIP Comprobantes en linea mediante agent-browser para preparar o emitir Facturas C y Facturas de Exportacion E, crear o retomar pre-comprobantes, anular facturas mediante Notas de Credito, descargar PDFs y responder consultas sobre comprobantes emitidos. Usar ante pedidos como 'hace una factura', 'factura C/E', 'anula la ultima factura', 'hace la nota de credito', 'factura esta transferencia', 'cuanto le facture a...', busquedas por cliente/CUIT y descargas de facturas argentinas."
---

# ARCA Comprobantes

Operar el sitio real de ARCA como un flujo fiscal sensible. Usar `agent-browser` para toda interaccion con el navegador y verificar la pantalla actual en cada paso; las etiquetas y el HTML de RCEL pueden cambiar.

## Preparar el entorno

1. Comprobar `command -v agent-browser`. Si falta, detener la operacion y recomendar:

   ```bash
   npm i -g agent-browser && agent-browser install
   ```

   En Linux, si faltan bibliotecas del navegador, recomendar `agent-browser install --with-deps`.
2. Antes de usarlo, cargar su guia compatible con la version instalada mediante `agent-browser skills get core`.
3. Obtener `ARCA_CUIT` y `ARCA_PASSWORD` primero de las variables del proceso y, si falta alguna, de un `.env` del directorio de trabajo o sus padres. No imprimir, registrar, interpolar en archivos ni devolver estos valores. Si siguen faltando, indicar solamente los nombres requeridos y detenerse.
4. Usar una sesion efimera dedicada, sin `--restore`, `--state` ni perfiles persistentes. Cerrar la sesion al terminar, incluso ante error.
5. Resolver Documentos con `xdg-user-dir DOCUMENTS` cuando exista; usar `$HOME/Documentos` como primera alternativa y `$HOME/Documents` como segunda. No descargar facturas dentro de la skill o del repositorio.

Leer [navegacion-rcel.md](references/navegacion-rcel.md) antes de iniciar sesion o tocar RCEL. Leer [resolucion-datos.md](references/resolucion-datos.md) para resolver representado, cliente, concepto, importe o moneda. Leer [consultas-y-descargas.md](references/consultas-y-descargas.md) para consultas, historial y PDFs.

## Interpretar el pedido

Construir internamente una intencion verificable con:

- operacion: borrador, emision C, emision E, anulacion con Nota de Credito o consulta;
- empresa representada;
- receptor e identificador;
- concepto y periodo;
- importe, moneda de origen y moneda del comprobante;
- punto de venta compatible;
- destino de descarga.

Aceptar lenguaje argentino: `una luca` = ARS 1.000, `120 lucas` = ARS 120.000, `un palo` = ARS 1.000.000 y `dos palos y medio` = ARS 2.500.000. Interpretar `$` como pesos salvo que el usuario diga USD o dolares. No completar una ambiguedad material con una suposicion silenciosa.

Si el pedido incluye una captura de transferencia, inspeccionarla y extraer nombre, CUIT/CUIL, importe, fecha y referencia visibles. Tratar la captura como entrada, no subirla a ARCA ni conservarla en artefactos. Resolver al receptor con esas pistas y pedir aclaracion solo si hay mas de una coincidencia plausible o falta un dato fiscal requerido.

## Resolver datos

Aplicar la cascada de [resolucion-datos.md](references/resolucion-datos.md). Reglas esenciales:

- Respetar una empresa explicita, por ejemplo `desde NATALIA LOBO`.
- Sin empresa explicita, elegir la representacion cuyo CUIT/denominacion corresponda a `ARCA_CUIT`; no elegir simplemente la primera opcion.
- Elegir el punto de venta que ofrezca el tipo solicitado. No fijar numeros: pueden variar por representado.
- Para nombres abreviados como `Lambda`, preferir una coincidencia reciente y clara del historial del mismo representado; si sigue habiendo duda, preguntar.
- Usar el rubro del emisor y descripciones recientes para proponer un concepto concreto y veraz cuando el usuario no lo indique.

## Moneda

- Emitir Factura C en pesos por defecto.
- Si el usuario da USD `en pesos`, convertir a ARS con la columna **Compra** de la fila `Dolar BNA` de El Cronista. Si dice MEP, usar **Compra** de `Dolar MEP`. Obtener la cotizacion renderizada en el momento y calcular `USD * compra`, redondeado a dos decimales.
- Si pide que el comprobante quede expresado en dolares, no convertir el importe: activar moneda extranjera y elegir Dolar Estadounidense. Verificar el tipo de cambio que muestre ARCA sin reemplazarlo por una cotizacion inventada.
- Emitir Factura E en dolares por defecto y usar un punto de venta que ofrezca Factura de Exportacion E.
- Si El Cronista no carga o no permite identificar sin duda fila, columna y fecha, informar el bloqueo; no sustituir otra fuente de forma silenciosa.

## Preparar y emitir

1. Navegar hasta la revision final siguiendo [navegacion-rcel.md](references/navegacion-rcel.md).
2. Validar en pantalla empresa, tipo, punto de venta, receptor, fechas, concepto, detalle, moneda, cotizacion e importe total.
3. Para un borrador, guardar como pre-comprobante cuando RCEL ofrezca esa accion. Informar el numero de transaccion y que no existe PDF fiscal todavia.
4. Para una emision, mostrar un resumen breve y pedir confirmacion explicita inmediatamente antes de `Confirmar Datos`, `Generar` o cualquier accion que produzca CAE/comprobante. Una confirmacion anterior o ambigua no elimina este control.
5. Tras confirmar, descargar el PDF oficial y validarlo segun [consultas-y-descargas.md](references/consultas-y-descargas.md).

No afirmar exito al llegar a la pantalla de revision. El exito requiere comprobante generado, datos finales coherentes y PDF oficial descargado.

## Anular con Nota de Credito

ARCA no borra una factura emitida. Interpretar `anular`, `cancelar factura` o `hacer la nota de credito` como emitir una Nota de Credito compatible y asociada al comprobante original.

1. Buscar la factura original en el representado correcto. Para `la ultima factura a Lambda`, resolver primero Lambda y ordenar las facturas por fecha, punto de venta y numero.
2. Verificar que exista una unica ultima factura compatible y que no tenga ya una Nota de Credito total asociada. Si hay empate, anulaciones previas o mas de una candidata plausible, pedir eleccion.
3. Elegir el mismo punto de venta y el tipo compatible: Nota de Credito C para Factura C o Nota de Credito por Operaciones con el Exterior E para Factura E.
4. Asociar explicitamente tipo, punto de venta y numero de la factura original. Para anulacion total, conservar receptor, moneda, importe y tipo de cambio del comprobante asociado.
5. Llegar a revision y pedir una confirmacion final especifica para la Nota de Credito. No presentar la anulacion como realizada hasta obtener CAE y descargar el PDF oficial.

Soportar inicialmente anulaciones totales. Ante ajustes parciales, descuentos o devoluciones parciales, detenerse y pedir importe/motivo exactos; no convertirlos automaticamente en anulacion total.

## Consultar

Entrar en `Consultas` del representado correcto y aplicar los filtros disponibles. Para preguntas por nombre, resolver primero el CUIT o inferirlo del historial reciente. Recorrer todas las paginas o dividir intervalos amplios; no calcular sobre una pagina parcial.

Ante `cuanto le facture`, sumar facturas del periodo y presentar por separado notas de credito/anulaciones; calcular neto solo si el usuario lo pide o dejar ambos valores claramente rotulados. Indicar fechas inclusivas, moneda y cantidad de comprobantes usados.

## Responder

Para una factura emitida, responder con la ruta local absoluta del PDF descargado, por ejemplo:

```text
/home/usuario/Documentos/facturas/lambda_sistemas_srl_30712345678/Factura_C_00002_00000123.pdf
```

Agregar una advertencia solo si hubo una diferencia no bloqueante. Para un borrador, responder con el numero de transaccion y aclarar que no hay PDF hasta emitirlo. Para una consulta, responder el resultado y el criterio de calculo, sin exponer credenciales ni datos ajenos al pedido.
