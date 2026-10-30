"""Observe real nodes; optionally test commands after a passive MQTT interval.

Never run with the device emulator. Does not flash or reset any device.
"""
import argparse
import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
import serial

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.core import validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--host", default="::1")
    parser.add_argument("--seconds", type=int, default=100)
    parser.add_argument("--max-gap", type=float, default=3.0,
                        help="maximum permitted gap between telemetry messages (seconds)")
    parser.add_argument("--commands", action="store_true")
    parser.add_argument("--serial", action="append", default=[], metavar="NODE=PORT")
    args = parser.parse_args()
    if args.seconds < 3 or args.max_gap <= 0:
        parser.error("--seconds must be at least 3 and --max-gap must be positive")
    serial_ports = []
    for entry in args.serial:
        if "=" not in entry or entry.split("=", 1)[0] not in ("node1", "node2"):
            parser.error("--serial must be node1=PORT or node2=PORT")
        serial_ports.append(entry.split("=", 1))
    if len({node for node, _ in serial_ports}) != len(serial_ports):
        parser.error("each node may have only one serial reader")
    args.out.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects earlier observations.
    stream = (args.out / "telemetry.jsonl").open("x", buffering=1)
    observations, errors, commands, connections = [], [], [], []
    watchdog = None
    stop = threading.Event()
    readers = []

    def serial_reader(node, port):
        try:
            with serial.Serial(port, 115200, timeout=0.3, exclusive=True) as dev:
                with (args.out / f"{node}-serial.log").open("x", buffering=1) as log:
                    while not stop.is_set():
                        line = dev.readline()
                        if line:
                            log.write(datetime.now(timezone.utc).isoformat() + " " + line.decode("utf-8", "replace"))
        except Exception as exc:
            errors.append({"serial": node, "error": str(exc)})

    for node, port in serial_ports:
        thread = threading.Thread(target=serial_reader, args=(node, port))
        thread.start()
        readers.append(thread)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="activitylink-hardware-check")

    def connected(c, userdata, flags, reason, properties):
        connections.append({"time": time.time(), "reason": str(reason)})
        if reason.is_failure:
            errors.append({"error": "MQTT connection refused", "reason": str(reason)})
        c.subscribe("activitylink/+/telemetry", qos=0)

    def message(c, userdata, msg):
        entry = {"time": time.time(), "topic": msg.topic, "payload": msg.payload.decode("utf-8", "replace")}
        try:
            if msg.retain:
                raise ValueError("retained telemetry is not a live observation")
            entry["data"] = validate(msg.topic, msg.payload)
        except Exception as exc:
            errors.append({"time": entry["time"], "error": str(exc)})
        observations.append(entry)
        stream.write(json.dumps(entry) + "\n")

    client.on_connect = connected
    client.on_message = message
    started = time.time()
    try:
        client.connect(args.host, 1883, 15)
        client.loop_start()
        stop.wait(args.seconds)
        passive_end = time.time()
        if args.commands:
            initial = next((e["data"]["enabled"] for e in reversed(observations)
                            if e.get("data", {}).get("node") == "node1"), None)
            if initial is None or not all(any(e.get("data", {}).get("node") == n for e in observations)
                                          for n in ("node1", "node2")):
                errors.append({"error": "commands skipped: missing valid telemetry"})
            else:
                def command(node, value, field, expected):
                    sent = time.time()
                    receipt = client.publish(f"activitylink/{node}/command", value.encode("ascii"), qos=0, retain=False)
                    receipt.wait_for_publish(timeout=5)
                    deadline = time.monotonic() + 6
                    matched = False
                    while time.monotonic() < deadline:
                        matched = any(e["time"] > sent and e.get("data", {}).get("node") == node
                                      and e["data"].get(field) == expected for e in list(observations))
                        if matched:
                            break
                        stop.wait(0.1)
                    commands.append({"time": sent, "node": node, "byte": value,
                                     "field": field, "expected": expected, "confirmed": matched})
                try:
                    command("node1", "P", "enabled", 0)
                    command("node1", "R", "enabled", 1)
                    for value in range(4):
                        command("node2", str(value), "led", value)
                    command("node2", "2", "led", 2)
                finally:
                    if initial == 0:
                        command("node1", "P", "enabled", 0)
                # Observe feedback watchdog after the final command (firmware uses >8s).
                stop.wait(11)
                last_command_time = next(c["time"] for c in reversed(commands) if c["node"] == "node2")
                watchdog = any(e["time"] >= last_command_time + 9
                               and e.get("data", {}).get("node") == "node2"
                               and e["data"]["led"] == 3 for e in observations)
    finally:
        client.disconnect()
        client.loop_stop()
        stop.set()
        for thread in readers:
            thread.join(timeout=2)
        stream.close()

    summary = {"started": started, "ended": time.time(), "passive_seconds": passive_end - started,
               "connections": connections, "errors": errors, "commands": commands,
               "watchdog_confirmed": watchdog, "nodes": {}}
    for node in ("node1", "node2"):
        entries = [e for e in observations if e.get("data", {}).get("node") == node and e["time"] <= passive_end]
        gaps = [b["time"] - a["time"] for a, b in zip(entries, entries[1:])]
        discontinuities = [{"before": a["data"], "after": b["data"]} for a, b in zip(entries, entries[1:])
                           if b["data"]["boot"] != a["data"]["boot"] or b["data"]["seq"] != a["data"]["seq"] + 1]
        summary["nodes"][node] = {"count": len(entries), "first": entries[0] if entries else None,
                                   "last": entries[-1] if entries else None, "max_gap_seconds": max(gaps, default=None),
                                   "sequence_discontinuities": discontinuities}
    summary["passed"] = not (errors or watchdog is False or len(connections) != 1
                            or any(not c["confirmed"] for c in commands)
                            or any(n["count"] < max(2, int(args.seconds * 0.9))
                                   or n["sequence_discontinuities"]
                                   or n["max_gap_seconds"] is None
                                   or n["max_gap_seconds"] > args.max_gap
                                   or n["first"]["time"] - started > args.max_gap
                                   or passive_end - n["last"]["time"] > args.max_gap
                                   for n in summary["nodes"].values()))
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return int(not summary["passed"])


if __name__ == "__main__":
    raise SystemExit(main())
