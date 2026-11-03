from datetime import datetime, date, timedelta
from sqlalchemy import select
from .db import SessionLocal
from .models import IPO, Snapshot, Watch
from .scrapers.ipo_sources import scrape_ipo_list, scrape_gmp_and_subscription
from .screener import score_ipo
from .alerts import notify
import operator

OPS = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le}

def refresh_ipo_list():
    with SessionLocal() as s:
        for row in scrape_ipo_list():
            ipo = s.scalar(select(IPO).where(IPO.name == row["name"]))
            if ipo is None:
                s.add(IPO(**row))
            else:
                for k, v in row.items():
                    if v is not None:
                        setattr(ipo, k, v)
        s.commit()

def snapshot_open_ipos():
    today = date.today()
    with SessionLocal() as s:
        live = {i.name: i for i in s.scalars(
            select(IPO).where(IPO.open_date <= today, IPO.close_date >= today))}
        for row in scrape_gmp_and_subscription():
            ipo = live.get(row["name"])
            if ipo:
                s.add(Snapshot(ipo_id=ipo.id, **{k: v for k, v in row.items() if k != "name"}))
        s.commit()

def rescore_all():
    with SessionLocal() as s:
        for ipo in s.scalars(select(IPO)):
            latest = max(ipo.snapshots, key=lambda x: x.ts, default=None)
            ipo.score, ipo.verdict, _ = score_ipo(ipo, latest)
        s.commit()

def _metric(ipo: IPO, snap: Snapshot | None, name: str):
    if name == "score": return ipo.score
    if snap is None: return None
    if name == "gmp_pct" and snap.gmp is not None and ipo.price_band_high:
        return 100 * snap.gmp / ipo.price_band_high
    return getattr(snap, name, None)

def evaluate_watchlist():
    with SessionLocal() as s:
        for w in s.scalars(select(Watch)):
            if w.last_triggered and datetime.utcnow() - w.last_triggered < timedelta(hours=6):
                continue  # cooldown to avoid spam
            ipo = s.get(IPO, w.ipo_id)
            snap = max(ipo.snapshots, key=lambda x: x.ts, default=None)
            val = _metric(ipo, snap, w.rule["metric"])
            if val is not None and OPS[w.rule["op"]](val, w.rule["value"]):
                notify(w.channel, f"IPO alert: {ipo.name}",
                       f"{w.rule['metric']} = {val:.1f} ({w.rule['op']} {w.rule['value']})\nScore: {ipo.score} ({ipo.verdict})")
                w.last_triggered = datetime.utcnow()
        s.commit()
