"""
fix_breached_samples.py
=======================
One-time remediation script.

The bug: check_and_create_alerts() used to run a TAT breach check at
sample INTAKE time. Any sample whose ETA had already passed (or was equal
to now) when it was first inserted got immediately stamped as 'breached'.

This script resets those samples back to 'assigned' (or 'reassigned' if
missed_batch=1), removes the spurious 'tat_breach' alerts that were
created within 5 minutes of the sample being created, and prints a summary.

Run once after deploying the bug-fix, then delete this script.

Usage:
    cd backend
    python fix_breached_samples.py
"""

from datetime import datetime, timedelta
from database import get_db

def fix():
    conn = get_db()
    cursor = conn.cursor()

    # ── 1. Find samples that were flagged 'breached' but their tat_breach
    #       alert was created within 5 minutes of the sample itself.
    #       Those are the ones that were wrongly breached at intake.
    cursor.execute("""
        SELECT s.sample_id, s.missed_batch, s.created_at
        FROM samples s
        WHERE s.status = 'breached'
        AND EXISTS (
            SELECT 1 FROM alerts a
            WHERE a.sample_id = s.sample_id
              AND a.alert_type = 'tat_breach'
              AND a.created_at <= s.created_at + INTERVAL '5 minutes'
        )
    """)

    rows = cursor.fetchall()
    print(f"Found {len(rows)} samples to remediate.")

    remediated = 0
    for row in rows:
        sample_id  = row["sample_id"]
        missed     = row["missed_batch"]
        new_status = "reassigned" if missed else "assigned"

        # Reset the sample status
        cursor.execute("""
            UPDATE samples SET status = %s, updated_at = NOW()
            WHERE sample_id = %s
        """, (new_status, sample_id))

        # Delete the spurious tat_breach alert (created within 5 min of intake)
        cursor.execute("""
            DELETE FROM alerts
            WHERE sample_id = %s
              AND alert_type = 'tat_breach'
              AND created_at <= (
                  SELECT created_at + INTERVAL '5 minutes'
                  FROM samples WHERE sample_id = %s
              )
        """, (sample_id, sample_id))

        print(f"  ✅ {sample_id}: breached → {new_status}  (missed_batch={bool(missed)})")
        remediated += 1

    conn.commit()
    conn.close()
    print(f"\nDone. Remediated {remediated} sample(s).")

if __name__ == "__main__":
    fix()
