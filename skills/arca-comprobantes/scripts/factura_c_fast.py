# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pypdf>=5,<7",
#   "python-dotenv>=1,<2",
# ]
# ///
"""Fast path for preparing and confirming a standard ARCA Factura C.

The prepare command stops at RCEL step 4. The confirm command requires --yes,
revalidates that review, generates the invoice, and downloads the official PDF.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import urllib.request
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from arca_auth import (
    AuthError,
    clean_environment,
    load_env_credentials,
    login_with_credentials,
    login_with_profile,
    resolve_profile,
)
from pypdf import PdfReader

RCEL_URL_PART = "fe.afip.gob.ar/rcel"
RCEL_MENU_URL = "https://fe.afip.gob.ar/rcel/jsp/menu_ppal.jsp"
STATE_DIR = Path(tempfile.gettempdir()) / "arca-skills"


class FastPathError(RuntimeError):
    pass


def normalized(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def slug(value: str) -> str:
    return normalized(value).replace(" ", "_") or "cliente"


def parse_amount(value: str) -> Decimal:
    try:
        amount = Decimal(value.replace(".", "").replace(",", ".") if "," in value else value)
    except InvalidOperation as exc:
        raise FastPathError(f"Importe invalido: {value}") from exc
    if amount <= 0:
        raise FastPathError("El importe debe ser positivo")
    return amount.quantize(Decimal("0.01"))


def validate_date(value: str) -> str:
    try:
        datetime.strptime(value, "%d/%m/%Y")
    except ValueError as exc:
        raise FastPathError(f"Fecha invalida: {value}; usar DD/MM/YYYY") from exc
    return value


def state_path(session: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "-", session)
    return STATE_DIR / f"factura-c-{safe}.json"


def write_state(session: str, payload: dict[str, Any]) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = state_path(session)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def read_state(session: str) -> dict[str, Any]:
    path = state_path(session)
    if not path.exists():
        raise FastPathError(f"No existe preparacion para la sesion {session!r}")
    return json.loads(path.read_text(encoding="utf-8"))


def subprocess_environment() -> dict[str, str]:
    return clean_environment()


def lookup_name(cuit: str) -> str:
    try:
        request = urllib.request.Request(
            f"https://arcadb.fastapicloud.dev/v1/records/{cuit}",
            headers={"Accept": "application/json", "User-Agent": "arca-skills/1.0"},
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.load(response)
        return str(payload.get("denominacion") or "").strip()
    except Exception:
        return ""


class Browser:
    def __init__(self, session: str, browser_args: str = "") -> None:
        self.session = session
        self.browser_args = browser_args

    def _command(self, *args: str, launch: bool = False) -> list[str]:
        command = ["agent-browser", "--session", self.session]
        if launch and self.browser_args:
            command.extend(["--args", self.browser_args])
        command.extend(args)
        return command

    def run(
        self,
        *args: str,
        launch: bool = False,
        check: bool = True,
        quiet: bool = False,
    ) -> str:
        result = subprocess.run(
            self._command(*args, launch=launch),
            env=subprocess_environment(),
            text=True,
            capture_output=True,
            check=False,
        )
        if check and result.returncode:
            message = (result.stderr or result.stdout).strip()
            raise FastPathError(message or f"agent-browser fallo: {' '.join(args)}")
        if not quiet and result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        return result.stdout

    def evaluate(self, script: str) -> Any:
        raw = self.run("eval", script, "--json", quiet=True)
        return self._parse_evaluation(raw)

    @staticmethod
    def _parse_evaluation(raw: str) -> Any:
        try:
            payload = json.loads(raw)
            if not payload.get("success"):
                raise FastPathError(str(payload.get("error") or "eval fallo"))
            return payload["data"]["result"]
        except (json.JSONDecodeError, KeyError) as exc:
            raise FastPathError(f"Respuesta eval inesperada: {raw[:500]}") from exc

    def wait(self, milliseconds: int = 250) -> None:
        self.run("wait", str(milliseconds), quiet=True)

    def url(self) -> str:
        return self.run("get", "url", quiet=True).strip()

    def close(self) -> None:
        self.run("close", check=False, quiet=True)

def set_values(browser: Browser, values: dict[str, str]) -> None:
    script = """
    (() => {
      const values = %s;
      for (const [selector, value] of Object.entries(values)) {
        const node = document.querySelector(selector);
        if (!node) throw new Error(`No existe ${selector}`);
        node.value = value;
        node.dispatchEvent(new Event('input', {bubbles: true}));
        node.dispatchEvent(new Event('change', {bubbles: true}));
        node.dispatchEvent(new Event('blur', {bubbles: true}));
      }
      return true;
    })()
    """ % json.dumps(values, ensure_ascii=False)
    browser.evaluate(script)


def click_value(browser: Browser, value: str) -> None:
    script = """
    (() => {
      const wanted = %s;
      const button = [...document.querySelectorAll('input[type=button], input[type=submit]')]
        .find(node => node.value.trim() === wanted);
      if (!button) throw new Error(`No existe boton ${wanted}`);
      button.click();
      return true;
    })()
    """ % json.dumps(value)
    browser.evaluate(script)


def select_text(browser: Browser, selector: str, text: str) -> str:
    script = """
    (() => {
      const selector = %s;
      const wanted = %s;
      const norm = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        .toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
      const select = document.querySelector(selector);
      if (!select) throw new Error(`No existe ${selector}`);
      const index = [...select.options].findIndex(option => norm(option.text) === norm(wanted));
      if (index < 0) throw new Error(`No existe opcion ${wanted}`);
      select.selectedIndex = index;
      select.dispatchEvent(new Event('change', {bubbles: true}));
      select.dispatchEvent(new Event('blur', {bubbles: true}));
      return select.selectedOptions[0].text.trim();
    })()
    """ % (json.dumps(selector), json.dumps(text, ensure_ascii=False))
    return str(browser.evaluate(script))


def open_rcel(browser: Browser) -> None:
    browser.run("wait", "--text", "Comprobantes en línea", quiet=True)
    browser.evaluate(
        """
        (() => {
          const node = [...document.querySelectorAll('*')]
            .find(e => e.children.length === 0 && /Comprobantes en línea/i.test(e.textContent));
          const clickable = node?.closest('a, button, [role=button], .card, .panel, .media');
          if (!clickable) throw new Error('No aparece Comprobantes en linea');
          clickable.click();
          return true;
        })()
        """
    )
    browser.wait(500)
    if RCEL_URL_PART not in browser.url():
        tabs = browser.run("tab", quiet=True)
        match = re.search(r"\[(t\d+)\].*fe\.afip\.gob\.ar/rcel", tabs)
        if not match:
            raise FastPathError("RCEL no se abrio en ninguna pestaña")
        browser.run("tab", match.group(1), quiet=True)
    browser.run("wait", "--load", "domcontentloaded", quiet=True)


def choose_represented(browser: Browser, represented: str) -> str:
    script = """
    (() => {
      const wanted = %s;
      const norm = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        .toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim().split(/\\s+/).sort().join(' ');
      const choices = [...document.querySelectorAll('input[type=button]')];
      if (!choices.length) return document.body.innerText;
      const button = choices.find(node => norm(node.value) === norm(wanted));
      if (!button) throw new Error(`No coincide representado: ${wanted}`);
      button.click();
      return button.value;
    })()
    """ % json.dumps(represented, ensure_ascii=False)
    selected = str(browser.evaluate(script))
    browser.wait(250)
    if "menu_ppal.jsp" not in browser.url():
        browser.run("open", RCEL_MENU_URL, quiet=True)
    body = str(browser.evaluate("document.body.innerText"))
    if "Representando a" not in body:
        raise FastPathError("No se pudo validar la empresa representada")
    return selected


def choose_factura_c_point(browser: Browser, requested: str = "") -> str:
    browser.run("click", "#btn_gen_cmp", quiet=True)
    browser.run("wait", "--load", "domcontentloaded", quiet=True)
    points = browser.evaluate(
        "[...document.querySelector('#puntodeventa').options].filter(o => o.value).map(o => ({value:o.value,text:o.text.trim()}))"
    )
    if requested:
        points = [point for point in points if requested in point["text"]]
    for point in points:
        browser.run("select", "#puntodeventa", str(point["value"]), quiet=True)
        browser.wait(150)
        types = browser.evaluate(
            "[...document.querySelector('#universocomprobante').options].map(o => ({value:o.value,text:o.text.trim()}))"
        )
        invoice = next((item for item in types if normalized(item["text"]) == "factura c"), None)
        if invoice:
            browser.run("select", "#universocomprobante", str(invoice["value"]), quiet=True)
            click_value(browser, "Continuar >")
            browser.wait(200)
            return str(point["text"])
    raise FastPathError("Ningun punto de venta ofrece Factura C")


def prepare(args: argparse.Namespace) -> int:
    try:
        profile = resolve_profile(args.auth_profile, args.auth_cuit)
        if profile:
            cuit = profile.cuit
            auth_source = f"vault:{profile.name}"
        else:
            cuit, password = load_env_credentials()
            auth_source = "env"
    except AuthError as exc:
        raise FastPathError(str(exc)) from exc

    represented = args.represented or lookup_name(cuit)
    if not represented:
        raise FastPathError("No se pudo resolver el representado; usar --represented")
    amount = parse_amount(args.amount)
    invoice_date = validate_date(args.date)
    period_from = validate_date(args.period_from or invoice_date)
    period_to = validate_date(args.period_to or invoice_date)
    due = validate_date(args.due or invoice_date)
    client_cuit = re.sub(r"\D", "", args.client_cuit)
    if len(client_cuit) != 11:
        raise FastPathError("--client-cuit debe tener 11 digitos")

    browser = Browser(args.session, args.browser_args or os.environ.get("ARCA_AGENT_BROWSER_ARGS", ""))
    try:
        if profile:
            login_with_profile(profile, args.session, browser.browser_args)
        else:
            login_with_credentials(cuit, password, args.session, browser.browser_args)
            del password
    except AuthError as exc:
        raise FastPathError(str(exc)) from exc
    open_rcel(browser)
    selected = choose_represented(browser, represented)
    point = choose_factura_c_point(browser, args.point)

    select_text(browser, "#idconcepto", "Servicios")
    set_values(
        browser,
        {
            "#fc": invoice_date,
            "#fsd": period_from,
            "#fsh": period_to,
            "#vencimientopago": due,
        },
    )
    click_value(browser, "Continuar >")
    browser.wait(200)

    select_text(browser, "#idivareceptor", args.iva_condition)
    browser.wait(150)
    select_text(browser, "#idtipodocreceptor", "CUIT")
    set_values(browser, {"#nrodocreceptor": client_cuit})
    browser.wait(700)
    receiver = browser.evaluate(
        """
        (() => ({
          name: document.querySelector('#razonsocialreceptor')?.value || '',
          addresses: [...document.querySelector('#domicilioreceptorcombo')?.options || []]
            .map(o => ({text:o.text.trim(),value:o.value}))
        }))()
        """
    )
    if normalized(args.client_name) not in normalized(receiver["name"]):
        raise FastPathError(f"ARCA devolvio otro receptor: {receiver['name']!r}")
    address = next(
        (
            item
            for item in receiver["addresses"]
            if normalized(args.address) in normalized(item["text"])
            or normalized(item["text"]) in normalized(args.address)
        ),
        None,
    )
    if not address:
        available = "; ".join(item["text"] for item in receiver["addresses"] if item["text"])
        raise FastPathError(f"No coincide domicilio {args.address!r}. Disponibles: {available}")
    browser.run("select", "#domicilioreceptorcombo", str(address["value"]), quiet=True)
    payment_script = """
    (() => {
      const wanted = %s;
      const norm = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        .toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
      const box = [...document.querySelectorAll('input[name=formaDePago],input[name=formaDePagoTarjeta]')]
        .find(node => norm(node.parentElement?.innerText || '') === norm(wanted));
      if (!box) throw new Error(`No existe condicion ${wanted}`);
      box.checked = true;
      box.dispatchEvent(new Event('change', {bubbles:true}));
      return box.id;
    })()
    """ % json.dumps(args.sale_condition, ensure_ascii=False)
    browser.evaluate(payment_script)
    click_value(browser, "Continuar >")
    browser.wait(200)

    set_values(
        browser,
        {
            "#detalle_descripcion1": args.description,
            "#detalle_cantidad1": "1",
            "#detalle_precio1": f"{amount:.2f}",
        },
    )
    select_text(browser, "#detalle_medida1", "unidades")
    browser.wait(150)
    loaded_total = str(browser.evaluate("document.querySelector('#imptotal')?.value || ''"))
    if Decimal(loaded_total or "0") != amount:
        raise FastPathError(f"Total cargado inesperado: {loaded_total}")
    click_value(browser, "Continuar >")
    browser.wait(200)

    review = browser.evaluate("({url:location.href,text:document.body.innerText})")
    expected = [client_cuit, args.client_name, args.description]
    missing = [value for value in expected if normalized(value) not in normalized(review["text"])]
    if "genComResumenDatos.do" not in review["url"] or missing:
        raise FastPathError(f"Revision final incompleta; faltan: {missing}")
    if f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") not in review["text"]:
        raise FastPathError("El total no aparece en la revision final")

    payload = {
        "schema": "arca_factura_c_fast_v1",
        "status": "ready_for_confirmation",
        "session": args.session,
        "auth_source": auth_source,
        "represented": selected,
        "point": point,
        "client_cuit": client_cuit,
        "client_name": receiver["name"],
        "address": address["text"],
        "iva_condition": args.iva_condition,
        "sale_condition": args.sale_condition,
        "description": args.description,
        "amount_ars": f"{amount:.2f}",
        "date": invoice_date,
        "period_from": period_from,
        "period_to": period_to,
        "due": due,
        "created_at": datetime.now().astimezone().isoformat(),
    }
    path = write_state(args.session, payload)
    print(json.dumps({**payload, "state_file": str(path)}, ensure_ascii=False, indent=2))
    return 0


def documents_dir() -> Path:
    if shutil.which("xdg-user-dir"):
        result = subprocess.run(
            ["xdg-user-dir", "DOCUMENTS"],
            env=subprocess_environment(),
            text=True,
            capture_output=True,
            check=False,
        ).stdout.strip()
        if result and result != str(Path.home()):
            return Path(result)
    spanish = Path.home() / "Documentos"
    return spanish if spanish.exists() else Path.home() / "Documents"


def unique_destination(directory: Path, filename: str) -> Path:
    path = directory / filename
    counter = 2
    while path.exists():
        path = directory / f"{Path(filename).stem}-{counter}{Path(filename).suffix}"
        counter += 1
    return path


def confirm(args: argparse.Namespace) -> int:
    if not args.yes:
        raise FastPathError("Confirmacion bloqueada: volver a ejecutar con --yes tras aprobacion humana")
    state = read_state(args.session)
    browser = Browser(args.session)
    try:
        review = browser.evaluate("({url:location.href,text:document.body.innerText})")
        if "genComResumenDatos.do" not in review["url"]:
            raise FastPathError(f"La sesion no esta en revision final: {review['url']}")
        for field in ("client_cuit", "client_name", "description"):
            if normalized(state[field]) not in normalized(review["text"]):
                raise FastPathError(f"La revision ya no coincide en {field}")
        amount = Decimal(state["amount_ars"])
        display_amount = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        if display_amount not in review["text"]:
            raise FastPathError("La revision ya no coincide en importe")

        browser.run("click", "#btngenerar", quiet=True)
        browser.wait(150)
        browser.run("find", "role", "button", "click", "--name", "Confirmar", quiet=True)
        browser.wait(300)
        generated = browser.evaluate(
            "({generated:/Comprobante Generado/.test(document.body.innerText), id:typeof idComprobante === 'undefined' ? '' : String(idComprobante)})"
        )
        if not generated["generated"] or not generated["id"]:
            raise FastPathError("ARCA no confirmo la generacion")

        with tempfile.TemporaryDirectory(prefix="arca-factura-") as temp_dir:
            temp_pdf = Path(temp_dir) / "factura.pdf"
            browser.run(
                "download",
                'input[type="button"][value="Imprimir..."]',
                str(temp_pdf),
                quiet=True,
            )
            reader = PdfReader(str(temp_pdf))
            pdf_text = "\n".join(page.extract_text() or "" for page in reader.pages)
            if state["client_cuit"] not in re.sub(r"\D", "", pdf_text):
                raise FastPathError("El PDF no contiene el CUIT esperado")
            if normalized(state["client_name"]) not in normalized(pdf_text):
                raise FastPathError("El PDF no contiene el receptor esperado")
            match = re.search(
                r"Punto de Venta:\s*(\d+).*?Comp\. Nro:\s*(\d+)", pdf_text, re.DOTALL
            )
            cae = re.search(r"CAE\s*N[°º]:\s*(\d+)", pdf_text)
            if not match or not cae:
                raise FastPathError("No se pudo extraer numero o CAE del PDF")
            point, number = match.groups()
            client_dir = documents_dir() / "facturas" / (
                f"{slug(state['client_name'])}_{state['client_cuit']}"
            )
            client_dir.mkdir(parents=True, exist_ok=True)
            destination = unique_destination(
                client_dir, f"Factura_C_{int(point):05d}_{int(number):08d}.pdf"
            )
            shutil.move(str(temp_pdf), destination)

        state_path(args.session).unlink(missing_ok=True)
        result = {
            "status": "generated",
            "point": f"{int(point):05d}",
            "number": f"{int(number):08d}",
            "cae": cae.group(1),
            "amount_ars": state["amount_ars"],
            "pdf": str(destination),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        browser.close()


def cancel(args: argparse.Namespace) -> int:
    Browser(args.session).close()
    state_path(args.session).unlink(missing_ok=True)
    print(json.dumps({"status": "cancelled", "session": args.session}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare", help="Cargar hasta revision final")
    prepare_parser.add_argument("--client-cuit", required=True)
    prepare_parser.add_argument("--client-name", required=True)
    prepare_parser.add_argument("--address", required=True, help="Texto completo o fragmento inequívoco")
    prepare_parser.add_argument("--description", required=True)
    prepare_parser.add_argument("--amount", required=True, help="Total final en ARS, punto decimal")
    prepare_parser.add_argument("--iva-condition", default="IVA Responsable Inscripto")
    prepare_parser.add_argument("--sale-condition", default="Contado")
    prepare_parser.add_argument("--represented", default="")
    prepare_parser.add_argument("--point", default="", help="Numero o fragmento del punto")
    today = date.today().strftime("%d/%m/%Y")
    prepare_parser.add_argument("--date", default=today)
    prepare_parser.add_argument("--period-from", default="")
    prepare_parser.add_argument("--period-to", default="")
    prepare_parser.add_argument("--due", default="")
    prepare_parser.add_argument("--session", default="arca-factura-c")
    prepare_parser.add_argument("--browser-args", default="")
    prepare_parser.add_argument("--auth-profile", default="", help="Perfil vault o alias")
    prepare_parser.add_argument("--auth-cuit", default="", help="CUIT del perfil vault")
    prepare_parser.set_defaults(handler=prepare)

    confirm_parser = subparsers.add_parser("confirm", help="Generar y descargar tras aprobacion")
    confirm_parser.add_argument("--session", default="arca-factura-c")
    confirm_parser.add_argument("--yes", action="store_true")
    confirm_parser.set_defaults(handler=confirm)

    cancel_parser = subparsers.add_parser("cancel", help="Cerrar sesion y borrar preparacion")
    cancel_parser.add_argument("--session", default="arca-factura-c")
    cancel_parser.set_defaults(handler=cancel)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.handler(args))
    except FastPathError as exc:
        if args.command == "prepare":
            Browser(args.session).close()
            state_path(args.session).unlink(missing_ok=True)
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
