# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "python-dotenv>=1,<2",
# ]
# ///
"""Manage ARCA auth-vault profiles and open an authenticated browser session."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import secrets
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import dotenv_values, find_dotenv

LOGIN_URL = "https://auth.afip.gob.ar/contribuyente_/login.xhtml"
PORTAL_URL_GLOB = "**/portal/app*"
USERNAME_SELECTOR = 'input[aria-label="CUIT/CUIL"], input[type="number"]'
PASSWORD_SELECTOR = 'input[aria-label="TU CLAVE"], input[type="password"]'
INIT_SCRIPT = Path(__file__).with_name("arca_login.js")


class AuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class AuthProfile:
    name: str
    cuit: str
    url: str


def normalized(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def normalize_cuit(value: str) -> str:
    cuit = re.sub(r"\D", "", value or "")
    if len(cuit) != 11:
        raise AuthError("El CUIT/CUIL debe tener 11 digitos")
    return cuit


def settings() -> dict[str, str]:
    dotenv = find_dotenv(usecwd=True)
    file_values = dotenv_values(dotenv) if dotenv else {}
    return {
        "ARCA_AUTH_PROFILE": str(
            os.environ.get("ARCA_AUTH_PROFILE")
            or file_values.get("ARCA_AUTH_PROFILE")
            or ""
        ).strip(),
        "ARCA_CUIT": str(
            os.environ.get("ARCA_CUIT") or file_values.get("ARCA_CUIT") or ""
        ).strip(),
        "ARCA_PASSWORD": str(
            os.environ.get("ARCA_PASSWORD") or file_values.get("ARCA_PASSWORD") or ""
        ),
    }


def clean_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("ARCA_CUIT", None)
    environment.pop("ARCA_PASSWORD", None)
    return environment


def config_path() -> Path:
    root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return root / "arca-skills" / "auth.json"


def configured_default() -> str:
    path = config_path()
    if not path.exists():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return str(payload.get("default_profile") or "").strip()
    except (json.JSONDecodeError, OSError) as exc:
        raise AuthError(f"Configuracion invalida en {path}") from exc


def set_configured_default(name: str) -> Path:
    profile = get_profile(name)
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"default_profile": profile.name}, indent=2) + "\n",
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


def run_agent_browser(
    *args: str,
    input_text: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["agent-browser", *args],
        env=clean_environment(),
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode:
        message = (result.stderr or result.stdout).strip()
        raise AuthError(message or f"agent-browser fallo: {' '.join(args)}")
    return result


def parse_agent_json(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AuthError(f"Respuesta inesperada de agent-browser: {raw[:300]}") from exc
    if not payload.get("success"):
        raise AuthError(str(payload.get("error") or "agent-browser fallo"))
    return dict(payload.get("data") or {})


def get_profile(name: str) -> AuthProfile:
    result = run_agent_browser("auth", "show", name, "--json")
    profile = parse_agent_json(result.stdout).get("profile") or {}
    cuit = normalize_cuit(str(profile.get("username") or ""))
    return AuthProfile(
        name=str(profile.get("name") or name),
        cuit=cuit,
        url=str(profile.get("url") or ""),
    )


def list_profiles() -> list[AuthProfile]:
    result = run_agent_browser("auth", "list", "--json")
    summaries = parse_agent_json(result.stdout).get("profiles") or []
    profiles: list[AuthProfile] = []
    for summary in summaries:
        name = str(summary.get("name") or "")
        url = str(summary.get("url") or "")
        if name.startswith("arca-env-"):
            run_agent_browser("auth", "delete", name, check=False)
            continue
        if name and "auth.afip.gob.ar" in url:
            profiles.append(get_profile(name))
    return sorted(profiles, key=lambda profile: profile.name)


def match_profile(profiles: list[AuthProfile], query: str) -> AuthProfile:
    wanted = normalized(query)
    digits = re.sub(r"\D", "", query)
    exact = [
        profile
        for profile in profiles
        if normalized(profile.name) == wanted or (len(digits) == 11 and profile.cuit == digits)
    ]
    if len(exact) == 1:
        return exact[0]
    partial = [profile for profile in profiles if wanted and wanted in normalized(profile.name)]
    if len(partial) == 1:
        return partial[0]
    if not exact and not partial:
        raise AuthError(f"No existe un perfil ARCA que coincida con {query!r}")
    choices = ", ".join(profile.name for profile in exact or partial)
    raise AuthError(f"Perfil ambiguo {query!r}; coincidencias: {choices}")


def resolve_profile(
    requested: str = "",
    requested_cuit: str = "",
) -> AuthProfile | None:
    profiles = list_profiles()
    if requested:
        return match_profile(profiles, requested)
    if requested_cuit:
        return match_profile(profiles, normalize_cuit(requested_cuit))

    values = settings()
    if values["ARCA_AUTH_PROFILE"]:
        return match_profile(profiles, values["ARCA_AUTH_PROFILE"])
    if values["ARCA_CUIT"]:
        selected_cuit = normalize_cuit(values["ARCA_CUIT"])
        matches = [
            profile
            for profile in profiles
            if profile.cuit == selected_cuit
        ]
        if len(matches) == 1:
            return matches[0]
        if values["ARCA_PASSWORD"]:
            return None
        raise AuthError(
            f"No existe un perfil vault para ARCA_CUIT={selected_cuit} y falta ARCA_PASSWORD"
        )

    default = configured_default()
    if default:
        return match_profile(profiles, default)
    if len(profiles) == 1:
        return profiles[0]
    if not profiles:
        return None

    choices = ", ".join(f"{profile.name} ({profile.cuit})" for profile in profiles)
    raise AuthError(
        "Hay varios perfiles ARCA y ninguno es predeterminado. "
        f"Elegir uno: {choices}"
    )


def save_profile(name: str, cuit: str, password: str) -> None:
    run_agent_browser(
        "auth",
        "save",
        name,
        "--url",
        LOGIN_URL,
        "--username",
        cuit,
        "--password-stdin",
        "--username-selector",
        USERNAME_SELECTOR,
        "--password-selector",
        PASSWORD_SELECTOR,
        "--submit-selector",
        PASSWORD_SELECTOR,
        input_text=password + "\n",
    )


def load_env_credentials() -> tuple[str, str]:
    values = settings()
    if not values["ARCA_CUIT"] or not values["ARCA_PASSWORD"]:
        raise AuthError(
            "No hay perfil ARCA utilizable ni un par ARCA_CUIT/ARCA_PASSWORD en .env"
        )
    return normalize_cuit(values["ARCA_CUIT"]), values["ARCA_PASSWORD"]


def close_session(session: str) -> None:
    run_agent_browser("--session", session, "close", check=False)


def login_with_profile(
    profile: AuthProfile,
    session: str,
    browser_args: str = "",
) -> None:
    if not INIT_SCRIPT.exists():
        raise AuthError(f"No existe init script: {INIT_SCRIPT}")
    close_session(session)

    prefix = ["--session", session]
    if browser_args:
        prefix.extend(["--args", browser_args])
    prefix.extend(["--init-script", str(INIT_SCRIPT)])
    try:
        result = run_agent_browser(*prefix, "auth", "login", profile.name, "--json")
    except AuthError as exc:
        if browser_args or "No usable sandbox" not in str(exc):
            raise
        close_session(session)
        return login_with_profile(profile, session, "--no-sandbox")

    parse_agent_json(result.stdout)
    current = run_agent_browser("--session", session, "get", "url").stdout.strip()
    if "/portal/app" not in current:
        run_agent_browser(
            "--session",
            session,
            "find",
            "role",
            "button",
            "click",
            "--name",
            "Ingresar",
        )
        run_agent_browser("--session", session, "wait", "--url", PORTAL_URL_GLOB)


def login_with_credentials(
    cuit: str,
    password: str,
    session: str,
    browser_args: str = "",
) -> None:
    temporary = f"arca-env-{os.getpid()}-{secrets.token_hex(4)}"
    save_profile(temporary, normalize_cuit(cuit), password)
    try:
        login_with_profile(get_profile(temporary), session, browser_args)
    finally:
        run_agent_browser("auth", "delete", temporary, check=False)


def add_command(args: argparse.Namespace) -> int:
    values = settings()
    raw_cuit = args.cuit or values["ARCA_CUIT"]
    if not raw_cuit:
        if not sys.stdin.isatty():
            raise AuthError("Falta el CUIT/CUIL; usar --cuit o ejecutar desde una terminal")
        raw_cuit = input("CUIT/CUIL de ARCA: ").strip()
    cuit = normalize_cuit(raw_cuit)
    name = args.profile or f"arca-{cuit}"
    if name.startswith("arca-env-"):
        raise AuthError("El prefijo arca-env- esta reservado para perfiles temporales")

    existing = {profile.name for profile in list_profiles()}
    if name in existing and not args.replace:
        raise AuthError(f"El perfil {name!r} ya existe; usar --replace para actualizarlo")

    password = ""
    if (
        values["ARCA_PASSWORD"]
        and values["ARCA_CUIT"]
        and normalize_cuit(values["ARCA_CUIT"]) == cuit
    ):
        password = values["ARCA_PASSWORD"]
    if not password:
        if not sys.stdin.isatty():
            raise AuthError(
                "La clave no esta en el .env del mismo CUIT. Ejecutar auth add "
                "personalmente desde una terminal; no pegarla en el chat"
            )
        password = getpass.getpass("Clave fiscal de ARCA: ")
    if not password:
        raise AuthError("La clave fiscal no puede estar vacia")

    save_profile(name, cuit, password)
    default_path = set_configured_default(name) if args.default else None
    print(
        json.dumps(
            {
                "status": "saved",
                "profile": name,
                "cuit": cuit,
                "default": bool(args.default),
                "config": str(default_path) if default_path else None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def list_command(_args: argparse.Namespace) -> int:
    profiles = list_profiles()
    default_query = settings()["ARCA_AUTH_PROFILE"] or configured_default()
    default = match_profile(profiles, default_query).name if default_query else ""
    print(
        json.dumps(
            {
                "default": default or None,
                "profiles": [
                    {
                        "name": profile.name,
                        "cuit": profile.cuit,
                        "default": profile.name == default,
                    }
                    for profile in profiles
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def default_command(args: argparse.Namespace) -> int:
    profile = match_profile(list_profiles(), args.profile)
    path = set_configured_default(profile.name)
    print(
        json.dumps(
            {"status": "default_set", "profile": profile.name, "config": str(path)},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def login_command(args: argparse.Namespace) -> int:
    profile = resolve_profile(args.profile, args.cuit)
    browser_args = args.browser_args or os.environ.get("ARCA_AGENT_BROWSER_ARGS", "")
    if profile:
        login_with_profile(profile, args.session, browser_args)
        cuit = profile.cuit
        source = f"vault:{profile.name}"
    else:
        cuit, password = load_env_credentials()
        login_with_credentials(cuit, password, args.session, browser_args)
        source = "env"
    print(
        json.dumps(
            {
                "status": "logged_in",
                "session": args.session,
                "cuit": cuit,
                "source": source,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add", help="Guardar un login en el auth vault")
    add_parser.add_argument("--profile", default="", help="Alias, por ejemplo arca-natalia")
    add_parser.add_argument("--cuit", default="")
    add_parser.add_argument("--default", action="store_true")
    add_parser.add_argument("--replace", action="store_true")
    add_parser.set_defaults(handler=add_command)

    list_parser = subparsers.add_parser("list", help="Listar perfiles ARCA")
    list_parser.set_defaults(handler=list_command)

    default_parser = subparsers.add_parser("default", help="Elegir perfil predeterminado")
    default_parser.add_argument("profile")
    default_parser.set_defaults(handler=default_command)

    login_parser = subparsers.add_parser("login", help="Abrir una sesion autenticada")
    login_parser.add_argument("--profile", default="", help="Nombre, alias o fragmento")
    login_parser.add_argument("--cuit", default="")
    login_parser.add_argument("--session", default="arca-login")
    login_parser.add_argument("--browser-args", default="")
    login_parser.set_defaults(handler=login_command)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.handler(args))
    except AuthError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
