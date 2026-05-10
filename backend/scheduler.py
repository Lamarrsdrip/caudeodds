"""Daily cron scheduler for ClaudeOdds.

Auto-runs the AI ensemble pipeline at a fixed UTC hour each day so the admin
doesn't have to click "Force Re-Generate" manually. Hour is configurable via
admin_config.cron_hour_utc (default 8 = 09:00 Lagos).
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from models import Settings
from pipeline import run_pipeline, today_str

logger = logging.getLogger("claudeodd.scheduler")

_scheduler: AsyncIOScheduler | None = None


async def _run_daily_pipeline(db):
    """Run the AI pipeline if today's run hasn't completed yet."""
    date_str = today_str()
    existing = await db.claudeodd_runs.find_one({"_id": date_str}, {"_id": 0})
    if existing:
        logger.info("Daily cron: today's slip already generated — skipping")
        return

    job_id = str(uuid.uuid4())
    await db.claudeodd_jobs.insert_one({
        "id": job_id,
        "date": date_str,
        "status": "running",
        "force": False,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "picks": 0, "rejected": 0, "fixtures_analyzed": 0,
        "error": None,
        "source": "cron",
    })

    try:
        settings_doc = await db.claudeodd_settings.find_one({"_id": "main"}, {"_id": 0})
        settings = Settings(**settings_doc) if settings_doc else Settings()
        picks, rejections, total = await run_pipeline(date_str, settings)
        if picks:
            await db.claudeodd_picks.insert_many([p.model_dump() for p in picks])
        if rejections:
            await db.claudeodd_rejections.insert_many([r.model_dump() for r in rejections])
        await db.claudeodd_runs.update_one(
            {"_id": date_str},
            {"$set": {"date": date_str, "rejected_count": len(rejections),
                      "fixtures_analyzed": total,
                      "completed_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        await db.claudeodd_jobs.update_one({"id": job_id}, {"$set": {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "picks": len(picks), "rejected": len(rejections), "fixtures_analyzed": total,
        }})
        # Notify admin via push that the slip is ready and needs a SportyBet code
        try:
            from push_service import broadcast
            await broadcast(
                db,
                title="ClaudeOdds — Today's slip is ready",
                body=f"AI ensemble produced {len(picks)} picks. Open the admin panel to publish the SportyBet code.",
                url="/admin/predictions",
                user_filter={"user_id": "admin"},  # only admin, no broad alert yet (no code published)
            )
        except Exception as e:
            logger.warning("Admin push failed: %s", e)
        logger.info("Daily cron pipeline complete: picks=%d total=%d", len(picks), total)
    except Exception as e:
        logger.exception("Daily cron pipeline failed: %s", e)
        await db.claudeodd_jobs.update_one({"id": job_id}, {"$set": {
            "status": "failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error": str(e)[:500],
        }})


async def configure_scheduler(db) -> dict:
    """Read admin config and (re)schedule the daily job."""
    global _scheduler
    cfg = await db.admin_config.find_one({"_id": "main"}, {"_id": 0}) or {}
    hour = int(cfg.get("cron_hour_utc", 8))
    minute = int(cfg.get("cron_minute_utc", 0))
    enabled = bool(cfg.get("cron_enabled", True))

    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC")
        _scheduler.start()

    # Remove existing job if any
    if _scheduler.get_job("daily_pipeline"):
        _scheduler.remove_job("daily_pipeline")

    if enabled:
        _scheduler.add_job(
            _run_daily_pipeline,
            CronTrigger(hour=hour, minute=minute, timezone="UTC"),
            id="daily_pipeline",
            args=[db],
            replace_existing=True,
            misfire_grace_time=3600,
        )
        logger.info("Daily cron scheduled at %02d:%02d UTC", hour, minute)
        return {"enabled": True, "hour_utc": hour, "minute_utc": minute,
                "next_run": str(_scheduler.get_job("daily_pipeline").next_run_time)}
    logger.info("Daily cron is DISABLED in admin config")
    return {"enabled": False}


def shutdown():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
