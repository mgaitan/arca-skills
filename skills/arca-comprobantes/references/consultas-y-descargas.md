# Consultas y descargas

## Buscar comprobantes

Entrar por `Consultas` o directamente, dentro de la sesion autenticada, a `https://fe.afip.gob.ar/rcel/jsp/filtrarComprobantesGenerados.do`.

La pantalla permite filtrar por:

- fecha de emision desde/hasta (`#fed`, `#feh`);
- tipo de comprobante;
- punto de venta (`select[name="puntoDeVenta"]`);
- numero de comprobante;
- tipo y numero de documento del receptor;
- CAE.

Para `ultimo año`, usar los 12 meses corridos hasta hoy, con extremos inclusivos, y decir las fechas usadas. Si el CUIT del cliente es conocido, filtrar por tipo de documento y numero. Si solo se conoce el nombre, resolverlo primero o buscar ventanas recientes y extraer el CUIT de una coincidencia inequívoca.

Recorrer paginacion completa. Si RCEL limita el intervalo o los resultados, dividir por meses y deduplicar por tipo + punto de venta + numero.

## Calcular importes

- Mantener monedas separadas; no sumar ARS y USD sin una conversion solicitada.
- Para `cuanto facture`, sumar facturas emitidas y mostrar notas de credito por separado.
- Para importe neto de anulaciones, restar solo notas de credito vinculadas al periodo/conjunto y explicar el criterio.
- Informar cantidad de comprobantes, intervalo y representado usados.
- No afirmar que una factura fue cobrada sin evidencia de pago independiente.

## Descargar PDF

1. Resolver el directorio Documentos del sistema.
2. Crear `<Documentos>/facturas/<cliente-slug>_<cliente-cuit>/`. Construir el slug desde la razon social: minusculas, transliteracion ASCII, espacios y signos convertidos a `_`, guiones bajos repetidos colapsados y bordes recortados. Usar el CUIT con 11 digitos sin guiones. Ejemplo: `Lambda Sistemas S.R.L.` y `30712345678` -> `lambda_sistemas_srl_30712345678`. Para Factura E sin CUIT argentino, usar el identificador tributario extranjero normalizado; si tampoco existe, terminar en `sin_cuit` y advertirlo.
3. Desde el resultado o detalle oficial, identificar el control que descarga/imprime el PDF. Usar `agent-browser download <selector> <ruta-destino>` para capturar la descarga.
4. Preservar el nombre oficial cuando sea seguro. Si no lo es, usar `Factura_<tipo>_<punto>_<numero>.pdf`. No sobrescribir: agregar un sufijo incremental.
5. Verificar que el archivo exista, no este vacio y sea PDF. Comprobar dentro del documento, cuando las herramientas locales lo permitan: tipo, emisor, receptor, CUIT/identificador, punto de venta, numero, fecha, moneda, total y CAE/autorizacion.
6. Si la descarga falla, volver al detalle autenticado y reintentar una vez. No crear un PDF mediante `agent-browser pdf`: eso imprime la pagina y no reemplaza el comprobante oficial.

Nunca guardar PDFs, capturas, exports, cookies o datos de clientes en el directorio de la skill.

## Respuesta

Tras una emision exitosa, devolver la ruta absoluta del PDF oficial. Si se emitio pero no se pudo descargar o validar el PDF, decirlo claramente y no presentar una ruta inexistente.

Un pre-comprobante pendiente no tiene PDF fiscal: devolver su numero de transaccion y estado, no fabricar una ruta.
