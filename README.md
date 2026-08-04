# ARCA Comprobantes

Agent Skill para operar **Comprobantes en linea** de ARCA (antes AFIP) mediante [agent-browser](https://agent-browser.dev/).

Permite preparar y emitir Facturas C y Facturas de Exportacion E, trabajar con pre-comprobantes, anular facturas mediante Notas de Credito, consultar comprobantes emitidos y descargar los PDFs oficiales fuera del repositorio.

> Esta skill interactua con servicios fiscales reales. Antes de generar una factura o Nota de Credito exige una revision y confirmacion humana final.

## Requisitos

- Node.js y npm.
- [agent-browser](https://github.com/vercel-labs/agent-browser):

  ```bash
  npm i -g agent-browser
  agent-browser install
  agent-browser skills get core
  ```

  En Linux, usar `agent-browser install --with-deps` si faltan dependencias del navegador. `agent-browser skills get core` carga las instrucciones que corresponden exactamente a la version instalada.

## Instalacion

Con `npx skills` para Codex, a nivel de usuario:

```bash
npx skills add mgaitan/arca-comprobantes -g -a codex -s arca-comprobantes -y
```

Con GitHub CLI 2.92 o posterior (`gh skill` esta en preview):

```bash
gh skill install mgaitan/arca-comprobantes arca-comprobantes --agent codex --scope user
```

Para otro agente, cambiar `codex` por un valor soportado como `claude-code`, `cursor` o `github-copilot`.

## Desarrollo local

Para que los cambios del checkout se reflejen sin reinstalar, enlazar el repositorio directamente:

```bash
git clone https://github.com/mgaitan/arca-comprobantes.git
cd arca-comprobantes
mkdir -p ~/.agents/skills
ln -s "$PWD/skills/arca-comprobantes" ~/.agents/skills/arca-comprobantes
```

Si el destino ya existe, quitar primero esa instalacion concreta. `npx skills add` desde una ruta local copia la skill, por lo que no funciona como instalacion autoactualizable.

## Credenciales

Definir las variables en el entorno del proceso o en un `.env` del directorio desde el que se ejecuta el agente:

```dotenv
ARCA_CUIT=20123456789
ARCA_PASSWORD=tu_clave_fiscal
```

La skill no imprime credenciales, no persiste cookies y cierra la sesion del navegador al terminar. No versionar el `.env`.

## Ejemplos

```text
Hacé la factura a Lambda Sistemas por 2500 dolares en pesos

Factura C a CUIT 20222939098, 120 lucas

Facturar desde NATALIA LOBO a Lionel Andres Messi. Servicios de traduccion. 12 USD MEP en pesos

Hacer Factura E a Ruth Puentes por 514 dolares

Facturar esta transferencia recibida <captura con info>

Hacer la Nota de Credito de la ultima factura a Lambda

¿Cuanto le facture a Lambda Sistemas en el ultimo año?
```

Las facturas descargadas se guardan en una ruta como:

```text
~/Documentos/facturas/lambda_sistemas_srl_30712345678/Factura_C_00002_00000123.pdf
```

## Alcance

La skill automatiza navegacion y controles operativos; no reemplaza asesoramiento contable, fiscal o legal. Los datos de ARCADB se usan para resolver identidades, mientras que ARCA y sus PDFs oficiales son la fuente final de cada comprobante.

`agents/openai.yaml` contiene metadata opcional para la interfaz de Codex: nombre visible, descripcion corta y prompt sugerido. No contiene logica de facturacion y otros agentes pueden ignorarlo.
