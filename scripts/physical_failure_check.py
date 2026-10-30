"""Record HAR disconnection and reconnection during a manual test."""
import argparse
import json
from pathlib import Path
import threading
import time

import paho.mqtt.client as mqtt

from native_stack import config, db

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--out", type=Path, required=True)
parser.add_argument("--timeout", type=int, default=300)
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=False)
stream = (args.out / "mqtt.jsonl").open("x", buffering=1)
events = []
ready = threading.Event()
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="activitylink-physical-check")
client.on_connect = lambda c, u, f, r, p: c.subscribe("activitylink/+/telemetry")
client.on_subscribe = lambda *a: ready.set()


def message(c, u, msg):
    entry = {"time": time.time(), "topic": msg.topic, "data": json.loads(msg.payload)}
    events.append(entry)
    stream.write(json.dumps(entry) + "\n")


client.on_message = message
client.connect("::1", 1883, 15)
client.loop_start()
credentials = config()
start = time.time()
stale, recovery = None, None
try:
    assert ready.wait(5)
    print("READY: unplug HAR for at least 15s, then replug", flush=True)
    while time.time() - start < args.timeout:
        with db(credentials, user="activitylink", database="activitylink") as connection:
            with connection.cursor() as cur:
                cur.execute("SELECT * FROM metrics ORDER BY id DESC LIMIT 1")
                row = cur.fetchone()
        if row and row["time"] > start and row["sensor_stale"] and row["reported_led"] == 3:
            if stale is None:
                stale = row
                print("STALE/RED observed; awaiting HAR return", flush=True)
        if stale and row["time"] > stale["time"] and not row["sensor_stale"] and row["reported_led"] in (1, 2):
            recovery = row
            break
        time.sleep(0.3)
finally:
    client.disconnect()
    client.loop_stop()
    stream.close()
sensor_events = [e for e in events if e["data"]["node"] == "node1"]
boots = list(dict.fromkeys(e["data"]["boot"] for e in sensor_events))
result = {"start": start, "end": time.time(), "stale": stale, "recovery": recovery,
          "observed_har_boots": boots, "passed": bool(stale and recovery and len(boots) >= 2),
          "scope": "physical action by user; red/stale, new HAR boot and recovery via actual MQTT/SQL"}
(args.out / "summary.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
raise SystemExit(not result["passed"])
