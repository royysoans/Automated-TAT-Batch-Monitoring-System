
from fastapi import APIRouter, Query
from database import get_db
from alert_service import check_all_samples_for_breaches
from notification_service import NOTIFICATIONS_ENABLED, NOTIFICATION_TO, SMTP_HOST

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])

@router.get("")
def list_alerts(
    alert_type: str = Query(None, description="Filter by type: missed_batch, tat_breach, extended_tat"),
    acknowledged: bool = Query(None, description="Filter by acknowledged status"),
    limit: int = Query(50, ge=1, le=500),
):

    conn = get_db()
    cursor = conn.cursor()

    query = "SELECT * FROM alerts WHERE 1=1"
    params = []

    if alert_type:
        query += " AND alert_type = %s"
        params.append(alert_type)
    if acknowledged is not None:
        query += " AND acknowledged = %s"
        params.append(1 if acknowledged else 0)

    query += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()

    alerts = []
    for row in rows:
        alert_dict = dict(row)
        if alert_dict.get("created_at"):
            alert_dict["created_at"] = str(alert_dict["created_at"])
        alerts.append(alert_dict)

    conn.close()

    return {"alerts": alerts, "total": len(alerts)}

@router.post("/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int):

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("UPDATE alerts SET acknowledged = 1 WHERE id = %s", (alert_id,))
    if cursor.rowcount == 0:
        conn.close()
        return {"error": "Alert not found"}

    conn.commit()
    conn.close()
    return {"success": True, "alert_id": alert_id}

@router.post("/check-breaches")
def trigger_breach_check():

    results = check_all_samples_for_breaches()
    return {"breaches_found": len(results), "details": results}

@router.get("/notification-status")
def notification_status():

    return {
        "email_enabled": NOTIFICATIONS_ENABLED,
        "smtp_host": SMTP_HOST if NOTIFICATIONS_ENABLED else None,
        "recipients": NOTIFICATION_TO.split(",") if NOTIFICATIONS_ENABLED and NOTIFICATION_TO else [],
        "message": "Email notifications are active" if NOTIFICATIONS_ENABLED else "Email notifications are not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, and NOTIFICATION_TO in your .env file."
    }
