"""
Source adapters. Each returns plain dicts so the DB layer stays decoupled.
The column names below are PLACEHOLDERS: open your chosen source, inspect the table,
and adjust the mapping. Check robots.txt / terms before scraping, and prefer
official sources (NSE/BSE/SEBI) for anything you can get there.
"""
import pandas as pd
from io import StringIO
from datetime import datetime
from .base import fetch_html, to_float
from ..config import IPO_LIST_URL, GMP_URL

def _date(s):
    for fmt in ("%b %d, %Y", "%d %b %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(s).strip(), fmt).date()
        except ValueError:
            continue
    return None

def scrape_ipo_list() -> list[dict]:
    if not IPO_LIST_URL:
        return []
    tables = pd.read_html(StringIO(fetch_html(IPO_LIST_URL)))
    df = tables[0]
    out = []
    for _, r in df.iterrows():
        out.append({
            "name": str(r.get("Issuer Company", r.get("Company", ""))).strip(),
            "open_date": _date(r.get("Open")),
            "close_date": _date(r.get("Close")),
            "listing_date": _date(r.get("Listing Date")),
            "issue_size_cr": to_float(r.get("Issue Size (Rs Cr)")),
            "price_band_high": to_float(r.get("Issue Price (Rs)")),
        })
    return [x for x in out if x["name"]]

def scrape_gmp_and_subscription() -> list[dict]:
    """Return [{name, gmp, sub_total, sub_qib, sub_nii, sub_retail}, ...]"""
    if not GMP_URL:
        return []
    df = pd.read_html(StringIO(fetch_html(GMP_URL)))[0]
    return [{
        "name": str(r.get("IPO", "")).strip(),
        "gmp": to_float(r.get("GMP")),
        "sub_total": to_float(r.get("Subscription")),
    } for _, r in df.iterrows()]
