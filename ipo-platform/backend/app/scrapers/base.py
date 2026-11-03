import httpx
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (research project; contact: you@example.com)"}

def fetch_html(url: str, timeout: int = 20) -> str:
    r = httpx.get(url, headers=HEADERS, timeout=timeout, follow_redirects=True)
    r.raise_for_status()
    return r.text

def fetch_html_js(url: str, wait_selector: str | None = None) -> str:
    """Playwright fallback for JS-rendered pages. Run `playwright install chromium` once."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=HEADERS["User-Agent"])
        page.goto(url, wait_until="networkidle")
        if wait_selector:
            page.wait_for_selector(wait_selector, timeout=15000)
        html = page.content()
        browser.close()
    return html

def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")

def to_float(text) -> float | None:
    if text is None:
        return None
    t = str(text).replace(",", "").replace("₹", "").replace("%", "").replace("x", "").strip()
    try:
        return float(t)
    except ValueError:
        return None
