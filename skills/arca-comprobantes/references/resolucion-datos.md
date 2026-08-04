# Resolucion de datos

## Receptor

Aplicar esta cascada dentro de la empresa representada elegida:

1. Si hay CUIT explicito, normalizar a 11 digitos y consultar `GET https://arcadb.fastapicloud.dev/v1/records/{cuit}`. Comparar CUIT y denominacion con el pedido.
2. Si solo hay nombre, consultar `GET https://arcadb.fastapicloud.dev/v1/records?query=<nombre>&limit=20`. Usar `denominacion`, `cuit`, `tipo_persona`, condicion tributaria y actividad para desambiguar.
3. Si ARCADB no responde, no encuentra la entidad o el usuario usa un alias, buscar facturas recientes del mismo representado. Comparar nombre normalizado, CUIT, recurrencia y recencia. `Lambda` puede resolverse como `Lambda Sistemas S.R.L.` si es la unica coincidencia reciente clara.
4. Si quedan dos candidatos razonables, mostrar nombre y CUIT enmascarado de cada uno y pedir eleccion. No elegir por orden de resultados.

ARCADB es una ayuda de lookup, no evidencia de una factura. La pantalla de ARCA y el PDF oficial son la fuente final de los datos facturados.

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

## Conversion USD a ARS

1. Abrir con `agent-browser` la pagina renderizada `https://www.cronista.com/MercadosOnline/monedas.html`.
2. Localizar la tabla que tiene columnas `Compra`, `Venta`, `Variacion`.
3. Para oficial usar la fila exacta `Dolar BNA`; para MEP usar `Dolar MEP`. No confundir con Blue, MEP Contado, CCL, Tarjeta o Mayorista.
4. Leer el primer valor de la fila, correspondiente a Compra, junto con la fecha visible de la pagina.
5. Convertir formato argentino (`1.523,88` -> `1523.88`) y calcular `importe_usd * compra` con precision decimal.
6. Redondear el total final a centavos y conservar tasa, tipo y fecha en el resumen de revision.

Ejemplos:

- `2500 dolares en pesos`: Factura C en ARS; USD 2.500 por Compra de Dolar BNA.
- `12 usd MEP en pesos`: Factura C en ARS; USD 12 por Compra de Dolar MEP.
- `expresada en dolares`: mantener el importe nominal en USD y usar moneda extranjera en ARCA; no aplicar esta conversion.

No reutilizar una cotizacion de una ejecucion anterior.

## Periodos y condicion de venta

- Para Servicios sin periodo explicito, usar el periodo actual solo si coincide razonablemente con el pedido y mostrarlo antes de confirmar; si la fecha del servicio importa, preguntar.
- Usar `Contado` por defecto salvo que el pedido o historial claro indiquen otra condicion.
- No inferir cobro, deuda o medio de pago a partir de la existencia de la factura.
