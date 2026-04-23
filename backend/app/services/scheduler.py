import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.services.signal_engine import SignalEngine

logger = logging.getLogger(__name__)


def start_scheduler(app: FastAPI) -> None:
    settings = get_settings()
    if not settings.signal_scheduler_enabled:
        app.state.scheduler = None
        return

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        _run_daily_signal_scan,
        CronTrigger(
            hour=settings.signal_scan_hour_utc,
            minute=settings.signal_scan_minute_utc,
            timezone="UTC",
        ),
        id="daily_signal_scan",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info(
        "Started APScheduler for daily_signal_scan at %02d:%02d UTC",
        settings.signal_scan_hour_utc,
        settings.signal_scan_minute_utc,
    )


def stop_scheduler(app: FastAPI) -> None:
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler is None:
        return
    scheduler.shutdown(wait=False)
    app.state.scheduler = None


def _run_daily_signal_scan() -> None:
    settings = get_settings()
    with SessionLocal() as session:
        try:
            result = SignalEngine(db=session, settings=settings).scan_active_universe()
        except Exception:  # noqa: BLE001
            session.rollback()
            logger.exception("daily_signal_scan failed")
            return
        logger.info(
            "daily_signal_scan completed: generated=%d skipped=%d universe=%s",
            len(result.signals),
            len(result.skipped),
            result.universe_version_id,
        )
