from apscheduler.schedulers.background import BackgroundScheduler
from . import jobs

def build_scheduler() -> BackgroundScheduler:
    sch = BackgroundScheduler(timezone="Asia/Kolkata")
    sch.add_job(jobs.refresh_ipo_list, "cron", hour="8,18", id="ipo_list")
    sch.add_job(jobs.snapshot_open_ipos, "interval", minutes=30, id="snapshots")
    sch.add_job(jobs.rescore_all, "interval", minutes=30, id="rescore")
    sch.add_job(jobs.evaluate_watchlist, "interval", minutes=15, id="watchlist")
    return sch
