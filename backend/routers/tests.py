"""
Tests Router — browse EDOS test data.
"""

import json
from fastapi import APIRouter, Query
from database import get_db

router = APIRouter(prefix="/api/tests", tags=["Tests"])


@router.get("")
def list_tests(
    group: str = Query(None, description="Filter by test group (C1, C2, etc.)"),
    search: str = Query(None, description="Search by test code or name"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """List all tests from the EDOS data."""
    conn = get_db()
    cursor = conn.cursor()

    query = "SELECT * FROM tests WHERE 1=1"
    params = []

    if group:
        query += " AND test_group = %s"
        params.append(group)
    if search:
        query += " AND (test_code LIKE %s OR test_name LIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])

    query += " ORDER BY test_code LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    cursor.execute(query, params)
    rows = cursor.fetchall()

    tests = []
    for row in rows:
        schedule = json.loads(row["schedule_json"]) if row["schedule_json"] else {}
        tat = json.loads(row["tat_json"]) if row["tat_json"] else {}
        tests.append({
            "test_code": row["test_code"],
            "test_name": row["test_name"],
            "state": row["state"],
            "city": row["city"],
            "mrp": row["mrp"],
            "test_group": row["test_group"],
            "specimen_type": row["specimen_type"],
            "method": row["method"],
            "temperature": row["temperature"],
            "schedule_raw": row["schedule_raw"],
            "tat_raw": row["tat_raw"],
            "schedule_parsed": schedule,
            "tat_parsed": tat,
        })

    # Get total count
    count_query = "SELECT COUNT(*) as total FROM tests WHERE 1=1"
    count_params = []
    if group:
        count_query += " AND test_group = %s"
        count_params.append(group)
    if search:
        count_query += " AND (test_code LIKE %s OR test_name LIKE %s)"
        count_params.extend([f"%{search}%", f"%{search}%"])

    cursor.execute(count_query, count_params)
    total = cursor.fetchone()["total"]

    conn.close()
    return {"tests": tests, "total": total}


@router.get("/groups")
def get_groups():
    """Get all test groups with counts."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT test_group, COUNT(*) as count
        FROM tests
        GROUP BY test_group
        ORDER BY test_group
    """)
    groups = [{"group": row["test_group"], "count": row["count"]} for row in cursor.fetchall()]

    conn.close()
    return {"groups": groups}


@router.get("/{test_code}")
def get_test(test_code: str):
    """Get detail for a specific test."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM tests WHERE test_code = %s", (test_code,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return {"error": "Test not found"}

    schedule = json.loads(row["schedule_json"]) if row["schedule_json"] else {}
    tat = json.loads(row["tat_json"]) if row["tat_json"] else {}

    conn.close()
    return {
        "test_code": row["test_code"],
        "test_name": row["test_name"],
        "state": row["state"],
        "city": row["city"],
        "mrp": row["mrp"],
        "test_group": row["test_group"],
        "specimen_type": row["specimen_type"],
        "method": row["method"],
        "temperature": row["temperature"],
        "schedule_raw": row["schedule_raw"],
        "tat_raw": row["tat_raw"],
        "schedule_parsed": schedule,
        "tat_parsed": tat,
    }
