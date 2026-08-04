# ARCA Skills

Coleccion de Agent Skills para interactuar con los servicios web de **ARCA** (antes AFIP) mediante un navegador controlado por un agente.

El proyecto automatiza los mismos portales y formularios que utiliza una persona. No integra Web Services fiscales, no requiere instalar certificados, no administra claves privadas y no necesita SDKs SOAP ni homologacion de WSAA/WSFE.

Las skills usan [agent-browser](https://agent-browser.dev/) para iniciar sesion, inspeccionar la pantalla actual, completar formularios, consultar informacion y descargar documentos oficiales. Cada operacion sensible mantiene una revision humana antes de confirmar cambios irreversibles.

## Skills disponibles

| Skill | Estado | Alcance |
| --- | --- | --- |
| `arca-comprobantes` | Inicial | Facturas C, Facturas de Exportacion E, pre-comprobantes, Notas de Credito, consultas y descarga de PDFs. |

El repositorio esta preparado para incorporar otras areas de ARCA como skills independientes. Separarlas mantiene disparadores claros y permite aplicar controles acordes al riesgo de cada servicio.

## Requisitos

- Node.js y npm.
- [agent-browser](https://github.com/vercel-labs/agent-browser):

  ```bash
  npm i -g agent-browser
  agent-browser install
  agent-browser skills get core
  ```

En Linux, usar `agent-browser install --with-deps` si faltan dependencias del navegador. `agent-browser skills get core` carga las instrucciones correspondientes a la version instalada.

## Instalacion

Instalar una skill concreta con `npx skills`:

```bash
npx skills add mgaitan/arca-skills -g -a codex -s arca-comprobantes -y
```

Instalar todas las skills disponibles:

```bash
npx skills add mgaitan/arca-skills -g -a codex -s '*' -y
```

Con GitHub CLI 2.92 o posterior (`gh skill` esta en preview):

```bash
gh skill install mgaitan/arca-skills arca-comprobantes --agent codex --scope user
```

Para otro agente, cambiar `codex` por un valor soportado como `claude-code`, `cursor` o `github-copilot`.

## Desarrollo local

Clonar el conjunto y enlazar solamente las skills en desarrollo:

```bash
git clone https://github.com/mgaitan/arca-skills.git
cd arca-skills
mkdir -p ~/.agents/skills
ln -s "$PWD/skills/arca-comprobantes" ~/.agents/skills/arca-comprobantes
```

El symlink refleja las modificaciones locales sin reinstalar. Una sesion del agente ya iniciada puede requerir reinicio para refrescar metadata o disparadores. `npx skills add` desde una ruta local copia los archivos, por lo que no sirve como instalacion autoactualizable.

## Credenciales

Cada skill declara las variables que necesita. Para Comprobantes en linea, definirlas en el entorno del proceso o en un `.env` del directorio desde el que se ejecuta el agente:

```dotenv
ARCA_CUIT=20123456789
ARCA_PASSWORD=tu_clave_fiscal
```

Las skills no deben imprimir credenciales, persistir cookies ni versionar archivos `.env`. Los documentos descargados se guardan fuera del repositorio.

## Ejemplos: comprobantes

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

## Estructura

```text
skills/
  arca-comprobantes/
    SKILL.md
    agents/openai.yaml
    references/
    scripts/
```

`SKILL.md` contiene las instrucciones operativas. `references/` conserva detalles que se cargan solo cuando hacen falta. `scripts/` contiene fast paths deterministas en Python PEP 723 que se ejecutan con `uv run`. `agents/openai.yaml` aporta metadata opcional para la interfaz de Codex y puede ser ignorado por otros agentes.

## Seguridad y alcance

Estas skills automatizan navegacion y controles operativos; no reemplazan asesoramiento contable, fiscal, laboral o legal. ARCA y los documentos oficiales descargados son la fuente final de cada operacion.

Antes de publicar cambios, verificar que Git no contenga credenciales, cookies, capturas, PDFs, datos de contribuyentes ni exports de los portales.
