
from datetime import datetime
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from database import get_db
from notification_service import send_completion_email

router = APIRouter(prefix="/api/samples", tags=["Samples"])

VALID_STATUSES = {"assigned", "reassigned", "processing", "completed", "breached"}
VALID_TRANSITIONS = {
    "assigned":   {"processing", "completed", "breached"},
    "reassigned": {"processing", "completed", "breached"},
    "processing": {"completed", "breached"},
    "completed":  set(),
    "breached":   {"processing", "completed"},  # allow closing out breached samples
}

class StatusUpdate(BaseModel):
    status: str

@router.get("")
def list_samples(
    status: str = Query(None, description="Filter by status"),
    test_code: str = Query(None, description="Filter by test code"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):

    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT s.*, t.test_name, t.test_group, t.schedule_raw, t.tat_raw
        FROM samples s
        LEFT JOIN tests t ON s.test_code = t.test_code
        WHERE 1=1
    """
    params = []

    if status:
        query += " AND s.status = %s"
        params.append(status)
    if test_code:
        query += " AND s.test_code = %s"
        params.append(test_code)

    query += " ORDER BY s.created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    cursor.execute(query, params)
    rows = cursor.fetchall()

    samples = []
    now = datetime.now()
    for row in rows:
        eta = datetime.fromisoformat(row["eta"]) if row["eta"] else None
        time_remaining = None
        is_overdue = False
        if eta:
            delta = (eta - now).total_seconds()
            time_remaining = max(0.0, delta)
            is_overdue = delta < 0

        samples.append({
            "id": row["id"],
            "sample_id": row["sample_id"],
            "test_code": row["test_code"],
            "test_name": row["test_name"],
            "test_group": row["test_group"],
            "received_at": row["received_at"],
            "batch_cutoff": row["batch_cutoff"],
            "eta": row["eta"],
            "status": row["status"],
            "missed_batch": bool(row["missed_batch"]),
            "original_batch_cutoff": row["original_batch_cutoff"],
            "schedule_raw": row["schedule_raw"],
            "tat_raw": row["tat_raw"],
            "time_remaining_seconds": time_remaining,
            "is_overdue": is_overdue,
            "created_at": str(row["created_at"]) if row["created_at"] else None,
        })

    conn.close()
    return {"samples": samples, "total": len(samples)}

@router.get("/stats")
def get_stats():

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total FROM samples")
    total = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT status, COUNT(*) as count FROM samples GROUP BY status
    """)
    status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

    cursor.execute("SELECT COUNT(*) as count FROM samples WHERE missed_batch = 1")
    missed = cursor.fetchone()["count"]

    now = datetime.now().isoformat()
    cursor.execute("""
        SELECT COUNT(*) as count FROM samples
        WHERE eta < %s AND status NOT IN ('completed', 'breached')
    """, (now,))
    overdue = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM alerts WHERE acknowledged = 0")
    active_alerts = cursor.fetchone()["count"]

    cursor.execute("""
        SELECT COUNT(*) as count FROM samples
        WHERE created_at > NOW() - INTERVAL '1 day'
    """)
    recent = cursor.fetchone()["count"]

    conn.close()

    return {
        "total_samples": total,
        "by_status": status_counts,
        "on_time": status_counts.get("assigned", 0) + status_counts.get("completed", 0),
        "delayed": missed,
        "overdue": overdue,
        "breached": status_counts.get("breached", 0),
        "active_alerts": active_alerts,
        "recent_24h": recent,
    }

@router.get("/{sample_id}")
def get_sample(sample_id: str):
    """Get detail for a single sample."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.*, t.test_name, t.test_group, t.schedule_raw, t.tat_raw,
               t.specimen_type, t.method, t.temperature
        FROM samples s
        LEFT JOIN tests t ON s.test_code = t.test_code
        WHERE s.sample_id = %s
    """, (sample_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {"error": "Sample not found"}

    cursor.execute("""
        SELECT * FROM alerts WHERE sample_id = %s ORDER BY created_at DESC
    """, (sample_id,))
    alert_rows = cursor.fetchall()

    alerts = []
    for a in alert_rows:
        alert_dict = dict(a)
        if alert_dict.get("created_at"):
            alert_dict["created_at"] = str(alert_dict["created_at"])
        alerts.append(alert_dict)

    now = datetime.now()
    eta = datetime.fromisoformat(row["eta"]) if row["eta"] else None
    time_remaining = None
    if eta:
        time_remaining = max(0.0, (eta - now).total_seconds())

    conn.close()

    return {
        "sample_id": row["sample_id"],
        "test_code": row["test_code"],
        "test_name": row["test_name"],
        "test_group": row["test_group"],
        "specimen_type": row["specimen_type"],
        "method": row["method"],
        "temperature": row["temperature"],
        "received_at": row["received_at"],
        "batch_cutoff": row["batch_cutoff"],
        "eta": row["eta"],
        "status": row["status"],
        "missed_batch": bool(row["missed_batch"]),
        "original_batch_cutoff": row["original_batch_cutoff"],
        "schedule_raw": row["schedule_raw"],
        "tat_raw": row["tat_raw"],
        "time_remaining_seconds": time_remaining,
        "is_overdue": eta and now > eta,
        "alerts": alerts,
    }

@router.put("/{sample_id}/status")
def update_sample_status(sample_id: str, body: StatusUpdate):

    new_status = body.status.lower()
    if new_status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status '{new_status}'. Valid: {VALID_STATUSES}")

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT status, test_code, user_email FROM samples WHERE sample_id = %s", (sample_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Sample not found")

    current_status = row["status"]
    allowed = VALID_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        conn.close()
        raise HTTPException(
            status_code=422,
            detail=f"Cannot transition from '{current_status}' to '{new_status}'. Allowed: {allowed}"
        )

    cursor.execute("""
        UPDATE samples SET status = %s, updated_at = NOW()
        WHERE sample_id = %s
    """, (new_status, sample_id))

    conn.commit()
    conn.close()

    if new_status == "completed" and row.get("user_email"):
        try:
            send_completion_email(sample_id, row["test_code"], row["user_email"])
        except Exception:
            pass

    return {"success": True, "sample_id": sample_id, "old_status": current_status, "new_status": new_status}

@router.delete("/{sample_id}")
def delete_sample(sample_id: str):

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM samples WHERE sample_id = %s", (sample_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Sample not found")

    cursor.execute("DELETE FROM alerts WHERE sample_id = %s", (sample_id,))
    cursor.execute("DELETE FROM samples WHERE sample_id = %s", (sample_id,))

    conn.commit()
    conn.close()

    return {"success": True, "message": f"Sample {sample_id} deleted successfully"}
