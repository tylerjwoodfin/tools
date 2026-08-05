#!/usr/bin/env python3
"""Amazon order automation: natural-language search → ChatGPT pick → confirm → order."""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cabinet import Cabinet
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
from tyler_python_helpers import ChatGPT

cabinet = Cabinet()

DEFAULT_WS = "ws://127.0.0.1:9311/"
DEFAULT_STORAGE = Path.home() / ".local" / "share" / "amazon-order" / "storage_state.json"
AMAZON_SEARCH = "https://www.amazon.com/s?k={query}"
PLAYWRIGHT_VERSION = "1.61.0"


@dataclass
class ProductCandidate:
    """One Amazon search result card."""

    index: int
    title: str
    price: str
    rating: str
    url: str
    asin: str
    snippet: str = ""


def cue(message: str) -> None:
    """Print a step cue for the user."""
    print(f"→ {message}", flush=True)


def storage_state_path() -> Path:
    """Path for Playwright Amazon session cookies."""
    raw = cabinet.get("amazon", "storage_state")
    if raw:
        return Path(os.path.expanduser(str(raw)))
    return DEFAULT_STORAGE


def has_saved_session() -> bool:
    """True when a Playwright storage-state file exists."""
    return storage_state_path().is_file()


def playwright_ws_endpoint() -> str | None:
    """WebSocket URL for a remote Playwright server, if configured or reachable."""
    env = os.environ.get("PLAYWRIGHT_WS_ENDPOINT", "").strip()
    if env:
        return env
    configured = cabinet.get("amazon", "playwright_ws")
    if configured:
        return str(configured).strip()
    host, port = "127.0.0.1", 9311
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return DEFAULT_WS
    except OSError:
        return None


def want_headless() -> bool:
    """Whether local Chromium should run headless."""
    raw = cabinet.get("amazon", "headless")
    if raw is None:
        return False
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def confirm(prompt: str, *, default_no: bool = True) -> bool:
    """Ask for y/n confirmation on stdin."""
    suffix = " [y/N] " if default_no else " [Y/n] "
    try:
        answer = input(f"? {prompt}{suffix}").strip().lower()
    except EOFError:
        return False
    if not answer:
        return not default_no
    return answer in {"y", "yes"}


def extract_asin(url: str) -> str:
    """Pull ASIN from a product URL if present."""
    match = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", url)
    return match.group(1) if match else ""


def _coerce_pick_index(value: Any, count: int) -> int | None:
    """Turn a numeric pick into a valid 0-based index, or None."""
    try:
        idx = int(value)
    except (TypeError, ValueError):
        return None
    if idx < 0:
        return None
    return idx if 0 <= idx < count else None


def parse_pick_response(raw: str, count: int) -> int | None:
    """
    Parse ChatGPT's pick: JSON {\"index\": N} or a bare integer.
    Returns 0-based index, or None if no reasonable match.
    """
    text = raw.strip()
    candidates = [text]
    fenced = re.search(r"```(?:json)?\s*(\{.*?\}|\-?\d+)\s*```", text, re.DOTALL)
    if fenced:
        candidates.insert(0, fenced.group(1).strip())
    obj = re.search(r"\{[^{}]*\"index\"[^{}]*\}", text)
    if obj:
        candidates.insert(0, obj.group(0))

    for chunk in candidates:
        try:
            data = json.loads(chunk)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if isinstance(data, dict) and "index" in data:
            return _coerce_pick_index(data["index"], count)
        if isinstance(data, int):
            return _coerce_pick_index(data, count)

    match = re.search(r"-?\d+", text)
    if not match:
        return None
    return _coerce_pick_index(match.group(0), count)


def pick_product_with_chatgpt(description: str, candidates: list[ProductCandidate]) -> int | None:
    """Ask ChatGPT which candidate best matches the everyday-language description."""
    payload = [
        {
            "index": c.index,
            "title": c.title,
            "price": c.price,
            "rating": c.rating,
            "asin": c.asin,
            "snippet": c.snippet,
        }
        for c in candidates
    ]
    prompt = f"""You help pick an Amazon product from search results.

User request (everyday language): {description!r}

Candidates (JSON):
{json.dumps(payload, indent=2)}

Pick the single best match that a reasonable shopper would buy for that request.
Use title and snippet together (titles are sometimes just a brand name).
Prefer correctly matching flavor/variant/size when stated, then rating and price.
If nothing is a reasonable match, return index -1.

Respond with ONLY a JSON object like: {{"index": 0}}
No markdown, no explanation."""
    cue("Asking ChatGPT to pick the best match…")
    response = ChatGPT().query(prompt)
    cue(f"ChatGPT replied: {response}")
    return parse_pick_response(response, len(candidates))


def scrape_search_results(page: Page, limit: int = 8) -> list[ProductCandidate]:
    """Collect top search result cards from the current Amazon results page."""
    page.wait_for_selector('[data-component-type="s-search-result"]', timeout=20000)
    cards = page.query_selector_all('[data-component-type="s-search-result"]')
    results: list[ProductCandidate] = []
    for card in cards:
        if len(results) >= limit:
            break
        asin = (card.get_attribute("data-asin") or "").strip()
        if not asin:
            continue

        img = card.query_selector("img.s-image")
        title = (img.get_attribute("alt") or "").strip() if img else ""
        if not title or len(title) < 8:
            link_el = card.query_selector("h2 a")
            if link_el:
                title = (link_el.get_attribute("aria-label") or "").strip()
            if not title:
                title_el = (
                    card.query_selector("h2 a span.a-text-normal")
                    or card.query_selector("a.a-link-normal span.a-text-normal")
                    or card.query_selector("h2 span")
                )
                title = (title_el.inner_text().strip() if title_el else "").strip()
        title = re.sub(r"\s*sponsored\s*$", "", title, flags=re.I).strip()
        title = title.rstrip(".").strip()
        if title.endswith("..."):
            # Prefer fuller text from the card body when alt is truncated
            try:
                body = " ".join(card.inner_text().split())
            except Exception:  # pylint: disable=broad-exception-caught
                body = ""
            # First long-ish segment often is the product name
            for part in re.split(r"\s{2,}|\n", body):
                part = part.strip()
                if len(part) > len(title) and "out of 5" not in part.lower():
                    title = part[:300]
                    break
            else:
                if body:
                    # Strip leading badges like "Overall Pick"
                    cleaned = re.sub(
                        r"^(Overall Pick|Best Seller|Amazon's Choice)\s+",
                        "",
                        body,
                        flags=re.I,
                    )
                    title = cleaned[:220].strip()
        if not title:
            continue

        price_el = card.query_selector("span.a-price span.a-offscreen")
        price = (price_el.inner_text().strip() if price_el else "n/a").strip()
        rating_el = card.query_selector("span.a-icon-alt")
        rating = (rating_el.inner_text().strip() if rating_el else "n/a").strip()

        link_el = (
            card.query_selector(f'a[href*="/dp/{asin}"]')
            or card.query_selector('a[href*="/dp/"]')
            or card.query_selector("h2 a")
        )
        href = link_el.get_attribute("href") if link_el else ""
        url = urllib.parse.urljoin("https://www.amazon.com", href or f"/dp/{asin}")

        try:
            snippet = " ".join(card.inner_text().split())[:400]
        except Exception:  # pylint: disable=broad-exception-caught
            snippet = ""

        results.append(
            ProductCandidate(
                index=len(results),
                title=title[:300],
                price=price,
                rating=rating,
                url=url,
                asin=asin,
                snippet=snippet,
            )
        )
    return results


def open_context(browser: Browser, *, headed_hint: bool) -> BrowserContext:
    """Create a browser context, loading saved Amazon auth when available."""
    path = storage_state_path()
    kwargs: dict[str, Any] = {
        "viewport": {"width": 1280, "height": 900},
        "locale": "en-US",
        "user_agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
    }
    if path.is_file():
        kwargs["storage_state"] = str(path)
        cue(f"Loaded session from {path}")
    elif headed_hint:
        cue("No saved session yet — you may need to sign in (amazon --login).")
    return browser.new_context(**kwargs)


def save_storage(context: BrowserContext) -> Path:
    """Persist cookies/local storage for later runs."""
    path = storage_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(path))
    cue(f"Saved session to {path}")
    return path


def connect_or_launch(playwright: Any, *, force_local: bool = False) -> tuple[Browser, str]:
    """
    Prefer Docker/remote Playwright server; otherwise launch local Chromium.
    Returns (browser, mode) where mode is 'remote' or 'local'.
    """
    if not force_local:
        ws = playwright_ws_endpoint()
        if ws:
            cue(f"Connecting to Playwright server at {ws}")
            browser = playwright.chromium.connect(ws)
            return browser, "remote"
    cue("Launching local Chromium")
    browser = playwright.chromium.launch(headless=False if force_local else want_headless())
    return browser, "local"


def run_login() -> int:
    """Open Amazon in local headed Chromium so the user can sign in; save storage state."""
    print(
        "\nPlaywright does not use your Firefox cookies.\n"
        "A separate Chromium window will open — sign in there once.\n"
        f"Session will be saved to {storage_state_path()}.\n"
    )
    with sync_playwright() as playwright:
        # Always local + headed so 2FA is possible (Docker server is headless).
        browser, _mode = connect_or_launch(playwright, force_local=True)
        try:
            context = open_context(browser, headed_hint=True)
            page = context.new_page()
            cue("Opening Amazon sign-in…")
            page.goto("https://www.amazon.com/", wait_until="domcontentloaded")
            page.wait_for_timeout(1000)
            sign_in = page.query_selector("#nav-link-accountList") or page.query_selector(
                "a[href*='/ap/signin']"
            )
            if sign_in:
                sign_in.click()
            else:
                page.goto(
                    "https://www.amazon.com/ap/signin",
                    wait_until="domcontentloaded",
                )
            print(
                "\nSign in to Amazon in the Chromium window (complete 2FA if prompted).\n"
                "When you see your name / Account & Lists in the header, return here.\n"
            )
            if not confirm("Save this browser session now?", default_no=False):
                cue("Aborted — session not saved.")
                return 1
            save_storage(context)
            context.close()
        finally:
            browser.close()
    return 0


def diagnose_missing_buybox(page: Page) -> str:
    """Explain why Add to Cart / Buy Now might be missing."""
    url = page.url
    try:
        body = page.inner_text("body")[:4000].lower()
    except Exception:  # pylint: disable=broad-exception-caught
        body = ""
    if "robot" in body or "captcha" in body or "validatecaptcha" in url.lower():
        return "Amazon showed a captcha/robot check — try amazon --login, then retry."
    if "sign in" in body and ("password" in body or "email" in body):
        return "Amazon is asking you to sign in — run: amazon --login"
    if page.query_selector("#buybox-see-all-buying-options-announce") or page.query_selector(
        "a[href*='offer-listing']"
    ):
        return "This listing has no 1-click buy box (see all buying options)."
    if not has_saved_session():
        return (
            "No Playwright session saved. Firefox login does not count — "
            "run: amazon --login"
        )
    return "Buy box not found (page layout/captcha?). Try amazon --login and retry."


def dismiss_noise(page: Page) -> None:
    """Best-effort dismiss common Amazon interstitial popups."""
    selectors = [
        "#sp-cc-accept",
        "input#sp-cc-accept",
        "#attach-close_sideSheet-link",
        "#attachSiNoCoverage-announce",
        "button[data-action='a-popover-close']",
    ]
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click(timeout=1000)
        except Exception:  # pylint: disable=broad-exception-caught
            continue


def add_to_cart_and_checkout(page: Page, product: ProductCandidate, *, dry_run: bool) -> int:
    """Open product page, add to cart, checkout, optionally place order."""
    cue(f"Opening product: {product.title}")
    page.goto(f"https://www.amazon.com/dp/{product.asin}", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    dismiss_noise(page)

    add = None
    buy_now = None
    try:
        page.wait_for_selector(
            "#add-to-cart-button, input#add-to-cart-button, "
            "#buy-now-button, input#buy-now-button",
            timeout=8000,
        )
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    add = page.query_selector("#add-to-cart-button") or page.query_selector(
        "input#add-to-cart-button"
    )
    buy_now = page.query_selector("#buy-now-button") or page.query_selector(
        "input#buy-now-button"
    )

    if dry_run:
        if not add and not buy_now:
            cue(f"Dry run note: {diagnose_missing_buybox(page)}")
        else:
            cue("Dry run — buy box visible; stopping before cart/checkout.")
        return 0

    if buy_now and buy_now.is_enabled():
        cue("Clicking Buy Now…")
        buy_now.click()
    elif add:
        cue("Adding to cart…")
        add.click()
        page.wait_for_timeout(2000)
        dismiss_noise(page)
        cue("Going to cart…")
        page.goto("https://www.amazon.com/gp/cart/view.html", wait_until="domcontentloaded")
        checkout = page.query_selector(
            "input[name='proceedToRetailCheckout']"
        ) or page.query_selector("#sc-buy-box-ptc-button input")
        if not checkout:
            cue("Could not find Proceed to checkout.")
            return 1
        cue("Proceeding to checkout…")
        checkout.click()
    else:
        cue(diagnose_missing_buybox(page))
        return 1

    page.wait_for_timeout(2500)
    dismiss_noise(page)

    # Skip optional upsells / continue buttons when present
    for _ in range(4):
        cont = page.query_selector(
            "input[name='placeYourOrder1']"
        ) or page.query_selector("#submitOrderButtonId")
        if cont:
            break
        skip = (
            page.query_selector("input[name='continue-bottom']")
            or page.query_selector("#prime-interstitial-nothanks-button")
            or page.query_selector("a#prime-no-thanks")
            or page.query_selector("input.a-button-input[type='submit']")
        )
        if skip and skip.is_visible():
            try:
                label = skip.get_attribute("aria-labelledby") or ""
                cue(f"Clicking continue/skip control ({label or 'submit'})…")
                skip.click(timeout=2000)
                page.wait_for_timeout(1500)
            except Exception:  # pylint: disable=broad-exception-caught
                break
        else:
            break

    place = page.query_selector("input[name='placeYourOrder1']") or page.query_selector(
        "#submitOrderButtonId"
    )
    if not place:
        cue(
            "Could not find Place your order. Finish in the browser if checkout "
            "needs address/payment confirmation."
        )
        if not confirm("Keep the browser open until you finish manually?", default_no=False):
            return 1
        input("Press Enter when done… ")
        save_storage(page.context)
        return 0

    cue("Ready to place the order.")
    if not confirm(
        f"Place order for {product.title!r} ({product.price})?",
        default_no=True,
    ):
        cue("Order cancelled.")
        return 1

    cue("Placing order…")
    place.click()
    page.wait_for_timeout(4000)
    save_storage(page.context)

    body = page.inner_text("body")
    order_match = re.search(r"order\s*(?:number|#)?\s*[:\s]*([0-9]{3}-[0-9]{7}-[0-9]{7})", body, re.I)
    if order_match:
        cue(f"Order placed — {order_match.group(1)}")
    elif re.search(r"thank you|order placed|thanks for your order", body, re.I):
        cue("Order placed (confirmation page detected).")
    else:
        cue("Place-order clicked — verify confirmation in the browser.")
    return 0


def run_order(description: str, *, dry_run: bool, auto_yes: bool) -> int:
    """Search → pick → confirm → order."""
    if not description.strip():
        print("Usage: amazon <product description>", file=sys.stderr)
        return 2

    if not dry_run and not has_saved_session():
        cue(
            "No Playwright Amazon session yet. Your Firefox login is separate — "
            "Playwright uses its own Chromium cookies."
        )
        cue("Run once: amazon --login")
        return 1

    with sync_playwright() as playwright:
        browser, _mode = connect_or_launch(playwright)
        try:
            context = open_context(browser, headed_hint=True)
            page = context.new_page()
            query = description.strip()
            url = AMAZON_SEARCH.format(query=urllib.parse.quote_plus(query))
            cue(f"Searching Amazon for {query!r}…")
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            dismiss_noise(page)

            candidates = scrape_search_results(page)
            if not candidates:
                cue("No search results found.")
                return 1

            cue(f"Found {len(candidates)} candidates:")
            for c in candidates:
                print(f"  [{c.index}] {c.title} — {c.price} — {c.rating}")

            pick = pick_product_with_chatgpt(query, candidates)
            if pick is None:
                cue("ChatGPT found no reasonable match. Aborting.")
                return 1

            product = candidates[pick]
            cue(f"Selected [{product.index}] {product.title} ({product.price})")
            if not auto_yes and not confirm("Order this product?", default_no=False):
                cue("Aborted.")
                return 1

            code = add_to_cart_and_checkout(page, product, dry_run=dry_run)
            context.close()
            return code
        finally:
            browser.close()


def build_parser() -> argparse.ArgumentParser:
    """CLI parser."""
    parser = argparse.ArgumentParser(
        prog="amazon",
        description=(
            "Describe a product; Playwright + ChatGPT pick a match and place "
            "an Amazon order after confirmation."
        ),
    )
    parser.add_argument(
        "description",
        nargs="*",
        help="Everyday-language product description (e.g. strawberry flavored huel)",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Open Amazon sign-in and save session cookies",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Search and select only; do not add to cart or place order",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip product confirmation (still confirms place-order)",
    )
    parser.add_argument(
        "--version-check",
        action="store_true",
        help="Print expected Playwright version and exit",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version_check:
        print(PLAYWRIGHT_VERSION)
        return 0
    if args.login:
        return run_login()
    description = " ".join(args.description).strip()
    if not description:
        parser.print_help()
        return 2
    return run_order(description, dry_run=args.dry_run, auto_yes=args.yes)


if __name__ == "__main__":
    sys.exit(main())
