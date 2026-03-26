"""
Database setup for the TAT & Batch Monitoring System.
Connects to a PostgreSQL database (e.g., Neon or Supabase) using psycopg2.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db():
    """Get a database connection and a RealDictCursor."""
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable is not set. Please set it in .env")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    return conn


def init_db():
    """Initialize database tables."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tests (
            test_code TEXT PRIMARY KEY,
            test_name TEXT NOT NULL,
            state TEXT,
            city TEXT,
            mrp REAL,
            test_group TEXT,
            specimen_type TEXT,
            method TEXT,
            temperature TEXT,
            schedule_raw TEXT NOT NULL,
            tat_raw TEXT NOT NULL,
            schedule_json TEXT,
            tat_json TEXT
        );

        CREATE TABLE IF NOT EXISTS samples (
            id SERIAL PRIMARY KEY,
            sample_id TEXT UNIQUE NOT NULL,
            test_code TEXT NOT NULL,
            received_at TEXT NOT NULL,
            batch_cutoff TEXT,
            batch_processing_start TEXT,
            eta TEXT,
            status TEXT DEFAULT 'pending',
            missed_batch INTEGER DEFAULT 0,
            original_batch_cutoff TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (test_code) REFERENCES tests(test_code)
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id SERIAL PRIMARY KEY,
            sample_id TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            severity TEXT DEFAULT 'warning',
            message TEXT NOT NULL,
            acknowledged INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (sample_id) REFERENCES samples(sample_id)
        );

        CREATE INDEX IF NOT EXISTS idx_samples_status ON samples(status);
        CREATE INDEX IF NOT EXISTS idx_samples_test_code ON samples(test_code);
        CREATE INDEX IF NOT EXISTS idx_alerts_sample_id ON alerts(sample_id);
        CREATE INDEX IF NOT EXISTS idx_alerts_acknowledged ON alerts(acknowledged);
    """)

    conn.commit()
    cursor.close()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("PostgreSQL Database initialized.")

