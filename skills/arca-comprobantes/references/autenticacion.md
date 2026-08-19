# Autenticacion y perfiles

## Prioridad

Preferir perfiles cifrados del auth vault de `agent-browser`. Resolver la identidad en este orden:

1. Perfil o CUIT indicado por el usuario, por ejemplo `logueate con Natalia` o `usa el CUIT 20-12345678-9`.
2. `ARCA_AUTH_PROFILE` del entorno o `.env`.
3. Perfil cuyo username coincide con `ARCA_CUIT`.
4. Perfil predeterminado guardado por `auth default`.
5. El unico perfil ARCA existente.
6. El par `ARCA_CUIT`/`ARCA_PASSWORD` como fallback.

Si hay varios perfiles y no se puede elegir uno, mostrar nombre y CUIT de cada perfil y preguntar. El CUIT no es una clave; nunca pedir ni mostrar la password.

Si no existe ningun perfil y tampoco `ARCA_CUIT`, preguntar el CUIT y un alias opcional. Con esa respuesta, indicar al usuario el comando `auth add --profile <alias> --cuit <cuit>` para que ingrese la clave mediante `getpass` en su propia terminal.

## Administrar perfiles

Ejecutar los helpers con `uv run` desde `skills/arca-comprobantes`:

```bash
# cd /ruta/al/arca-skill/skills/arca-comprobantes
uv run scripts/arca_auth.py list
uv run scripts/arca_auth.py add --profile arca-natalia --default
uv run scripts/arca_auth.py add --profile arca-martin --cuit 20123456789
uv run scripts/arca_auth.py default arca-martin
uv run scripts/arca_auth.py login --profile natalia --session arca-operacion
uv run scripts/arca_auth.py login --cuit 20123456789 --session arca-operacion
```

Si Chrome no puede iniciar por el sandbox de Linux, diagnosticar primero con `agent-browser doctor --offline --quick` y repetir solo el login afectado:

```bash
uv run scripts/arca_auth.py login --session arca-operacion --browser-args=--no-sandbox
```

No agregar `--no-sandbox` por defecto: usarlo solo cuando el diagnóstico o el error de Chrome lo indique.

`auth add` toma el CUIT de `--cuit` o `ARCA_CUIT`; si falta y hay TTY, lo pregunta. Para la clave usa `ARCA_PASSWORD` solamente cuando corresponde al mismo `ARCA_CUIT`; en otro caso la pide una vez con `getpass`. El agente debe dar el comando para que el usuario lo ejecute personalmente y nunca pedir la clave por chat.

Los perfiles creados por el helper usan `scripts/arca_login.js` para atravesar el login secuencial CUIT -> `Siguiente` -> clave. El perfil se almacena cifrado por `agent-browser`. El default local se guarda sin secretos en `~/.config/arca-skills/auth.json`; `ARCA_AUTH_PROFILE` tiene prioridad sobre ese archivo.

El comando `login` deja abierta una sesion autenticada. Cerrarla al terminar:

```bash
agent-browser --session arca-operacion close
```

## Fallback `.env`

Mantener compatibilidad con:

```dotenv
ARCA_CUIT=20123456789
ARCA_PASSWORD=clave_fiscal
# ARCA_AUTH_PROFILE=arca-martin
```

`ARCA_AUTH_PROFILE` es opcional. Si no hay un perfil vault utilizable, el helper crea un perfil cifrado temporal desde `ARCA_CUIT`/`ARCA_PASSWORD`, inicia sesion y lo elimina inmediatamente. No pasar la clave como argumento de proceso.
