"""Read the latest controller run from SQL and optionally open its Grafana view."""

import argparse
import json
import os
import sys
from pathlib import Path
import time
import urllib.parse
import webbrowser

# Service management is kept with the platform support files.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "support/scripts"))

from native_stack import STATE, config, db


def watch_mqtt(out, broker="a"):
    import paho.mqtt.client as mqtt

    out.mkdir(parents=True, exist_ok=False)
    stream = (out / "mqtt.jsonl").open("x", buffering=1)
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2, client_id=f"activitylink-demo-watch-{os.getpid()}"
    )
    host, port = ("127.0.0.1", 18884) if broker == "b" else ("::1", 1883)

    def connected(client, userdata, flags, reason, properties):
        if reason.is_failure:
            print("MQTT connection rejected", flush=True)
            return
        print(f"MQTT connected; broker {broker.upper()} ({host}:{port}); observing telemetry", flush=True)
        client.subscribe("activitylink/+/telemetry")

    def disconnected(client, userdata, flags, reason, properties):
        print("MQTT disconnected; no device state can be observed through this channel", flush=True)

    def message(client, userdata, msg):
        data = json.loads(msg.payload)
        stream.write(json.dumps({"time": time.time(), "topic": msg.topic, "data": data}) + "\n")
        print(
            f"{data['node']} seq={data['seq']} activity={data['activity']} "
            f"enabled={data['enabled']} led={data['led']}",
            flush=True,
        )

    client.on_connect = connected
    client.on_disconnect = disconnected
    client.on_message = message
    try:
        client.connect(host, port, 15)
        client.loop_forever()
    except KeyboardInterrupt:
        pass
    except OSError as exc:
        hint = " Avviare prima una prova stress: il broker B è temporaneo." if broker == "b" else ""
        raise RuntimeError(f"Broker {broker.upper()} non raggiungibile.{hint}") from exc
    finally:
        client.disconnect()
        stream.close()
        print(f"Observations saved in {out / 'mqtt.jsonl'}")


def latest_run():
    if not (STATE / "credentials.json").exists():
        raise RuntimeError("Start the local services before reading the demo run")
    with db(config(), user="activitylink", database="activitylink") as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT run_id,time,adaptive,sensor_stale,actuator_stale,command_led,reported_led "
                "FROM metrics ORDER BY id DESC LIMIT 1"
            )
            row = cursor.fetchone()
    if row is None:
        raise RuntimeError("No controller samples yet; start the demo and wait for telemetry")
    if time.time() - row["time"] > 15:
        raise RuntimeError("The latest controller sample is old; start or resume the backend")
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--run-id", action="store_true")
    group.add_argument("--dashboard", action="store_true")
    group.add_argument("--watch", type=Path, metavar="OUTPUT_DIRECTORY")
    parser.add_argument("--broker", choices=("a", "b"), default="a", help="Broker for --watch")
    args = parser.parse_args()
    if args.watch:
        watch_mqtt(args.watch, args.broker)
        return
    row = latest_run()
    if args.run_id:
        print(row["run_id"])
        return
    query = urllib.parse.urlencode(
        {"from": "now-2m", "to": "now", "var-run_id": row["run_id"], "refresh": "5s"}
    )
    url = "http://127.0.0.1:3000/d/activitylink?" + query
    print(json.dumps(row, indent=2))
    print(url)

    # Select the observed run explicitly so the dashboard does not keep an older run filter
    if args.dashboard:
        webbrowser.open(url)


if __name__ == "__main__":
    main()
