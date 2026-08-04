# ARCA Skills

Colección de Agent Skills para interactuar con los servicios web de **ARCA** (antes AFIP) mediante un navegador controlado por un agente.

El proyecto automatiza los mismos portales y formularios que utiliza una persona. No integra Web Services fiscales, no requiere instalar certificados, no administra claves privadas y no necesita SDKs SOAP ni homologación de WSAA/WSFE.

Las skills usan [agent-browser](https://agent-browser.dev/) para iniciar sesión, inspeccionar la pantalla actual, completar formularios, consultar información y descargar documentos oficiales. Cada operación sensible mantiene una revisión humana antes de confirmar cambios irreversibles.

## Skills disponibles

| Skill | Estado | Alcance |
| --- | --- | --- |
| `arca-comprobantes` | Inicial | Facturas C, Facturas de Exportación E, pre-comprobantes, Notas de Crédito, consultas y descarga de PDFs. |

El repositorio está preparado para incorporar otras áreas de ARCA como skills independientes. Separarlas mantiene disparadores claros y permite aplicar controles acordes al riesgo de cada servicio.

## Requisitos

- uv y npm.
- [agent-browser](https://github.com/vercel-labs/agent-browser):

  ```bash
  npm i -g agent-browser
  agent-browser install
  agent-browser skills get core
  ```

En Linux, usar `agent-browser install --with-deps` si faltan dependencias del navegador. `agent-browser skills get core` carga las instrucciones correspondientes a la versión instalada.

## Instalación

Instalar una skill concreta con `npx skills`:

```bash
npx skills add mgaitan/arca-skills -g -a codex -s arca-comprobantes -y
```

Instalar todas las skills disponibles:

```bash
npx skills add mgaitan/arca-skills -g -a codex -s '*' -y
```

Con GitHub CLI 2.92 o posterior (`gh skill` está en preview):

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

El symlink refleja las modificaciones locales sin reinstalar. Una sesión del agente ya iniciada puede requerir reinicio para refrescar metadata o disparadores. `npx skills add` desde una ruta local copia los archivos, por lo que no sirve como instalación autoactualizable.

## Credenciales y perfiles

La opción recomendada es el auth vault cifrado de `agent-browser`. Cada CUIT puede tener un alias distinto:

```bash
uv run skills/arca-comprobantes/scripts/arca_auth.py add \
  --profile arca-natalia \
  --cuit 27123456789 \
  --default

uv run skills/arca-comprobantes/scripts/arca_auth.py add \
  --profile arca-martin \
  --cuit 20123456789
```

El alta debe ejecutarla la persona en su terminal. Si la clave no está en el `.env` para ese mismo CUIT, se pide una sola vez con `getpass` y se guarda cifrada; nunca se solicita por chat. Listar perfiles, cambiar el default o iniciar una sesión:

```bash
uv run skills/arca-comprobantes/scripts/arca_auth.py list
uv run skills/arca-comprobantes/scripts/arca_auth.py default arca-martin
uv run skills/arca-comprobantes/scripts/arca_auth.py login --profile natalia
```

La selección usa perfil pedido, `ARCA_AUTH_PROFILE`, coincidencia con `ARCA_CUIT`, default configurado o perfil único. Si hay varios sin default, el agente debe preguntar cuál usar.

El `.env` se mantiene como selector y fallback:

```dotenv
ARCA_AUTH_PROFILE=arca-martin
ARCA_CUIT=20123456789
ARCA_PASSWORD=tu_clave_fiscal
```

`ARCA_AUTH_PROFILE` es opcional. Si no existe un perfil vault utilizable, `ARCA_CUIT` y `ARCA_PASSWORD` permiten iniciar sesión mediante un perfil cifrado temporal que se elimina inmediatamente. Las skills no imprimen claves, no persisten cookies ni versionan `.env`.

## Ejemplos: comprobantes

```text
Logueate con Natalia

Logueate con el CUIT 20-12345678-9

Usá arca-martin como perfil predeterminado

Hacé la factura a Lambda Sistemas por 2500 dólares en pesos

Factura C a CUIT 20222939098, 120 lucas

Facturar desde NATALIA LOBO a Lionel Andrés Messi. Servicios de traducción. 12 USD MEP en pesos

Con el perfil Natalia, facturá a Lambda 120 lucas

Hacer Factura E a Ruth Puentes por 514 dólares

Facturar esta transferencia recibida <captura con info>

Hacer la Nota de Crédito de la última factura a Lambda

¿Cuánto le facturé a Lambda Sistemas en el último año?
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

Estas skills automatizan navegación y controles operativos; no reemplazan asesoramiento contable, fiscal, laboral o legal. ARCA y los documentos oficiales descargados son la fuente final de cada operación.

Antes de publicar cambios, verificar que Git no contenga credenciales, cookies, capturas, PDFs, datos de contribuyentes ni exports de los portales.
