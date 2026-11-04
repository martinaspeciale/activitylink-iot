"""Compare adaptation with actual nodes and controlled sensor loss at cloud ingress.

A temporary localhost broker relays unmodified telemetry and real actuator commands.
Only node1 telemetry is withheld during the fault window; radio traffic continues.
The ordinary cloud is stopped for the experiment and restored afterwards.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import paho.mqtt.client as mqtt

from native_stack import ROOT, STATE, PYTHON_DEPS, config, db, free_port, start_backend, stop_backend, wait_for


def scenario(out, credentials, adaptive, repeat):
    session_id = hashlib.sha256(str(out.parent.resolve()).encode()).hexdigest()[:10]
    name = f"hw-{'adaptive' if adaptive else 'baseline'}-{session_id}-{repeat}"
    start = time.time()
    # Each run contains 10 normal seconds, 15 seconds of selective loss, then 15 seconds of recovery.
    fault_start, fault_end, end = start + 10, start + 25, start + 40
    records, errors = [], []
    lock = threading.Lock()
    actual_ready, relay_ready = threading.Event(), threading.Event()
    actual = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="activitylink-stress-wire")
    relay = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="activitylink-stress-relay")
    out.mkdir()
    stream = (out / "wire.jsonl").open("x", buffering=1)

    def record(entry):
        with lock:
            records.append(entry)
            stream.write(json.dumps(entry) + "\n")

    def actual_connected(client, userdata, flags, reason, properties):
        client.subscribe("activitylink/+/telemetry")

    def relay_connected(client, userdata, flags, reason, properties):
        client.subscribe("activitylink/+/command")

    def receive(client, userdata, msg):
        now = time.time()
        # Withhold only HAR telemetry at cloud ingress; the radio nodes remain active.
        drop = msg.topic == "activitylink/node1/telemetry" and fault_start <= now < fault_end
        record({"time": now, "kind": "telemetry", "topic": msg.topic,
                "payload": msg.payload.decode(), "dropped": drop})
        if not drop:
            relay.publish(msg.topic, msg.payload, qos=0, retain=False)

    def command(client, userdata, msg):
        record({"time": time.time(), "kind": "command", "topic": msg.topic,
                "payload": msg.payload.decode()})
        # Forward backend commands to the real actuator through the ordinary broker.
        actual.publish(msg.topic, msg.payload, qos=0, retain=False)

    actual.on_connect, relay.on_connect = actual_connected, relay_connected
    actual.on_subscribe = lambda *args: actual_ready.set()
    relay.on_subscribe = lambda *args: relay_ready.set()
    actual.on_message, relay.on_message = receive, command
    proc = None
    try:
        relay.connect("127.0.0.1", 18884, 15)
        relay.loop_start()
        actual.connect("::1", 1883, 15)
        actual.loop_start()
        if not actual_ready.wait(5) or not relay_ready.wait(5):
            raise RuntimeError("relay subscription timeout")
        start = time.time()
        fault_start, fault_end, end = start + 10, start + 25, start + 40
        env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(PYTHON_DEPS), str(ROOT))),
                   DB_HOST="127.0.0.1", DB_PORT="13306", DB_PASSWORD=credentials["app"],
                   MQTT_HOST="127.0.0.1", MQTT_PORT="18884", ADAPTIVE=str(adaptive), RUN_ID=name)
        with (out / "cloud.log").open("x") as log:
            proc = subprocess.Popen([sys.executable, "-m", "backend.app"], cwd=ROOT, env=env,
                                    stdout=log, stderr=subprocess.STDOUT)
        print(f"START {name}: fault from +10s to +25s, total 40s", flush=True)
        while time.time() < end:
            if proc.poll() is not None:
                raise RuntimeError("experiment backend exited")
            time.sleep(0.2)
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=10)
        actual.disconnect()
        actual.loop_stop()
        relay.disconnect()
        relay.loop_stop()
        stream.close()

    with db(credentials, user="activitylink", database="activitylink") as connection:
        with connection.cursor() as cur:
            cur.execute("SELECT * FROM metrics WHERE run_id=%s ORDER BY time", (name,))
            metrics = cur.fetchall()
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    stale = [m for m in metrics if fault_start <= m["time"] < fault_end and m["sensor_stale"]]
    dropped = [r for r in records if r["kind"] == "telemetry" and r["dropped"]]
    sensor_before = [r for r in records if r["kind"] == "telemetry" and r["topic"] == "activitylink/node1/telemetry"
                     and r["time"] < fault_start]
    detection = stale[0]["time"] - sensor_before[-1]["time"] if stale and sensor_before else None
    recovered = any(m["time"] > fault_end + 2 and not m["sensor_stale"] for m in metrics)
    # Assess reported LED states after allowing time for stale detection and propagation.
    reported = [json.loads(r["payload"])["led"] for r in records if r["kind"] == "telemetry"
                and r["topic"] == "activitylink/node2/telemetry"
                and fault_start + 9 <= r["time"] < fault_end]
    result = {"run_id": name, "adaptive": adaptive, "start": start,
              "fault_start": fault_start, "fault_end": fault_end, "end": time.time(),
              "fault_kind": "selective node1 message loss at cloud ingress; actual radio nodes remain active",
              "sensor_messages_dropped": len(dropped), "stale_samples": len(stale),
              "stale_command_red": sum(m["command_led"] == 3 for m in stale),
              "reported_leds_during_stale": reported, "detection_seconds_from_last_forwarded": detection,
              "recovered": recovered, "last_counts": metrics[-1] if metrics else None}
    result["passed"] = bool(dropped and stale and reported and recovered and metrics[-1]["invalid"] == 0
                             and metrics[-1]["queue_drops"] == 0
                             and all((m["command_led"] == 3) == bool(adaptive) for m in stale)
                             and all((led == 3) == bool(adaptive) for led in reported))
    (out / "summary.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    args.out.mkdir(parents=True, exist_ok=False)
    credentials = config()
    free_port(18884)
    conf = args.out / "relay-broker.conf"
    conf.write_text("listener 18884 127.0.0.1\nallow_anonymous true\npersistence false\n")
    results = []
    # Avoid a second controller publishing commands while the experiment backend is active.
    stop_backend()
    broker = None
    try:
        with (args.out / "relay-broker.log").open("x") as log:
            broker = subprocess.Popen([str(ROOT / "tools/local-broker/build-no-tls/src/mosquitto"),
                                       "-c", str(conf.resolve()), "-v"], stdout=log, stderr=subprocess.STDOUT)
        def ready():
            import socket
            with socket.create_connection(("127.0.0.1", 18884), timeout=1):
                return True
        wait_for(ready, 10)
        for repeat in range(1, args.repeats + 1):
            # Alternate order to reduce a fixed ordering effect.
            for adaptive in ((1, 0) if repeat % 2 else (0, 1)):
                results.append(scenario(args.out / f"pair-{repeat}-{'adaptive' if adaptive else 'baseline'}",
                                        credentials, adaptive, repeat))
    finally:
        if broker:
            broker.terminate()
            broker.wait(timeout=10)
        # Restore ordinary adaptive control after the experiment, including on failure.
        start_backend(credentials, 1, "hardware-native-post-stress")
    summary = {"scope": "real MQTT/SQL/actuator, host ingress loss, 3 paired trials by default; no physical power failure",
               "runs": results, "passed": all(r["passed"] for r in results)}
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
    return int(not summary["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
