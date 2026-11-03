"""
Rule-based screening engine. Weights and thresholds live in CONFIG so you can
tune/backtest them without touching logic.
"""
from .models import IPO, Snapshot

CONFIG = {
    "weights": {"growth": 30, "debt": 20, "valuation": 25, "subscription": 25},
    "growth":  {"good": 25.0, "ok": 10.0},       # revenue growth %
    "debt":    {"good": 0.5, "ok": 1.5},         # debt/equity, lower is better
    "valuation": {"good": 0.9, "ok": 1.2},       # IPO PE / sector PE, lower is better
    "subscription": {"good": 30.0, "ok": 5.0},   # total subscription (x)
    "verdicts": {"apply": 70, "neutral": 45},
}

def _higher_better(v, good, ok):
    if v is None: return None
    return 1.0 if v >= good else 0.5 if v >= ok else 0.0

def _lower_better(v, good, ok):
    if v is None: return None
    return 1.0 if v <= good else 0.5 if v <= ok else 0.0

def score_ipo(ipo: IPO, latest: Snapshot | None) -> tuple[float, str, dict]:
    c = CONFIG
    val_ratio = (ipo.pe_ratio / ipo.sector_pe) if ipo.pe_ratio and ipo.sector_pe else None
    parts = {
        "growth": _higher_better(ipo.revenue_growth_pct, **c["growth"]),
        "debt": _lower_better(ipo.debt_to_equity, **c["debt"]),
        "valuation": _lower_better(val_ratio, **c["valuation"]),
        "subscription": _higher_better(latest.sub_total if latest else None, **c["subscription"]),
    }
    # re-normalise over the metrics we actually have
    avail = {k: v for k, v in parts.items() if v is not None}
    if not avail:
        return 0.0, "insufficient-data", parts
    total_w = sum(c["weights"][k] for k in avail)
    score = 100 * sum(c["weights"][k] * v for k, v in avail.items()) / total_w
    verdict = "apply" if score >= c["verdicts"]["apply"] else \
              "neutral" if score >= c["verdicts"]["neutral"] else "avoid"
    return round(score, 1), verdict, parts
