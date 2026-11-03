from contextlib import asynccontextmanager
from datetime import date
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import Base, engine, get_session
from .models import IPO, Snapshot, Watch
from .scheduler import build_scheduler
from . import jobs
from .scrapers.ipo import fetch_ipo

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    sch = build_scheduler()
    sch.start()
    yield
    sch.shutdown()

app = FastAPI(title="IPO Automation & Analysis Platform", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"],
                   allow_methods=["*"], allow_headers=["*"])

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")

def _dto(i: IPO):
    latest = max(i.snapshots, key=lambda x: x.ts, default=None)
    return {
        "id": i.id, "name": i.name, "open": i.open_date, "close": i.close_date,
        "listing": i.listing_date, "issue_size_cr": i.issue_size_cr,
        "price_band_high": i.price_band_high, "score": i.score, "verdict": i.verdict,
        "gmp": latest.gmp if latest else None,
        "subscription": latest.sub_total if latest else None,
    }

# ---------- ONE-STEP: give the IPO name + GMP, everything else is fetched ----------
class AnalyzeIn(BaseModel):
    name: str                       # e.g. "Chiraharit"
    gmp: float | None = None        # optional: GMP in rupees. Leave empty to fetch it automatically
    url: str | None = None          # optional: paste the Chittorgarh IPO page URL if name lookup fails

FIELDS = ["open_date", "close_date", "listing_date", "issue_size_cr", "price_band_high", "lot_size",
          "revenue_growth_pct", "debt_to_equity", "pe_ratio", "sector_pe"]

@app.post("/analyze")
def analyze(body: AnalyzeIn, s: Session = Depends(get_session)):
    try:
        data = fetch_ipo(name=body.name, url=body.url)
    except LookupError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(502, f"Could not fetch IPO data: {e}")

    ipo = s.scalar(select(IPO).where(IPO.name == body.name))
    if ipo is None:
        ipo = IPO(name=body.name); s.add(ipo)
    for f in FIELDS:
        if data.get(f) is not None:
            setattr(ipo, f, data[f])
    s.flush()
    gmp = body.gmp if body.gmp is not None else data.get("gmp")
    if gmp is not None or data.get("sub_total") is not None:
        s.add(Snapshot(ipo_id=ipo.id, gmp=gmp, sub_total=data.get("sub_total")))
    s.commit()
    jobs.rescore_all()
    s.refresh(ipo)

    gmp_pct = round(100 * gmp / ipo.price_band_high, 1) if (gmp is not None and ipo.price_band_high) else None
    missing = [f for f in FIELDS + ["sub_total"] if f not in data]
    if gmp is None:
        missing.append("gmp (not found online; add it in the request as \"gmp\")")
    return {
        **_dto(ipo),
        "gmp_pct": gmp_pct,
        "gmp_used": gmp,
        "fetched": {f: data[f] for f in FIELDS + ["sub_total", "sector_name", "gmp"] if f in data},
        "missing": missing,
        "source": data.get("source_url"),
        "gmp_source": data.get("gmp_url"),
    }

# ---------- Add IPOs by hand (optional) ----------
class IPOIn(BaseModel):
    name: str
    open_date: date | None = None
    close_date: date | None = None
    price_band_high: float | None = None
    issue_size_cr: float | None = None
    revenue_growth_pct: float | None = None
    debt_to_equity: float | None = None
    pe_ratio: float | None = None
    sector_pe: float | None = None

@app.post("/ipos")
def add_ipo(body: IPOIn, s: Session = Depends(get_session)):
    if s.scalar(select(IPO).where(IPO.name == body.name)):
        raise HTTPException(400, "An IPO with this name already exists")
    ipo = IPO(**body.model_dump())
    s.add(ipo); s.commit()
    jobs.rescore_all()
    return {"id": ipo.id, "name": ipo.name}

class SnapIn(BaseModel):
    gmp: float | None = None
    sub_total: float | None = None
    sub_qib: float | None = None
    sub_nii: float | None = None
    sub_retail: float | None = None

@app.post("/ipos/{ipo_id}/snapshot")
def add_snapshot(ipo_id: int, body: SnapIn, s: Session = Depends(get_session)):
    if not s.get(IPO, ipo_id):
        raise HTTPException(404, "IPO not found")
    s.add(Snapshot(ipo_id=ipo_id, **body.model_dump())); s.commit()
    jobs.rescore_all()
    return {"ok": True}

# ---------- View results ----------
@app.get("/ipos")
def list_ipos(s: Session = Depends(get_session)):
    return [_dto(i) for i in s.scalars(select(IPO).order_by(IPO.id))]

@app.get("/ipos/{ipo_id}/history")
def history(ipo_id: int, s: Session = Depends(get_session)):
    ipo = s.get(IPO, ipo_id)
    if not ipo: raise HTTPException(404)
    return [{"ts": x.ts, "gmp": x.gmp, "sub_total": x.sub_total,
             "qib": x.sub_qib, "nii": x.sub_nii, "retail": x.sub_retail}
            for x in sorted(ipo.snapshots, key=lambda x: x.ts)]

@app.get("/compare")
def compare(ids: list[int] = Query(...), s: Session = Depends(get_session)):
    return [_dto(i) for i in s.scalars(select(IPO).where(IPO.id.in_(ids)))]

# ---------- Alerts ----------
class WatchIn(BaseModel):
    ipo_id: int
    metric: str          # gmp_pct | sub_total | sub_retail | score
    op: str              # > >= < <=
    value: float
    channel: str = "telegram"   # telegram | email | both

@app.post("/watchlist")
def add_watch(w: WatchIn, s: Session = Depends(get_session)):
    row = Watch(ipo_id=w.ipo_id, rule={"metric": w.metric, "op": w.op, "value": w.value}, channel=w.channel)
    s.add(row); s.commit()
    return {"id": row.id}

@app.post("/admin/run/{job}")
def run_job(job: str):
    fn = {"list": jobs.refresh_ipo_list, "snap": jobs.snapshot_open_ipos,
          "score": jobs.rescore_all, "watch": jobs.evaluate_watchlist}.get(job)
    if not fn: raise HTTPException(404)
    fn()
    return {"ok": True}