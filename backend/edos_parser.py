"""
EDOS CSV Parser — ingests the master reference file and loads tests into the database.
"""

import csv
import json
import os
from database import get_db, init_db
from schedule_engine import parse_schedule, parse_tat


EDOS_PATH = os.path.join(os.path.dirname(__file__), "data", "edos_list.csv")


def load_edos():
    """Parse the EDOS CSV and insert/update tests in the database."""
    init_db()
    conn = get_db()
    cursor = conn.cursor()

    count = 0
    skipped = 0

    with open(EDOS_PATH, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)

        # Skip the title row "Edos List,,,,..."
        header_row = next(reader)

        # Read the actual header
        headers = next(reader)
        headers = [h.strip().lower() for h in headers]

        for row in reader:
            if len(row) < 12:
                skipped += 1
                continue

            row_num = row[0].strip()
            if not row_num or not row_num.isdigit():
                skipped += 1
                continue

            state = row[1].strip()
            city = row[2].strip()
            test_code = row[3].strip()
            test_name = row[4].strip()
            mrp_str = row[5].strip()
            test_group = row[6].strip()
            specimen_type = row[7].strip()
            method = row[8].strip()
            temperature = row[9].strip()
            schedule_raw = row[10].strip()
            tat_raw = row[11].strip()

            if not test_code and not test_name:
                skipped += 1
                continue

            # Use test_name as fallback for test_code
            if not test_code:
                test_code = f"UNKNOWN_{row_num}"

            try:
                mrp = float(mrp_str) if mrp_str else 0
            except ValueError:
                mrp = 0

            # Parse schedule and TAT
            schedule_parsed = parse_schedule(schedule_raw)
            tat_parsed = parse_tat(tat_raw)

            # Convert to JSON for storage (handle tuples)
            schedule_json = json.dumps(schedule_parsed, default=str)
            tat_json = json.dumps(tat_parsed, default=str)

            cursor.execute("""
                INSERT INTO tests
                (test_code, test_name, state, city, mrp, test_group, specimen_type,
                 method, temperature, schedule_raw, tat_raw, schedule_json, tat_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (test_code) DO UPDATE SET
                    test_name = EXCLUDED.test_name,
                    state = EXCLUDED.state,
                    city = EXCLUDED.city,
                    mrp = EXCLUDED.mrp,
                    test_group = EXCLUDED.test_group,
                    specimen_type = EXCLUDED.specimen_type,
                    method = EXCLUDED.method,
                    temperature = EXCLUDED.temperature,
                    schedule_raw = EXCLUDED.schedule_raw,
                    tat_raw = EXCLUDED.tat_raw,
                    schedule_json = EXCLUDED.schedule_json,
                    tat_json = EXCLUDED.tat_json
            """, (
                test_code, test_name, state, city, mrp, test_group, specimen_type,
                method, temperature, schedule_raw, tat_raw, schedule_json, tat_json
            ))
            count += 1

    conn.commit()
    conn.close()
    return {"loaded": count, "skipped": skipped}


if __name__ == "__main__":
    result = load_edos()
    print(f"EDOS loaded: {result['loaded']} tests, {result['skipped']} skipped")
