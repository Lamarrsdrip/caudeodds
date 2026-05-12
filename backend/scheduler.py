"""Daily cron scheduler for ClaudeOdds.

Auto-runs the AI ensemble pipeline at a fixed UTC hour each day so the admin
doesn't have to click "Force Re-Generate" manually. Hour is configurable via
admin_config.cron_hour_utc (default 8 = 09:00 Lagos).

Also runs an interval auto-settlement job that pulls final scores from
API-Football to mark pending picks won/lost/void.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

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
        picks, rejections, total = await run_pipeline(date_str, settings, db=db)
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
        # Notify admin via push that the slip is ready and needs a SportyBet code.
        # We broadcast to all admin push subscriptions (filter by user role isn't
        # available in the subscriptions collection, so we look up admin user IDs).
        try:
            from push_service import broadcast
            admin_ids = [u["id"] async for u in db.users.find({"role": "admin"}, {"_id": 0, "id": 1})]
            if admin_ids:
                await broadcast(
                    db,
                    title="ClaudeOdds — Today's slip is ready",
                    body=f"AI ensemble produced {len(picks)} picks. Open admin to publish the SportyBet code.",
                    url="/admin/predictions",
                    user_filter={"user_id": {"$in": admin_ids}},
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


async def _run_tomorrow_pregen(db):
    """Pre-generate tomorrow's slip late-night so the dashboard rolls over
    seamlessly the moment today's slate finishes."""
    from pipeline import tomorrow_str
    date_str = tomorrow_str()
    existing = await db.claudeodd_runs.find_one({"_id": date_str}, {"_id": 0})
    if existing:
        logger.info("Tomorrow-pregen: %s already generated — skipping", date_str)
        return

    job_id = str(uuid.uuid4())
    await db.claudeodd_jobs.insert_one({
        "id": job_id, "date": date_str, "status": "running", "force": False,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None, "picks": 0, "rejected": 0, "fixtures_analyzed": 0,
        "error": None, "source": "tomorrow_pregen",
    })
    try:
        settings_doc = await db.claudeodd_settings.find_one({"_id": "main"}, {"_id": 0})
        settings = Settings(**settings_doc) if settings_doc else Settings()
        picks, rejections, total = await run_pipeline(date_str, settings, db=db)
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
        logger.info("Tomorrow-pregen complete (%s): picks=%d total=%d", date_str, len(picks), total)
    except Exception as e:
        logger.exception("Tomorrow-pregen failed: %s", e)
        await db.claudeodd_jobs.update_one({"id": job_id}, {"$set": {
            "status": "failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error": str(e)[:500],
        }})


async def _run_autosettle(db):
    """Run auto-settlement sweep."""
    try:
        from settlement_service import settle_pending_picks
        stats = await settle_pending_picks(db)
        logger.info("Auto-settle: checked=%d settled=%d still_pending=%d skipped=%d",
                    stats["checked"], stats["settled"],
                    stats["still_pending"], stats["skipped"])
    except Exception as e:
        logger.exception("Auto-settle failed: %s", e)


async def _run_fixture_sync(db):
    """Fixture-first pipeline: schedule sync + odds enrichment + AI for newly priced.

    Runs every 15 min via APScheduler so tomorrow's fixtures appear on the
    dashboard hours before bookmaker odds — and flip from 'Waiting for Odds'
    → 'Analyzing' → 'Ready' automatically as odds drop in.
    """
    try:
        from fixture_sync_service import run_full_cycle
        stats = await run_full_cycle(db)
        for d, s in stats.items():
            logger.info(
                "Fixture-sync %s: schedule new=%d updated=%d · odds priced=%d · AI ready=%d rejected=%d",
                d, s["schedule"]["new"], s["schedule"]["updated"],
                s["odds"]["priced"], s["ai"]["ready"], s["ai"]["rejected"],
            )
    except Exception as e:
        logger.exception("Fixture-sync failed: %s", e)


async def configure_scheduler(db) -> dict:
    """Read admin config and (re)schedule the daily + auto-settle jobs."""
    global _scheduler
    cfg = await db.admin_config.find_one({"_id": "main"}, {"_id": 0}) or {}
    # Defensive clamp — protect the scheduler from any legacy/corrupt values
    try:
        hour = max(0, min(23, int(cfg.get("cron_hour_utc", 8))))
    except (TypeError, ValueError):
        hour = 8
    try:
        minute = max(0, min(59, int(cfg.get("cron_minute_utc", 0))))
    except (TypeError, ValueError):
        minute = 0
    enabled = bool(cfg.get("cron_enabled", True))
    autosettle_enabled = bool(cfg.get("autosettle_enabled", True))
    try:
        autosettle_hours = max(1, min(24, int(cfg.get("autosettle_interval_hours", 2))))
    except (TypeError, ValueError):
        autosettle_hours = 2

    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC")
        _scheduler.start()

    # Daily pipeline job
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

    # Auto-settle job
    if _scheduler.get_job("autosettle"):
        _scheduler.remove_job("autosettle")
    if autosettle_enabled:
        _scheduler.add_job(
            _run_autosettle,
            IntervalTrigger(hours=autosettle_hours),
            id="autosettle",
            args=[db],
            replace_existing=True,
            misfire_grace_time=3600,
            next_run_time=datetime.now(timezone.utc),  # run shortly after startup
        )
        logger.info("Auto-settle scheduled every %dh", autosettle_hours)

    # Tomorrow-pregen job: every day at 22:00 UTC pre-build tomorrow's slip
    # so the dashboard rolls over seamlessly the moment today's slate finishes.
    if _scheduler.get_job("tomorrow_pregen"):
        _scheduler.remove_job("tomorrow_pregen")
    if enabled:
        _scheduler.add_job(
            _run_tomorrow_pregen,
            CronTrigger(hour=22, minute=0, timezone="UTC"),
            id="tomorrow_pregen",
            args=[db],
            replace_existing=True,
            misfire_grace_time=3600,
        )
        logger.info("Tomorrow-pregen scheduled daily at 22:00 UTC")

    # Fixture-sync job: every 30 minutes pull tomorrow's schedule, match with
    # any newly published odds, and run AI on freshly-priced fixtures. This
    # cadence is intentionally conservative — the Odds API free tier is 500
    # req/month so we cache aggressively and don't poll more than necessary.
    if _scheduler.get_job("fixture_sync"):
        _scheduler.remove_job("fixture_sync")
    _scheduler.add_job(
        _run_fixture_sync,
        IntervalTrigger(minutes=30),
        id="fixture_sync",
        args=[db],
        replace_existing=True,
        misfire_grace_time=600,
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=15),
    )
    logger.info("Fixture-sync scheduled every 30 minutes")

    daily_next = _scheduler.get_job("daily_pipeline").next_run_time if _scheduler.get_job("daily_pipeline") else None
    settle_next = _scheduler.get_job("autosettle").next_run_time if _scheduler.get_job("autosettle") else None
    pregen_next = _scheduler.get_job("tomorrow_pregen").next_run_time if _scheduler.get_job("tomorrow_pregen") else None
    fxsync_next = _scheduler.get_job("fixture_sync").next_run_time if _scheduler.get_job("fixture_sync") else None
    return {
        "daily_enabled": enabled, "daily_next": str(daily_next),
        "daily_hour_utc": hour, "daily_minute_utc": minute,
        "autosettle_enabled": autosettle_enabled,
        "autosettle_interval_hours": autosettle_hours,
        "autosettle_next": str(settle_next),
        "tomorrow_pregen_next": str(pregen_next),
        "fixture_sync_next": str(fxsync_next),
    }


def shutdown():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
