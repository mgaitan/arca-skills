# Resolucion de datos

## Receptor

Aplicar esta cascada dentro de la empresa representada elegida:

1. Si hay CUIT explicito, normalizar a 11 digitos y consultar `GET https://arcadb.fastapicloud.dev/v1/records/{cuit}`. Comparar CUIT y denominacion con el pedido.
2. Si solo hay nombre, consultar `GET https://arcadb.fastapicloud.dev/v1/records?query=<nombre>&limit=20`. Usar `denominacion`, `cuit`, `tipo_persona`, condicion tributaria y actividad para desambiguar.
3. Si ARCADB no responde, no encuentra la entidad o el usuario usa un alias, buscar facturas recientes del mismo representado. Comparar nombre normalizado, CUIT, recurrencia y recencia. `Lambda` puede resolverse como `Lambda Sistemas S.R.L.` si es la unica coincidencia reciente clara.
4. Si quedan dos candidatos razonables, mostrar nombre y CUIT enmascarado de cada uno y pedir eleccion. No elegir por orden de resultados.

ARCADB es una ayuda de lookup, no evidencia de una factura. La pantalla de ARCA y el PDF oficial son la fuente final de los datos facturados.

Cuando una factura reciente se use como plantilla, inspeccionar el detalle oficial o su PDF y copiar solo los datos que siguen siendo semanticamente validos. El punto de venta, la fecha, la cotizacion, el importe y la condicion de pago deben volver a resolverse para la nueva operacion.

En Factura E distinguir `CUIT País`, `ID Impositivo` y documento extranjero. Una captura de transferencia puede mostrar varios numeros que no tienen etiqueta fiscal; asignarlos a un campo de ARCA solo si el historial oficial o una fuente del pedido lo confirma. Si no se puede distinguir, pedir el dato en vez de intercambiar identificadores por semejanza.

## Empresa emisora y concepto

Para inferir el rubro del emisor, consultar el CUIT autenticado exacto en ARCADB y priorizar `clae_actividad`, `actividad` y `complemento_actividad`. Contrastar con la actividad visible en RCEL y descripciones recientes del mismo emisor.

Orden para decidir la descripcion:

1. Usar el concepto que dio el usuario, corrigiendo solo errores ortograficos evidentes sin cambiar el sentido.
2. Reutilizar una descripcion reciente del mismo cliente si describe realmente el nuevo trabajo.
3. Proponer una descripcion concreta compatible con el rubro del emisor. Para servicios informaticos pueden servir `Consultoria sobre sistema informatico`, `Pruebas funcionales de sistema de cadena de bloques` o `Implementacion de agente de IA`.
4. Si el rubro no permite una inferencia honesta, preguntar que se facturo.

No agregar detalles politicos, tecnicos o comerciales que el usuario no haya indicado y que cambien la naturaleza del servicio.

## Importes

Normalizar expresiones antes de navegar:

| Expresion | Valor |
| --- | ---: |
| una luca | ARS 1.000 |
| 120 lucas | ARS 120.000 |
| un palo | ARS 1.000.000 |
| dos palos y medio | ARS 2.500.000 |

Usar aritmetica decimal y redondeo a dos decimales. Mostrar en el resumen previo tanto el importe original como la conversion.

Una multiplicacion de moneda por cotizacion calcula el total del comprobante; no convierte el primer factor en cantidad de articulos. Por ejemplo, `650 USD MEP x 1.549,81` significa ARS 1.007.376,50 como total y, salvo indicacion distinta, una linea con cantidad `1`. En cambio, `650 unidades a $1.549,81` expresa cantidad `650` y precio unitario ARS 1.549,81.

## Conversion USD a ARS

1. Si el usuario proporciona una cotizacion, usarla para el calculo y mostrarla como proporcionada por el usuario. No reemplazarla por otra tasa ni inventar una fecha de mercado.
2. Si falta la cotizacion, abrir con `agent-browser` la pagina renderizada `https://www.cronista.com/MercadosOnline/monedas.html`.
3. Localizar la tabla que tiene columnas `Compra`, `Venta`, `Variacion`.
4. Para oficial usar la fila exacta `Dolar BNA`; para MEP usar `Dolar MEP`. No confundir con Blue, MEP Contado, CCL, Tarjeta o Mayorista.
5. Leer el primer valor de la fila, correspondiente a Compra, junto con la fecha visible de la pagina.
6. Convertir formato argentino (`1.523,88` -> `1523.88`) y calcular `importe_usd * compra` con precision decimal.
7. Redondear el total final a centavos y conservar tasa, tipo y fecha en el resumen de revision. Para una tasa dada por el usuario, identificarla como tal y no atribuirle una fecha consultada.

Ejemplos:

- `2500 dolares en pesos`: Factura C en ARS; USD 2.500 por Compra de Dolar BNA.
- `12 usd MEP en pesos`: Factura C en ARS; USD 12 por Compra de Dolar MEP.
- `650 dolares MEP en pesos a 1.549,81`: total ARS 1.007.376,50; cantidad `1` y precio unitario ARS 1.007.376,50.
- `expresada en dolares`: mantener el importe nominal en USD y usar moneda extranjera en ARCA; no aplicar esta conversion.

No reutilizar una cotizacion de una ejecucion anterior.

## Periodos y condicion de venta

- Para Servicios sin periodo explicito, usar el periodo actual solo si coincide razonablemente con el pedido y mostrarlo antes de confirmar; si la fecha del servicio importa, preguntar.
- Usar `Contado` por defecto salvo que el pedido o historial claro indiquen otra condicion.
- No inferir cobro, deuda o medio de pago a partir de la existencia de la factura.
