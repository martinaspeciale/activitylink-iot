"""Controlled restart of project services with real nodes and watchdog evidence."""
import argparse
import json
from pathlib import Path
import threading
import time

import paho.mqtt.client as mqtt

from native_stack import config, db, pid, start_broker, start_mysql, stop_service, wait_for

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--out", type=Path, required=True)
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=False)
credentials = config()
start_broker()  # Adopt only the identified project broker, never an unrelated server.
events = []
stream = (args.out / "mqtt.jsonl").open("x", buffering=1)
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="activitylink-service-check")
ready = threading.Event()
client.on_connect = lambda c, u, f, r, p: c.subscribe("activitylink/+/telemetry")
client.on_subscribe = lambda *a: ready.set()


def receive(c, u, msg):
    entry = {"time": time.time(), "data": json.loads(msg.payload)}
    events.append(entry)
    stream.write(json.dumps(entry) + "\n")


def snapshot():
    with db(credentials, user="activitylink", database="activitylink") as connection:
        with connection.cursor() as cur:
            cur.execute("SELECT * FROM metrics ORDER BY id DESC LIMIT 1")
            metric = cur.fetchone()
            cur.execute("SELECT node,COUNT(*) AS count,MAX(received) AS latest FROM telemetry GROUP BY node")
            nodes = cur.fetchall()
    return {"metric": metric, "nodes": nodes}


def recovered(after):
    row = snapshot()
    if not (row["metric"]["time"] > after and not row["metric"]["sensor_stale"]
            and not row["metric"]["actuator_stale"]
            and row["metric"]["reported_led"] in (1, 2)
            and all(time.time() - n["latest"] < 3 for n in row["nodes"])):
        raise ValueError("waiting for fresh SQL and activity feedback")
    return row


client.on_message = receive
client.connect("::1", 1883, 15)
client.loop_start()
assert ready.wait(5)
cloud_pid = pid("cloud")
result = {"cloud_pid_before": cloud_pid, "before": snapshot()}
try:
    down = time.time()
    stop_service("mysql")
    print("MySQL stopped; collecting 12s of actual MQTT", flush=True)
    time.sleep(12)
    watchdog = any(e["time"] > down + 8 and e["data"]["node"] == "node2" and e["data"]["led"] == 3 for e in events)
    start_mysql(credentials)
    database_up = time.time()
    after_db = wait_for(lambda: recovered(database_up), 45)
    # Every sample observed during DB absence must eventually appear in SQL.
    during = [e for e in events if down + 1 <= e["time"] < database_up]
    def persisted():
        with db(credentials, user="activitylink", database="activitylink") as connection:
            with connection.cursor() as cur:
                for entry in during:
                    m = entry["data"]
                    cur.execute("SELECT received FROM telemetry WHERE node=%s AND boot=%s AND seq=%s", (m["node"], m["boot"], m["seq"]))
                    if not cur.fetchone():
                        raise ValueError("waiting for buffered telemetry commit")
        return True
    wait_for(persisted, 15)
    result["database"] = {"down": down, "up": database_up, "watchdog_red": watchdog,
                           "observed_while_down": len(during), "all_observed_persisted": True,
                           "cloud_pid_unchanged": pid("cloud") == cloud_pid, "after": after_db}
    result["database"]["passed"] = watchdog and len(during) > 10 and pid("cloud") == cloud_pid
    broker_down = time.time()
    stop_service("broker")
    print("Broker stopped for 12s; watchdog runs locally", flush=True)
    time.sleep(12)
    start_broker()
    broker_up = time.time()
    after_broker = wait_for(lambda: recovered(broker_up), 120)
    result["broker"] = {"down": broker_down, "up": broker_up,
                         "recovery_seconds_after_start": time.time() - broker_up,
                         "cloud_pid_unchanged": pid("cloud") == cloud_pid, "after": after_broker}
    result["broker"]["passed"] = pid("cloud") == cloud_pid
finally:
    start_mysql(credentials)
    start_broker()
    client.disconnect()
    client.loop_stop()
    stream.close()
result["passed"] = result["database"]["passed"] and result["broker"]["passed"]
(args.out / "summary.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
raise SystemExit(not result["passed"])
