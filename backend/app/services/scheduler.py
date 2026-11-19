"""Reliable background scheduler and worker for automated daily government-scheme synchronization.

Prevents overlapping runs, supports daily intervals, provides manual 'Sync now',
and exposes operational status and metrics.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Any

from app.core.config import settings
from app.database.connection import SessionLocal
from app.services.scheme_sync import run_sync_with_advisory_lock, sync_all_sources

logger = logging.getLogger("lifenavigator.scheduler")

_sync_lock = threading.Lock()
_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()

_scheduler_state: dict[str, Any] = {
    "is_running": False,
    "interval_hours": settings.SYNC_INTERVAL_HOURS,
    "last_run_started": None,
    "last_run_completed": None,
    "last_run_status": "idle",
    "last_summary": None,
    "total_runs": 0,
    "last_error": None,
}


def run_sync_job() -> dict[str, Any]:
    """Execute a single synchronization pass protected by local thread lock and PostgreSQL advisory lock."""
    if not _sync_lock.acquire(blocking=False):
        return {
            "status": "skipped",
            "reason": "Another synchronization job is currently running.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    now = datetime.now(timezone.utc)
    _scheduler_state["last_run_started"] = now.isoformat()
    _scheduler_state["last_run_status"] = "running"
    _scheduler_state["last_error"] = None

    try:
        summary = run_sync_with_advisory_lock(apply=True)
        if summary.skipped > 0 and summary.details and summary.details[0].get("status") == "skipped":
            result = {
                "status": "skipped",
                "reason": "Distributed advisory lock held by another worker process.",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
            _scheduler_state["last_run_completed"] = result["completed_at"]
            _scheduler_state["last_run_status"] = "skipped"
            _scheduler_state["last_summary"] = result
            return result

        result = {
            "status": "success",
            "discovered": summary.discovered,
            "added": summary.added,
            "updated": summary.updated,
            "unchanged": summary.unchanged,
            "skipped": summary.skipped,
            "failed": summary.failed,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        _scheduler_state["last_run_completed"] = result["completed_at"]
        _scheduler_state["last_run_status"] = "success"
        _scheduler_state["last_summary"] = result
        _scheduler_state["total_runs"] += 1
        return result
    except Exception as exc:
        logger.exception("Scheduled synchronization failed: %s", exc)
        result = {
            "status": "failed",
            "error": str(exc),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        _scheduler_state["last_run_completed"] = result["completed_at"]
        _scheduler_state["last_run_status"] = "failed"
        _scheduler_state["last_error"] = str(exc)
        return result
    finally:
        _sync_lock.release()


def _scheduler_loop() -> None:
    """Background worker loop sleeping between daily intervals."""
    interval_seconds = max(3600, settings.SYNC_INTERVAL_HOURS * 3600)
    logger.info("Daily scheme scheduler started with %s-hour interval.", settings.SYNC_INTERVAL_HOURS)

    # Initial check on launch
    time.sleep(2)  # Give DB pool a moment to initialize
    if not _stop_event.is_set():
        run_sync_job()

    while not _stop_event.is_set():
        # Sleep in small 5-second intervals so shutdown is fast and responsive
        for _ in range(int(interval_seconds / 5)):
            if _stop_event.is_set():
                break
            time.sleep(5)
        if not _stop_event.is_set():
            run_sync_job()


def start_scheduler() -> None:
    """Start the background scheduler thread."""
    global _worker_thread
    if not settings.SCHEDULER_ENABLED:
        logger.info("Scheme scheduler is disabled by configuration.")
        _scheduler_state["is_running"] = False
        return
    if _worker_thread is not None and _worker_thread.is_alive():
        return

    _stop_event.clear()
    _scheduler_state["is_running"] = True
    _worker_thread = threading.Thread(target=_scheduler_loop, daemon=True, name="SchemeScheduler")
    _worker_thread.start()


def stop_scheduler() -> None:
    """Stop the background scheduler thread."""
    _stop_event.set()
    _scheduler_state["is_running"] = False


def trigger_sync_now() -> dict[str, Any]:
    """Trigger manual on-demand synchronization using the exact same worker pipeline."""
    result = run_sync_job()
    return {
        "status": "completed" if result.get("status") == "success" else result.get("status", "completed"),
        "report": result,
    }


def get_scheduler_status() -> dict[str, Any]:
    """Return operational health, schedule timestamps, and last run report."""
    interval_hours = settings.SYNC_INTERVAL_HOURS
    last_comp = _scheduler_state["last_run_completed"]
    next_run = None
    if last_comp:
        try:
            dt = datetime.fromisoformat(last_comp)
            next_run = (dt + timedelta(hours=interval_hours)).isoformat()
        except Exception:
            pass

    return {
        "is_running": _sync_lock.locked(),
        "scheduler_running": _scheduler_state["is_running"],
        "is_busy": _sync_lock.locked(),
        "interval_hours": interval_hours,
        "sync_interval_hours": interval_hours,
        "last_run_started": _scheduler_state["last_run_started"],
        "last_run_completed": _scheduler_state["last_run_completed"],
        "last_sync_time": _scheduler_state["last_run_completed"],
        "last_run_status": _scheduler_state["last_run_status"],
        "next_scheduled_run": next_run,
        "next_scheduled_sync": next_run,
        "total_runs": _scheduler_state["total_runs"],
        "last_summary": _scheduler_state["last_summary"],
        "last_error": _scheduler_state["last_error"],
    }
