"""
SQLite to PostgreSQL Data Migration Script
Transfers tests, samples, and alerts from local sqlite db to cloud Postgres.
"""

import sqlite3
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "data", "tat_monitor.db")
POSTGRES_URL = os.environ.get("DATABASE_URL")

def migrate():
    print(f"Connecting to SQLite at {SQLITE_PATH}...")
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    sq_cursor = sqlite_conn.cursor()

    if not POSTGRES_URL:
        print("ERROR: DATABASE_URL not set in .env")
        return

    print("Connecting to PostgreSQL...")
    pg_conn = psycopg2.connect(POSTGRES_URL)
    pg_conn.autocommit = True
    pg_cursor = pg_conn.cursor()

    # 1. Tests
    sq_cursor.execute("SELECT * FROM tests")
    tests = sq_cursor.fetchall()
    print(f"Migrating {len(tests)} tests...")
    for t in tests:
        try:
            pg_cursor.execute("""
                INSERT INTO tests (
                    test_code, test_name, state, city, mrp, test_group, 
                    specimen_type, method, temperature, schedule_raw, tat_raw, 
                    schedule_json, tat_json
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) ON CONFLICT (test_code) DO NOTHING
            """, (
                t['test_code'], t['test_name'], t['state'], t['city'], 
                t['mrp'], t['test_group'], t['specimen_type'], t['method'], 
                t['temperature'], t['schedule_raw'], t['tat_raw'], 
                t['schedule_json'], t['tat_json']
            ))
        except Exception as e:
            print(f"Error migrating test {t['test_code']}: {e}")

    # 2. Samples
    sq_cursor.execute("SELECT * FROM samples")
    samples = sq_cursor.fetchall()
    print(f"Migrating {len(samples)} samples...")
    for s in samples:
        try:
            pg_cursor.execute("""
                INSERT INTO samples (
                    sample_id, test_code, received_at, batch_cutoff, 
                    batch_processing_start, eta, status, missed_batch, 
                    original_batch_cutoff, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                ) ON CONFLICT (sample_id) DO NOTHING
            """, (
                s['sample_id'], s['test_code'], s['received_at'], 
                s['batch_cutoff'], s['batch_processing_start'], s['eta'], 
                s['status'], s['missed_batch'], s['original_batch_cutoff'], 
                s['created_at'], s['updated_at']
            ))
        except Exception as e:
            print(f"Error migrating sample {s['sample_id']}: {e}")

    # 3. Alerts
    sq_cursor.execute("SELECT * FROM alerts")
    alerts = sq_cursor.fetchall()
    print(f"Migrating {len(alerts)} alerts...")
    for a in alerts:
        try:
            pg_cursor.execute("""
                INSERT INTO alerts (
                    sample_id, alert_type, severity, message, 
                    acknowledged, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s
                )
            """, (
                a['sample_id'], a['alert_type'], a['severity'], 
                a['message'], a['acknowledged'], a['created_at']
            ))
        except Exception as e:
            print(f"Error migrating alert: {e}")

    print("Migration complete!")
    pg_cursor.close()
    pg_conn.close()
    sqlite_conn.close()

if __name__ == "__main__":
    migrate()
