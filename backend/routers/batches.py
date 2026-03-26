"""
Batches Router — view batch queues and upcoming batch windows.
"""

import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Query
from database import get_db
from schedule_engine import parse_schedule, find_next_batch

router = APIRouter(prefix="/api/batches", tags=["Batches"])


@router.get("")
def list_batches(
    limit: int = Query(20, ge=1, le=100),
):
    """
    List upcoming batch windows across all tests.
    Shows which tests have upcoming batches and how many samples are queued.
    """
    conn = get_db()
    cursor = conn.cursor()

    # PostgreSQL strict GROUP BY: must include all non-aggregated SELECT columns.
    cursor.execute("""
        SELECT
            s.batch_cutoff,
            s.test_code,
            t.test_name,
            t.test_group,
            t.schedule_raw,
            t.tat_raw,
            COUNT(*) as sample_count,
            SUM(CASE WHEN s.missed_batch = 1 THEN 1 ELSE 0 END) as missed_count,
            STRING_AGG(s.sample_id, ',') as sample_ids
        FROM samples s
        LEFT JOIN tests t ON s.test_code = t.test_code
        WHERE s.status IN ('assigned', 'reassigned', 'pending', 'in_batch', 'processing')
        GROUP BY s.batch_cutoff, s.test_code, t.test_name, t.test_group, t.schedule_raw, t.tat_raw
        ORDER BY s.batch_cutoff ASC
        LIMIT %s
    """, (limit,))

    batches = []
    now = datetime.now()

    for row in cursor.fetchall():
        batch_cutoff = datetime.fromisoformat(row["batch_cutoff"]) if row["batch_cutoff"] else None
        is_past = batch_cutoff and batch_cutoff < now
        time_until = None
        if batch_cutoff and not is_past:
            time_until = (batch_cutoff - now).total_seconds()

        batches.append({
            "batch_cutoff": row["batch_cutoff"],
            "test_code": row["test_code"],
            "test_name": row["test_name"],
            "test_group": row["test_group"],
            "schedule": row["schedule_raw"],
            "tat": row["tat_raw"],
            "sample_count": row["sample_count"],
            "missed_count": row["missed_count"],
            "sample_ids": row["sample_ids"].split(",") if row["sample_ids"] else [],
            "is_past": is_past,
            "time_until_seconds": time_until,
        })

    conn.close()
    return {"batches": batches}


@router.get("/upcoming")
def upcoming_batches():
    """
    Show the next batch window for each unique test that has samples.
    """
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now()

    # Get distinct test codes with pending samples
    cursor.execute("""
        SELECT DISTINCT ON (s.test_code) s.test_code, t.test_name, t.schedule_json, t.schedule_raw
        FROM samples s
        LEFT JOIN tests t ON s.test_code = t.test_code
        WHERE s.status IN ('assigned', 'reassigned', 'pending')
    """)

    upcoming = []
    for row in cursor.fetchall():
        schedule = json.loads(row["schedule_json"]) if row["schedule_json"] else {}

        # Convert lists back to tuples
        if "cutoff_time" in schedule and isinstance(schedule["cutoff_time"], list):
            schedule["cutoff_time"] = tuple(schedule["cutoff_time"])
        if "cutoff_times" in schedule:
            schedule["cutoff_times"] = [tuple(t) if isinstance(t, list) else t for t in schedule["cutoff_times"]]
        if "window_start" in schedule and isinstance(schedule["window_start"], list):
            schedule["window_start"] = tuple(schedule["window_start"])
        if "window_end" in schedule and isinstance(schedule["window_end"], list):
            schedule["window_end"] = tuple(schedule["window_end"])

        next_batch = find_next_batch(schedule, now)

        upcoming.append({
            "test_code": row["test_code"],
            "test_name": row["test_name"],
            "schedule": row["schedule_raw"],
            "next_batch": next_batch.isoformat(),
            "time_until_seconds": (next_batch - now).total_seconds(),
        })

    conn.close()
    upcoming.sort(key=lambda x: x["next_batch"])
    return {"upcoming": upcoming}
