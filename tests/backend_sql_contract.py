"""Actual MySQL tests of identity/freshness in an isolated temporary schema."""

import argparse
import json
import os
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from backend.app import connect_database, store
from backend.core import validate
from native_stack import config, db

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
credentials = config()
name = "activitylink_test_" + uuid.uuid4().hex[:12]
root = db(credentials)
with root.cursor() as cursor:
    cursor.execute(f"CREATE DATABASE {name}")
os.environ.update(DB_NAME=name, DB_USER="root", DB_PASSWORD=credentials["root"], DB_PORT="13306")
connection = None
try:
    connection = connect_database()
    message = dict(
        node="node1", boot="0123456789abcdef", seq=2, uptime=10, activity=1, enabled=1, led=1
    )
    validate("activitylink/node1/telemetry", json.dumps(message))
    assert store(connection, message, 100.0) == "accepted"
    assert store(connection, message, 110.0) == "duplicates"
    assert store(connection, dict(message, seq=1), 120.0) == "out_of_order"
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS n,MAX(received) AS last FROM telemetry")
        assert cursor.fetchone() == {"n": 1, "last": 100.0}, "duplicates must not refresh freshness"
    assert store(connection, dict(message, boot="fedcba9876543210", seq=1), 130.0) == "accepted"
    assert store(connection, dict(message, seq=3, uptime=11), 140.0) == "accepted"
    result = {
        "passed": True,
        "checks": [
            "real schema creation",
            "insert",
            "duplicate identity",
            "out-of-order rejection",
            "duplicates do not refresh freshness",
            "new boot restarts sequence",
            "next sequence",
        ],
        "scope": "temporary SQL schema; no simulated messages sent to hardware broker",
    }
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
finally:
    if connection:
        connection.close()
    with root.cursor() as cursor:
        cursor.execute(f"DROP DATABASE {name}")
    root.close()
