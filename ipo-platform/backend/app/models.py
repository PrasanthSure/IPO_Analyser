from datetime import datetime, date
from sqlalchemy import String, Float, Date, DateTime, ForeignKey, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

class IPO(Base):
    __tablename__ = "ipos"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    open_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    listing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    issue_size_cr: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_band_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_band_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    lot_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # fundamentals (from RHP / aggregator)
    revenue_growth_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    debt_to_equity: Mapped[float | None] = mapped_column(Float, nullable=True)
    pe_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    sector_pe: Mapped[float | None] = mapped_column(Float, nullable=True)
    # screening output
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    verdict: Mapped[str | None] = mapped_column(String(20), nullable=True)
    snapshots: Mapped[list["Snapshot"]] = relationship(back_populates="ipo", cascade="all, delete-orphan")

class Snapshot(Base):
    """Time series of GMP + subscription, captured every few minutes while an IPO is open."""
    __tablename__ = "snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    ipo_id: Mapped[int] = mapped_column(ForeignKey("ipos.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    gmp: Mapped[float | None] = mapped_column(Float, nullable=True)
    sub_total: Mapped[float | None] = mapped_column(Float, nullable=True)
    sub_qib: Mapped[float | None] = mapped_column(Float, nullable=True)
    sub_nii: Mapped[float | None] = mapped_column(Float, nullable=True)
    sub_retail: Mapped[float | None] = mapped_column(Float, nullable=True)
    ipo: Mapped[IPO] = relationship(back_populates="snapshots")

class Watch(Base):
    """rule example: {"metric": "gmp_pct", "op": ">", "value": 20}"""
    __tablename__ = "watchlist"
    id: Mapped[int] = mapped_column(primary_key=True)
    ipo_id: Mapped[int] = mapped_column(ForeignKey("ipos.id"))
    rule: Mapped[dict] = mapped_column(JSON)
    channel: Mapped[str] = mapped_column(String(20), default="telegram")  # telegram | email | both
    last_triggered: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
