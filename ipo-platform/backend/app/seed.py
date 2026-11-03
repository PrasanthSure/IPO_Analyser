"""
Loads FICTIONAL demo IPOs + price/subscription history so you can test
/compare, scoring and alerts before real scrapers are wired up.
Run from the backend folder:   python -m app.seed
"""
from datetime import date, timedelta, datetime
from sqlalchemy import select
from .db import Base, engine, SessionLocal
from .models import IPO, Snapshot, Watch
from .jobs import rescore_all

today = date.today()

# name, growth%, D/E, IPO PE, sector PE, size(Cr), price, lot, final sub(x), final GMP(Rs), open offset(days)
DEMO = [
    ("Demo Solar Ltd",      42.0, 0.3, 18, 24, 850, 120, 125, 62.0, 38, -1),
    ("Demo Pharma Ltd",     18.0, 0.9, 30, 28, 1200, 450, 33, 12.0, 40, -1),
    ("Demo Infra Ltd",       6.0, 2.4, 45, 30, 600, 210, 70, 2.5, -5, 0),
    ("Demo Fintech Ltd",    55.0, 1.1, 60, 40, 2000, 330, 45, 28.0, 25, -2),
    ("Demo Textiles Ltd",   11.0, 0.6, 20, 22, 400, 95, 150, 8.0, 6, -10),
]

def main():
    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        for (name, g, de, pe, spe, size, price, lot, sub, gmp, off) in DEMO:
            if s.scalar(select(IPO).where(IPO.name == name)):
                continue
            o = today + timedelta(days=off)
            ipo = IPO(name=name, open_date=o, close_date=o + timedelta(days=3),
                      listing_date=o + timedelta(days=8), issue_size_cr=size,
                      price_band_low=price - 10, price_band_high=price, lot_size=lot,
                      revenue_growth_pct=g, debt_to_equity=de, pe_ratio=pe, sector_pe=spe)
            s.add(ipo); s.flush()
            for k in range(1, 7):  # 6 snapshots, growing toward the final values
                f = k / 6
                s.add(Snapshot(
                    ipo_id=ipo.id, ts=datetime.utcnow() - timedelta(hours=(6 - k) * 4),
                    gmp=round(gmp * f, 1), sub_total=round(sub * f, 2),
                    sub_qib=round(sub * f * 1.6, 2), sub_nii=round(sub * f * 1.2, 2),
                    sub_retail=round(sub * f * 0.7, 2)))
        s.commit()

    rescore_all()

    with SessionLocal() as s:
        first = s.scalar(select(IPO).order_by(IPO.id))
        if first and not s.scalar(select(Watch).where(Watch.ipo_id == first.id)):
            s.add(Watch(ipo_id=first.id, rule={"metric": "gmp_pct", "op": ">", "value": 5},
                        channel="telegram"))
            s.commit()
        for i in s.scalars(select(IPO).order_by(IPO.id)):
            print(f"id={i.id}  {i.name:<20} score={i.score}  verdict={i.verdict}")
    print("\nDone. Open http://127.0.0.1:8000/docs and try GET /ipos and GET /compare")

if __name__ == "__main__":
    main()
