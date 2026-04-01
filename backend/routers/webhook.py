
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from database import get_db
from schedule_engine import parse_schedule, parse_tat, find_next_batch, calculate_eta
from alert_service import check_and_create_alerts
from notification_service import send_confirmation_email

router = APIRouter(prefix="/api/webhook", tags=["Webhook"])

class SampleWebhook(BaseModel):
    sample_id: str = Field(..., description="Unique sample/test identifier")
    test_code: str = Field(..., description="Test code from EDOS")
    user_email: str = Field(None, description="Optional email address to send notifications to")
    received_at: str = Field(..., description="ISO timestamp when sample was received")

@router.post("/sample")
def receive_sample(payload: SampleWebhook):

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT sample_id FROM samples WHERE sample_id = %s", (payload.sample_id,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=409, detail=f"Sample {payload.sample_id} already exists")

    cursor.execute("SELECT * FROM tests WHERE test_code = %s", (payload.test_code,))
    test = cursor.fetchone()

    if not test:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail=f"Test code '{payload.test_code}' not found in EDOS data"
        )

    try:
        received_at = datetime.fromisoformat(payload.received_at)
        # Normalise to naive datetime (strip timezone) so all comparisons are consistent
        if received_at.tzinfo is not None:
            received_at = received_at.replace(tzinfo=None)
    except ValueError:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid timestamp format. Use ISO format.")

    schedule = json.loads(test["schedule_json"])
    tat = json.loads(test["tat_json"])

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

    batch_cutoff = find_next_batch(schedule, received_at)

    missed_batch = False
    original_batch_cutoff = None

    if schedule.get("type") not in ("unknown", "walk_in", "refer"):
        cutoff = schedule.get("cutoff_time")
        if cutoff:
            ct_hour, ct_min = cutoff if isinstance(cutoff, (list, tuple)) else (cutoff, 0)
            same_day_cutoff = received_at.replace(hour=ct_hour, minute=ct_min, second=0, microsecond=0)

            days = schedule.get("days")
            if days is None or received_at.weekday() in days:
                if received_at > same_day_cutoff:
                    missed_batch = True
                    original_batch_cutoff = same_day_cutoff.isoformat()

    eta = calculate_eta(batch_cutoff, tat)

    status = "assigned"
    if missed_batch:
        status = "reassigned"

    cursor.execute("""
        INSERT INTO samples
        (sample_id, test_code, user_email, received_at, batch_cutoff, batch_processing_start,
         eta, status, missed_batch, original_batch_cutoff)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        payload.sample_id,
        payload.test_code,
        payload.user_email,
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

    if payload.user_email:
        try:
            send_confirmation_email(
                payload.sample_id, payload.test_code, received_at, 
                batch_cutoff, eta, payload.user_email
            )
        except Exception:
            pass

    alerts = check_and_create_alerts(
        payload.sample_id, payload.test_code,
        received_at, batch_cutoff, eta, missed_batch, user_email=payload.user_email
    )

    conn = get_db()
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
