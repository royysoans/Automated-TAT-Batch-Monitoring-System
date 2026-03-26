"""
Webhook Router — receives incoming sample/test triggers.
This is the entry point that kicks off the entire pipeline.
"""

import json
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from database import get_db
from schedule_engine import parse_schedule, parse_tat, find_next_batch, calculate_eta
from alert_service import check_and_create_alerts

router = APIRouter(prefix="/api/webhook", tags=["Webhook"])


class SampleWebhook(BaseModel):
    sample_id: str = Field(..., description="Unique sample/test identifier")
    test_code: str = Field(..., description="Test code from EDOS")
    received_at: str = Field(..., description="ISO timestamp when sample was received")


@router.post("/sample")
def receive_sample(payload: SampleWebhook):
    """
    Webhook endpoint for sample intake.
    On receipt:
    1. Look up test in EDOS data
    2. Find next available batch window
    3. Assign sample to batch
    4. Calculate ETA
    5. Check for missed batch
    6. Trigger alerts if needed
    """
    conn = get_db()
    cursor = conn.cursor()

    # Check for duplicate sample
    cursor.execute("SELECT sample_id FROM samples WHERE sample_id = %s", (payload.sample_id,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail=f"Sample {payload.sample_id} already exists")

    # Look up the test in EDOS data
    cursor.execute("SELECT * FROM tests WHERE test_code = %s", (payload.test_code,))
    test = cursor.fetchone()

    if not test:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail=f"Test code '{payload.test_code}' not found in EDOS data"
        )

    # Parse the received timestamp
    try:
        received_at = datetime.fromisoformat(payload.received_at)
    except ValueError:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid timestamp format. Use ISO format.")

    # Parse schedule and TAT from stored JSON
    schedule = json.loads(test["schedule_json"])
    tat = json.loads(test["tat_json"])

    # Convert any stored time lists back to tuples
    if "cutoff_time" in schedule and isinstance(schedule["cutoff_time"], list):
        schedule["cutoff_time"] = tuple(schedule["cutoff_time"])
    if "cutoff_times" in schedule:
        schedule["cutoff_times"] = [tuple(t) if isinstance(t, list) else t for t in schedule["cutoff_times"]]
    if "window_start" in schedule and isinstance(schedule["window_start"], list):
        schedule["window_start"] = tuple(schedule["window_start"])
    if "window_end" in schedule and isinstance(schedule["window_end"], list):
        schedule["window_end"] = tuple(schedule["window_end"])
    if "target_time" in tat and isinstance(tat["target_time"], list):
        tat["target_time"] = tuple(tat["target_time"])

    # Find next batch window
    batch_cutoff = find_next_batch(schedule, received_at)

    # Detect missed batch: if we had to skip to a later batch
    # A batch is "missed" if the sample arrived after the cutoff of the
    # immediate/same-day batch
    missed_batch = False
    original_batch_cutoff = None

    if schedule.get("type") not in ("unknown", "walk_in", "refer"):
        cutoff = schedule.get("cutoff_time")
        if cutoff:
            ct_hour, ct_min = cutoff if isinstance(cutoff, (list, tuple)) else (cutoff, 0)
            same_day_cutoff = received_at.replace(hour=ct_hour, minute=ct_min, second=0, microsecond=0)

            # Check if the sample arrived on a valid day but after the cutoff
            days = schedule.get("days")
            if days is None or received_at.weekday() in days:
                if received_at > same_day_cutoff:
                    missed_batch = True
                    original_batch_cutoff = same_day_cutoff.isoformat()

    # Calculate ETA
    eta = calculate_eta(batch_cutoff, tat)

    # Determine status
    status = "assigned"
    if missed_batch:
        status = "reassigned"

    # Store sample
    cursor.execute("""
        INSERT INTO samples
        (sample_id, test_code, received_at, batch_cutoff, batch_processing_start,
         eta, status, missed_batch, original_batch_cutoff)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        payload.sample_id,
        payload.test_code,
        received_at.isoformat(),
        batch_cutoff.isoformat(),
        batch_cutoff.isoformat(),
        eta.isoformat(),
        status,
        1 if missed_batch else 0,
        original_batch_cutoff
    ))

    conn.commit()
    conn.close()

    # Check and create alerts (this may update status to 'breached')
    alerts = check_and_create_alerts(
        payload.sample_id, payload.test_code,
        received_at, batch_cutoff, eta, missed_batch
    )

    # Re-fetch official status from DB in case alert_service updated it
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM samples WHERE sample_id = %s", (payload.sample_id,))
    final_status = cursor.fetchone()["status"]
    conn.close()

    return {
        "success": True,
        "sample_id": payload.sample_id,
        "test_code": payload.test_code,
        "test_name": test["test_name"],
        "received_at": received_at.isoformat(),
        "batch_cutoff": batch_cutoff.isoformat(),
        "eta": eta.isoformat(),
        "status": final_status,
        "missed_batch": missed_batch,
        "original_batch_cutoff": original_batch_cutoff,
        "alerts": alerts,
        "schedule_type": schedule.get("type"),
        "tat_type": tat.get("type")
    }
