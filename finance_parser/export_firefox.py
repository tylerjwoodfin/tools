"""Drive the Amazon Order History Exporter extension with Playwright Firefox.

Uses a dedicated Nightly profile (not the daily Firefox profile) and the
signed extension copied from the profile where it is installed. Playwright
cannot open the extension popup or dismiss its save dialog, so the script
arms the extension on the order-history page and records the orders it parses.
Amazon cookies are read from that daily profile.
"""

from __future__ import annotations

import csv
import json
import re
import sqlite3
import time
from datetime import date
from pathlib import Path

EXT_ID = "order-history-exporter@amazon.example"
EXT_UUID = "3b400a64-85c4-4ad3-a18f-7e132d6b3261"
ORDER_URL = "https://www.amazon.com/gp/your-account/order-history"
DATA_DIR = Path.home() / ".local" / "share" / "amazon-sure"
PROFILE_DIR = DATA_DIR / "firefox-profile"
DOWNLOAD_DIR = DATA_DIR / "downloads"
EXPORT_TIMEOUT_S = 20 * 60
PARSED_ORDER_RE = re.compile(
    r"Parsed order: (?P<id>[^,]+), (?P<date>\d{4}-\d{2}-\d{2}), "
    r"(?P<amount>-?[0-9.]+) (?P<currency>[A-Z]{3})"
)
CSV_COLUMNS = [
    "Order ID",
    "Order Date",
    "Total Amount",
    "Currency",
    "Total Savings",
    "Status",
    "Item Title",
]
CARD_JS = """
() => {
  const cards = document.querySelectorAll(".order-card");
  return [...cards].map((card) => {
    const rawId = card.querySelector(".yohtmlc-order-id")?.innerText || "";
    const id = rawId.replace(/ORDER\\s*#\\s*/i, "").trim();
    const titles = [...card.querySelectorAll(".yohtmlc-product-title")]
      .map((node) => node.innerText.trim())
      .filter(Boolean);
    const status = (
      card.querySelector(".yohtmlc-shipment-status-primaryText")?.innerText || ""
    ).trim();
    return { id, titles, status };
  }).filter((row) => row.id);
}
"""


def find_extension_xpi() -> Path:
    """Path to the exporter installed in a Firefox profile on this machine."""
    root = Path.home() / "Library" / "Application Support" / "Firefox" / "Profiles"
    matches = sorted(root.glob(f"*/extensions/{EXT_ID}.xpi"))
    if not matches:
        raise RuntimeError(
            "Order History Exporter for Amazon is not installed in Firefox on this machine."
        )
    return matches[0]


def daily_firefox_profile() -> Path:
    """Profile that contains the exporter (and the Amazon login)."""
    return find_extension_xpi().parent.parent


def _expiry_seconds(raw: int) -> int:
    """Firefox builds here store expiry in milliseconds; older ones use seconds."""
    if raw > 10**14:
        return raw // 1_000_000
    if raw > 10**11:
        return raw // 1000
    return raw


def _same_site(raw: int, secure: bool) -> str:
    """Map Firefox's sameSite bitfield to a Playwright value."""
    low = raw & 0x03
    name = {0: "None", 1: "Lax", 2: "Strict"}.get(low, "Lax")
    if name == "None" and not secure:
        return "Lax"
    return name


def amazon_cookies() -> list[dict[str, object]]:
    """Amazon cookies from the daily Firefox profile, for the automation browser."""
    database = daily_firefox_profile() / "cookies.sqlite"
    if not database.is_file():
        raise RuntimeError(f"Firefox cookie database not found: {database}")
    uri = f"file:{database}?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    try:
        rows = connection.execute(
            """
            select host, name, value, path, expiry, isSecure, isHttpOnly, sameSite
            from moz_cookies
            where host like '%amazon.com' and originAttributes = ''
            """
        ).fetchall()
    finally:
        connection.close()

    now = int(time.time())
    cookies: list[dict[str, object]] = []
    for host, name, value, path, expiry, is_secure, is_http_only, same_site in rows:
        if not name:
            continue
        expires = _expiry_seconds(int(expiry or 0))
        if expires and expires < now:
            continue
        secure = bool(is_secure)
        item: dict[str, object] = {
            "name": name,
            "value": value,
            "domain": host,
            "path": path or "/",
            "httpOnly": bool(is_http_only),
            "secure": secure,
            "sameSite": _same_site(int(same_site or 0), secure),
        }
        if expires:
            item["expires"] = expires
        cookies.append(item)
    if not cookies:
        raise RuntimeError(
            "No usable Amazon cookies in Firefox. Sign in to Amazon in Firefox and retry."
        )
    return cookies


def prepare_profile(download_dir: Path) -> Path:
    """Dedicated Playwright profile with the signed exporter sideloaded.

    The xpi is copied unchanged. A modified copy loses its Mozilla signature
    and this Nightly build deletes it on startup.
    """
    profile = PROFILE_DIR
    profile.mkdir(parents=True, exist_ok=True)
    download_dir.mkdir(parents=True, exist_ok=True)
    extensions = profile / "extensions"
    extensions.mkdir(exist_ok=True)
    source = find_extension_xpi().read_bytes()
    target = extensions / f"{EXT_ID}.xpi"
    if not target.is_file() or target.read_bytes() != source:
        target.write_bytes(source)
        for name in ("addonStartup.json.lz4", "extensions.json"):
            stale = profile / name
            if stale.exists():
                stale.unlink()
    uuids = json.dumps({EXT_ID: EXT_UUID})
    prefs = "\n".join(
        [
            'user_pref("xpinstall.signatures.required", false);',
            'user_pref("extensions.autoDisableScopes", 0);',
            'user_pref("extensions.enabledScopes", 5);',
            f'user_pref("extensions.webextensions.uuids", {json.dumps(uuids)});',
            'user_pref("browser.download.folderList", 2);',
            f'user_pref("browser.download.dir", {json.dumps(str(download_dir))});',
            'user_pref("browser.download.useDownloadDir", true);',
            'user_pref("browser.download.manager.showWhenStarting", false);',
            'user_pref("browser.shell.checkDefaultBrowser", false);',
            'user_pref("browser.aboutwelcome.enabled", false);',
            'user_pref("datareporting.policy.dataSubmissionEnabled", false);',
            "",
        ]
    )
    (profile / "user.js").write_text(prefs)
    return profile


def parse_parsed_order_line(text: str) -> dict[str, str] | None:
    """Parse one exporter console line, or None when it is not an order."""
    match = PARSED_ORDER_RE.search(text or "")
    if not match:
        return None
    return match.groupdict()


def merge_cards(cards: dict[str, dict[str, object]], rows: list[dict[str, object]]) -> None:
    """Keep titles and status seen on order cards while the exporter walks pages."""
    for row in rows:
        order_id = str(row.get("id") or "").strip()
        if not order_id:
            continue
        current = cards.setdefault(order_id, {"titles": [], "status": ""})
        titles = current["titles"]
        assert isinstance(titles, list)
        for title in row.get("titles") or []:
            text = str(title).strip()
            if text and text not in titles:
                titles.append(text)
        status = str(row.get("status") or "").strip()
        if status and not current["status"]:
            current["status"] = status


def write_export_csv(
    path: Path,
    parsed: list[dict[str, str]],
    cards: dict[str, dict[str, object]],
) -> None:
    """Write an exporter-shaped CSV from parsed orders and card titles."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for item in parsed:
            card = cards.get(item["id"]) or {}
            titles = card.get("titles") or [""]
            status = str(card.get("status") or "")
            if not isinstance(titles, list) or not titles:
                titles = [""]
            for title in titles:
                writer.writerow(
                    {
                        "Order ID": item["id"],
                        "Order Date": item["date"],
                        "Total Amount": item["amount"],
                        "Currency": item["currency"],
                        "Total Savings": "",
                        "Status": status,
                        "Item Title": title,
                    }
                )


def _needs_signin(url: str) -> bool:
    return any(token in url for token in ("/ap/signin", "/ap/mfa", "/ap/cvf"))


def _firefox_prefs(download_dir: Path) -> dict[str, object]:
    return {
        "xpinstall.signatures.required": False,
        "extensions.autoDisableScopes": 0,
        "extensions.enabledScopes": 5,
        "browser.download.folderList": 2,
        "browser.download.dir": str(download_dir),
        "browser.download.useDownloadDir": True,
        "browser.download.manager.showWhenStarting": False,
        "browser.shell.checkDefaultBrowser": False,
        "browser.aboutwelcome.enabled": False,
        "datareporting.policy.dataSubmissionEnabled": False,
    }


def _launch(headless: bool, download_dir: Path):
    """Open the dedicated profile. Imported here so unit tests skip Playwright."""
    from playwright.sync_api import sync_playwright

    playwright = sync_playwright().start()
    try:
        context = playwright.firefox.launch_persistent_context(
            str(PROFILE_DIR),
            headless=headless,
            accept_downloads=True,
            downloads_path=str(download_dir),
            firefox_user_prefs=_firefox_prefs(download_dir),
            no_viewport=True,
        )
    except Exception:
        playwright.stop()
        raise
    return playwright, context


def _signin_error() -> RuntimeError:
    return RuntimeError(
        "Amazon asked to sign in. Log in with Firefox on this machine and retry."
    )


def _arm_export(page, start: date, end: date) -> None:
    """Store the exporter's resume state, then open that year's order history."""
    years = [str(year) for year in range(start.year, end.year + 1)]
    page.evaluate(
        """({ start, end, years, base }) => {
          sessionStorage.setItem("amazonExporter", JSON.stringify({
            inProgress: true,
            format: "csv",
            startDate: start,
            endDate: end,
            exportAll: false,
            yearsToProcess: years,
            currentYearIndex: 0,
            currentStartIndex: 0,
            collectedOrders: [],
            seenOrderIds: [],
            baseUrl: base,
          }));
        }""",
        {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "years": years,
            "base": ORDER_URL,
        },
    )


def _snapshot_cards(page, cards: dict[str, dict[str, object]]) -> None:
    try:
        rows = page.evaluate(CARD_JS)
    except Exception:
        return
    if isinstance(rows, list):
        merge_cards(cards, rows)


def export_amazon_csv(start: date, end: date, *, headless: bool = True) -> Path:
    """Run the exporter for ``start``..``end`` and return the CSV path."""
    download_dir = DOWNLOAD_DIR
    prepare_profile(download_dir)
    parsed: list[dict[str, str]] = []
    seen: set[str] = set()
    cards: dict[str, dict[str, object]] = {}
    state = {"started": False, "complete": False}
    playwright, context = _launch(headless, download_dir)
    try:
        context.add_cookies(amazon_cookies())
        page = context.pages[0] if context.pages else context.new_page()

        def on_console(message) -> None:
            text = message.text or ""
            if "Amazon Exporter" in text:
                state["started"] = True
            if "Export complete" in text:
                state["complete"] = True
            item = parse_parsed_order_line(text)
            if item and item["id"] not in seen:
                seen.add(item["id"])
                parsed.append(item)

        page.on("console", on_console)
        page.goto(ORDER_URL, wait_until="domcontentloaded", timeout=60_000)
        if _needs_signin(page.url):
            raise _signin_error()
        _arm_export(page, start, end)
        try:
            page.goto(
                f"{ORDER_URL}?timeFilter=year-{start.year}",
                wait_until="domcontentloaded",
                timeout=60_000,
            )
        except Exception:
            # The exporter navigates on load, which aborts our own navigation.
            if _needs_signin(page.url):
                raise _signin_error() from None
        print("Amazon exporter is running.")
        deadline = time.time() + EXPORT_TIMEOUT_S
        armed_at = time.time()
        while time.time() < deadline:
            if _needs_signin(page.url):
                raise _signin_error()
            _snapshot_cards(page, cards)
            if state["complete"]:
                time.sleep(1)
                _snapshot_cards(page, cards)
                break
            if not state["started"] and time.time() - armed_at > 45:
                raise RuntimeError(
                    "Amazon exporter did not start. Is the extension still installed in Firefox?"
                )
            page.wait_for_timeout(1000)
        else:
            raise RuntimeError("Amazon exporter did not finish within 20 minutes.")
        path = download_dir / f"amazon-orders-{date.today().isoformat()}.csv"
        write_export_csv(path, parsed, cards)
        print(f"Exporter parsed {len(parsed)} order(s).")
        return path
    finally:
        context.close()
        playwright.stop()


def check_setup(*, headless: bool = True) -> str:
    """Confirm Amazon is signed in and the exporter content script runs."""
    prepare_profile(DOWNLOAD_DIR)
    seen: list[str] = []
    playwright, context = _launch(headless, DOWNLOAD_DIR)
    try:
        context.add_cookies(amazon_cookies())
        page = context.pages[0] if context.pages else context.new_page()
        page.on(
            "console",
            lambda message: seen.append(message.text or ""),
        )
        page.goto(ORDER_URL, wait_until="domcontentloaded", timeout=60_000)
        if _needs_signin(page.url):
            raise _signin_error()
        page.wait_for_timeout(8000)
        if not any("Amazon Exporter" in text for text in seen):
            raise RuntimeError("Amazon exporter content script did not run.")
        return "exporter-running amazon-signed-in"
    finally:
        context.close()
        playwright.stop()
