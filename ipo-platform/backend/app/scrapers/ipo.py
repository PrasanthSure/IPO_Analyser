"""
Fetches everything about an IPO from its Chittorgarh detail page, so you only need
to supply the IPO name (or page URL) and the GMP.

Pulled automatically: dates, price, lot size, issue size, total subscription,
revenue growth (Total Income, latest vs previous year), debt/equity, P/E and a
sector P/E (median P/E of recently listed IPOs in the same sector, shown on the page).

Use sparingly (one request per IPO, results are stored) and check the site's terms.
"""
import re
import statistics
from datetime import datetime
from difflib import SequenceMatcher
from bs4 import BeautifulSoup
from .base import fetch_html, fetch_html_js, to_float

BASE = "https://www.chittorgarh.com"
LIST_PAGES = [
    f"{BASE}/report/ipo-in-india-list-main-board-sme/82/mainboard/",
    f"{BASE}/report/ipo-in-india-list-main-board-sme/82/sme/",
]
IPO_HREF = re.compile(r"/ipo/([a-z0-9\-]+)/(\d+)/?$")


def _norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\b(ltd|limited|ipo|pvt|private|india)\b\.?", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def find_ipo_url(name: str) -> str | None:
    """Look the IPO up on Chittorgarh's list pages and return its detail-page URL."""
    target = _norm(name)
    best, best_score = None, 0.0
    for page in LIST_PAGES:
        try:
            html = fetch_html(page)
            links = BeautifulSoup(html, "lxml").find_all("a", href=IPO_HREF)
            if not links:  # list is JS-rendered -> use the browser
                html = fetch_html_js(page)
                links = BeautifulSoup(html, "lxml").find_all("a", href=IPO_HREF)
        except Exception:
            continue
        for a in links:
            cand = _norm(a.get_text(" ")) or _norm(IPO_HREF.search(a["href"]).group(1))
            if not cand:
                continue
            score = SequenceMatcher(None, target, cand).ratio()
            if target and (target in cand or cand in target):
                score = max(score, 0.9)
            if score > best_score:
                best_score, best = score, a["href"]
    if best and best_score >= 0.75:
        return best if best.startswith("http") else BASE + best
    return None


# ---------- small parsing helpers ----------
def _cells(row):
    return [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]

def _find_table(soup, header_contains: str):
    for t in soup.find_all("table"):
        first = t.find("tr")
        if first and header_contains.lower() in " ".join(_cells(first)).lower():
            return t
    return None

def _row_values(table, label: str):
    """Return the list of cells after the label cell, for the row whose first cell starts with label."""
    if table is None:
        return None
    for tr in table.find_all("tr"):
        cells = _cells(tr)
        if cells and cells[0].lower().startswith(label.lower()):
            return cells[1:]
    return None

def _kv(soup, label: str):
    for tr in soup.find_all("tr"):
        cells = _cells(tr)
        if len(cells) >= 2 and cells[0].lower().startswith(label.lower()):
            return cells[1]
    return None

def _num(text):
    if text is None:
        return None
    m = re.findall(r"-?\d[\d,]*\.?\d*", str(text))
    return float(m[-1].replace(",", "")) if m else None

def _date_after(text: str, label: str):
    m = re.search(label + r"\s*[A-Za-z]{3},\s*([A-Za-z]{3}\s+\d{1,2},\s*\d{4})", text)
    if m:
        try:
            return datetime.strptime(re.sub(r"\s+", " ", m.group(1)), "%b %d, %Y").date()
        except ValueError:
            return None
    return None


def parse_detail(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)
    out: dict = {}

    h1 = soup.find("h1")
    if h1:
        out["page_title"] = re.sub(r"\s*IPO Details\s*$", "", h1.get_text(" ", strip=True)).strip()

    out["open_date"] = _date_after(text, r"IPO Open")
    out["close_date"] = _date_after(text, r"IPO Close")
    out["listing_date"] = _date_after(text, r"Listing")

    # price: fixed price -> "Issue Price", book built -> "Price Band" ("₹57 to ₹60" -> upper)
    price_txt = _kv(soup, "Price Band") or _kv(soup, "Issue Price")
    out["price_band_high"] = _num(price_txt)
    out["lot_size"] = int(_num(_kv(soup, "Lot Size")) or 0) or None

    size_txt = _kv(soup, "Total Issue Size") or ""
    m = re.search(r"₹\s*([\d,\.]+)\s*Cr", size_txt)
    out["issue_size_cr"] = float(m.group(1).replace(",", "")) if m else None

    # subscription (total only; category split is behind a login on the site)
    sub_table = _find_table(soup, "Subscription (times)")
    tot = _row_values(sub_table, "Total")
    out["sub_total"] = _num(tot[0]) if tot else None

    # financials -> revenue growth
    fin = _find_table(soup, "Period Ended")
    income = _row_values(fin, "Total Income")
    if income and len(income) >= 2:
        cur, prev = _num(income[0]), _num(income[1])
        if cur is not None and prev:
            out["revenue_growth_pct"] = round((cur - prev) / abs(prev) * 100, 1)

    # debt / equity: KPI table first, else borrowing / net worth
    kpi = _find_table(soup, "KPI")
    de = _row_values(kpi, "Debt/Equity")
    out["debt_to_equity"] = _num(de[0]) if de else None
    if out["debt_to_equity"] is None:
        borrow, nw = _row_values(fin, "Total Borrowing"), _row_values(fin, "NET Worth")
        if borrow and nw and _num(nw[0]):
            out["debt_to_equity"] = round(_num(borrow[0]) / _num(nw[0]), 2)

    # P/E: use post-IPO if present, else pre-IPO
    val = _find_table(soup, "Valuation Metric")
    pe = _row_values(val, "P/E")
    if pe:
        out["pe_ratio"] = _num(pe[1]) if len(pe) > 1 and _num(pe[1]) is not None else _num(pe[0])

    # sector P/E: median of the PE Ratio column in "Recently Listed IPOs in <sector>"
    for h in soup.find_all(["h2", "h3"]):
        if "Recently Listed IPOs in" in h.get_text():
            out["sector_name"] = h.get_text(" ", strip=True).replace("Recently Listed IPOs in", "").strip()
            t = h.find_next("table")
            if t:
                header = _cells(t.find("tr"))
                if "PE Ratio" in header:
                    i = header.index("PE Ratio")
                    vals = [_num(_cells(tr)[i]) for tr in t.find_all("tr")[1:] if len(_cells(tr)) > i]
                    vals = [v for v in vals if v is not None and v > 0]
                    if vals:
                        out["sector_pe"] = round(statistics.median(vals), 1)
            break
    return {k: v for k, v in out.items() if v is not None}


GMP_HREF = re.compile(r"investorgain\.com/chr-gmp/[a-z0-9\-]+/\d+")

def parse_gmp(html: str) -> float | None:
    """Reads the latest GMP (in rupees) from an InvestorGain per-IPO GMP page."""
    text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    for pat in (r"latest Grey Market Premium \(GMP\) for .{0,80}? is\s*₹\s*(-?[\d,\.]+)",
                r"last GMP of .{0,80}? was\s*₹\s*(-?[\d,\.]+)"):
        m = re.search(pat, text)
        if m:
            return float(m.group(1).replace(",", ""))
    return None


def fetch_gmp(detail_url: str, detail_html: str) -> tuple[float | None, str | None]:
    """The IPO's GMP page uses the same slug/id as its Chittorgarh page (and is linked from it)."""
    a = BeautifulSoup(detail_html, "lxml").find("a", href=GMP_HREF)
    if a:
        gmp_url = a["href"]
    else:
        m = IPO_HREF.search(detail_url.rstrip("/") + "/")
        gmp_url = f"https://www.investorgain.com/chr-gmp/{m.group(1)}/{m.group(2)}" if m else None
    if not gmp_url:
        return None, None
    try:
        return parse_gmp(fetch_html(gmp_url)), gmp_url
    except Exception:
        return None, gmp_url


def fetch_ipo(name: str | None = None, url: str | None = None) -> dict:
    url = url or (find_ipo_url(name) if name else None)
    if not url:
        raise LookupError("Could not find this IPO. Paste its Chittorgarh page URL in the 'url' field.")
    try:
        html = fetch_html(url)
    except Exception:
        html = fetch_html_js(url)
    data = parse_detail(html)
    data["source_url"] = url
    gmp, gmp_url = fetch_gmp(url, html)
    if gmp is not None:
        data["gmp"] = gmp
    if gmp_url:
        data["gmp_url"] = gmp_url
    return data
