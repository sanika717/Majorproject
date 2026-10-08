"""Minimal background scheduler: one daemon thread, no extra framework.

Env (all optional):
  ESG_AUTO_UPDATE=0            disable the scheduler entirely
  ESG_AIR_INTERVAL_MIN=60      CPCB feed is hourly
  ESG_DAILY_INTERVAL_MIN=1440  electricity / carbon / water checks
  ESG_UPDATE_START_DELAY_S=20  wait after startup before the first cycle
  DATA_GOV_IN_API_KEY          required for the air job
Multi-worker safe: a job is skipped if another worker ran it within its interval (esg_update_runs).
"""
import logging
import os
import threading
from datetime import datetime, timedelta
from typing import Any, Dict
from backend.app.models.esg import EsgUpdateRun
from backend.app.services.esg_update import air_cpcb, electricity_bescom, file_sources
from backend.app.services.esg_update.http import UpdateError
from backend.app.services.esg_update.provenance import bump_if_changed

log = logging.getLogger("urbanpulse.esg_update")
JOBS = ("air", "electricity", "carbon", "water")


def _interval(job: str) -> timedelta:
    key, default = ("ESG_AIR_INTERVAL_MIN", 60) if job == "air" else ("ESG_DAILY_INTERVAL_MIN", 1440)
    return timedelta(minutes=int(os.environ.get(key, default)))


def run_job(job: str, session_factory, force: bool = False) -> Dict[str, Any]:
    if job not in JOBS:
        raise ValueError(f"unknown job {job}")
    db = session_factory()
    try:
        now = datetime.utcnow()
        last = db.query(EsgUpdateRun).filter_by(job=job).order_by(EsgUpdateRun.id.desc()).first()
        if not force and last:
            if last.status == "running" and now - last.started_at < timedelta(minutes=10):
                return {"job": job, "status": "skipped", "message": "already running"}
            if last.status != "running" and last.finished_at and now - last.finished_at < _interval(job):
                return {"job": job, "status": "skipped", "message": "ran recently (interval not elapsed)"}
        run = EsgUpdateRun(job=job, started_at=now, status="running")
        db.add(run)
        db.commit()
        try:
            if job == "air":
                res = air_cpcb.run(db)
            elif job == "electricity":
                res = electricity_bescom.run(db)
            else:
                res = file_sources.run(db, job)
        except UpdateError as e:
            db.rollback()
            res = {"status": "failed", "message": str(e)}
        except Exception as e:  # never let a bad source kill the scheduler
            db.rollback()
            log.exception("ESG update job %s crashed", job)
            res = {"status": "failed", "message": f"{type(e).__name__}: {e}"}
        run = db.get(EsgUpdateRun, run.id)
        run.status = res.get("status", "ok")
        run.finished_at = datetime.utcnow()
        for k in ("fetched", "inserted", "updated", "unchanged"):
            setattr(run, k, res.get(k, 0))
        run.data_hash, run.source_url, run.message = res.get("data_hash"), res.get("source_url"), res.get("message")
        db.commit()
        new_version = None
        if run.status == "ok" and (run.inserted or run.updated):
            new_version = bump_if_changed(db, f"{job}: {run.inserted} inserted, {run.updated} updated")
        log.info("ESG update %s -> %s (%s)", job, run.status, run.message)
        return {"job": job, "status": run.status, "fetched": run.fetched, "inserted": run.inserted, "updated": run.updated,
                "unchanged": run.unchanged, "message": run.message, "esg_recalculation_triggered": new_version is not None,
                "data_version": new_version}
    finally:
        db.close()


class EsgUpdateScheduler:
    def __init__(self, session_factory, tick_s: int = 30):
        self.sf, self.tick, self._stop, self._t = session_factory, tick_s, threading.Event(), None

    def start(self):
        if os.environ.get("ESG_AUTO_UPDATE", "1") == "0" or self._t:
            return False
        self._t = threading.Thread(target=self._loop, name="esg-updater", daemon=True)
        self._t.start()
        return True

    def stop(self):
        self._stop.set()

    def _loop(self):
        if self._stop.wait(int(os.environ.get("ESG_UPDATE_START_DELAY_S", "20"))):
            return
        while not self._stop.is_set():
            for job in JOBS:          # run_job itself enforces each job's interval
                try:
                    run_job(job, self.sf)
                except Exception:
                    log.exception("scheduler tick failed for %s", job)
            self._stop.wait(self.tick)
