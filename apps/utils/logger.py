# apps/utils/logger.py

import json
from datetime import datetime

# Simpele tellers per status
_metrics = {
    "jobs_executed": 0,
    "jobs_skipped": 0,
    "jobs_failed": 0,
}

def log_job(
    job: str,
    guild_id: int | None = None,
    channel_id: int | None = None,
    dag: str | None = None,
    status: str = "executed",
    duration: float | None = None,
    attempt: int | None = None,
    user_id: int | None = None,
    message_id: int | None = None,
) -> None:
    """
    Schrijf één regel JSON naar stdout met extra context.
    """
    record = {
        "timestamp": datetime.now().isoformat(),
        "job": job,
        "status": status,
        "guild_id": guild_id,
        "channel_id": channel_id,
        "dag": dag,
        "duration": duration,
        "attempt": attempt,
        "user_id": user_id,
        "message_id": message_id,
    }
    # Print alleen niet‑lege velden
    print(json.dumps({k: v for k, v in record.items() if v is not None}))

    # Tellers bijhouden
    if status == "executed":
        _metrics["jobs_executed"] += 1
    elif status == "skipped":
        _metrics["jobs_skipped"] += 1
    elif status == "failed":
        _metrics["jobs_failed"] += 1

def log_startup(missed: list[str]) -> None:
    """
    Log een opstartmelding met een lijst van ingehaalde jobs.
    """
    print(json.dumps({
        "timestamp": datetime.now().isoformat(),
        "event": "startup",
        "missed_jobs": missed,
    }))

def get_metrics() -> dict:
    """
    Geef de huidige tellers terug. Handig voor tests of toekomstige monitoring.
    """
    return _metrics.copy()
