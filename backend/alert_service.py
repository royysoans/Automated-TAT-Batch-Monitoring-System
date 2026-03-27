
from datetime import datetime
from database import get_db
from notification_service import send_alert_notification

def check_and_create_alerts(sample_id, test_code, received_at, batch_cutoff, eta, missed_batch=False):

    conn = get_db()
    cursor = conn.cursor()
    alerts_created = []

    if missed_batch:
        message = (
            f"Sample {sample_id} (test {test_code}) missed its original batch window. "
            f"Received at {received_at.strftime('%Y-%m-%d %H:%M')}, "
            f"reassigned to batch at {batch_cutoff.strftime('%Y-%m-%d %H:%M')}. "
            f"New ETA: {eta.strftime('%Y-%m-%d %H:%M')}."
        )
        cursor.execute("""
            INSERT INTO alerts (sample_id, alert_type, severity, message)
            VALUES (%s, 'missed_batch', 'warning', %s)
        """, (sample_id, message))
        alerts_created.append({"type": "missed_batch", "severity": "warning", "message": message})
        try:
            send_alert_notification("missed_batch", "warning", message, sample_id, test_code)
        except Exception:
            pass

    time_to_result = (eta - received_at).total_seconds() / 3600
    if time_to_result > 168:
        message = (
            f"Sample {sample_id} (test {test_code}) has an extended TAT of "
            f"{time_to_result:.0f} hours ({time_to_result/24:.1f} days). "
            f"ETA: {eta.strftime('%Y-%m-%d %H:%M')}."
        )
        cursor.execute("""
            INSERT INTO alerts (sample_id, alert_type, severity, message)
            VALUES (%s, 'extended_tat', 'info', %s)
        """, (sample_id, message))
        alerts_created.append({"type": "extended_tat", "severity": "info", "message": message})
        try:
            send_alert_notification("extended_tat", "info", message, sample_id, test_code)
        except Exception:
            pass

    now = datetime.now()
    if now > eta:
        hours_overdue = (now - eta).total_seconds() / 3600
        severity = "critical" if hours_overdue > 24 else "warning"
        message = (
            f"OVERDUE: Sample {sample_id} (test {test_code}) is {hours_overdue:.1f} hours "
            f"past its ETA of {eta.strftime('%Y-%m-%d %H:%M')}."
        )
        cursor.execute("""
            INSERT INTO alerts (sample_id, alert_type, severity, message)
            VALUES (%s, 'tat_breach', %s, %s)
        """, (sample_id, severity, message))
        alerts_created.append({"type": "tat_breach", "severity": severity, "message": message})
        try:
            send_alert_notification("tat_breach", severity, message, sample_id, test_code)
        except Exception:
            pass

        cursor.execute("""
            UPDATE samples SET status = 'breached', updated_at = NOW()
            WHERE sample_id = %s
        """, (sample_id,))

    conn.commit()
    conn.close()
    return alerts_created

def check_all_samples_for_breaches():

    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now().isoformat()
    cursor.execute("""
        SELECT sample_id, test_code, eta, user_email
        FROM samples
        WHERE status IN ('assigned', 'reassigned', 'pending', 'processing')
        AND eta < %s
    """, (now,))

    overdue = cursor.fetchall()
    alerts = []

    for row in overdue:
        sample_id = row["sample_id"]
        eta = datetime.fromisoformat(row["eta"])
        hours_overdue = (datetime.now() - eta).total_seconds() / 3600

        cursor.execute("""
            SELECT COUNT(*) as cnt FROM alerts
            WHERE sample_id = %s AND alert_type = 'tat_breach'
            AND created_at > NOW() - INTERVAL '1 hour'
        """, (sample_id,))

        if cursor.fetchone()["cnt"] == 0:
            severity = "critical" if hours_overdue > 24 else "warning"
            message = (
                f"OVERDUE: Sample {sample_id} (test {row['test_code']}) is "
                f"{hours_overdue:.1f} hours past ETA of {eta.strftime('%Y-%m-%d %H:%M')}."
            )
            cursor.execute("""
                INSERT INTO alerts (sample_id, alert_type, severity, message)
                VALUES (%s, 'tat_breach', %s, %s)
            """, (sample_id, severity, message))
            alerts.append({"sample_id": sample_id, "severity": severity})
            try:
                send_alert_notification("tat_breach", severity, message, sample_id, row["test_code"], user_email=row["user_email"])
            except Exception:
                pass

            cursor.execute("""
                UPDATE samples SET status = 'breached', updated_at = NOW()
                WHERE sample_id = %s
            """, (sample_id,))

    conn.commit()
    conn.close()
    return alerts
