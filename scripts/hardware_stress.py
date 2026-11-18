"""Compare adaptation with actual nodes and controlled sensor loss at cloud ingress.

A temporary localhost broker relays unmodified telemetry and real actuator commands.
Only node1 telemetry is withheld during the fault window; radio traffic continues.
The ordinary cloud is stopped for the experiment and restored afterwards.
"""

import argparse
import fcntl
import hashlib
import json
import os
import select
import signal
import socket
from pathlib import Path
import subprocess
import sys
import threading
import time

import paho.mqtt.client as mqtt

# Service management is kept with the platform support files.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "support/scripts"))

from native_stack import (
    ROOT,
    WORK,
    STATE,
    PYTHON_DEPS,
    config,
    db,
    free_port,
    start_backend,
    stop_backend,
    wait_for,
)


CONTROL_SOCKET = Path("/tmp") / ("activitylink-stress-" + hashlib.sha256(str(STATE).encode()).hexdigest()[:16] + ".sock")


def control_request(command):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(5)
        connection.connect(str(CONTROL_SOCKET))
        connection.sendall((command + "\n").encode())
        with connection.makefile("r") as stream:
            response = json.loads(stream.readline())
    if not response["ok"]:
        raise RuntimeError(response["message"])
    return response


def show_stress_timer(response):
    """Display elapsed time from the relay switch; confirm stale from real SQL metrics."""
    settings = json.loads((ROOT / "config/devices.json").read_text())
    threshold = float(settings["stale_seconds"])
    started = response["fault_started_monotonic"]
    print("Timer dall'attivazione del blocco HAR (soglia di freschezza del backend).", flush=True)
    while True:
        elapsed = max(0.0, time.monotonic() - started)
        shown = min(elapsed, threshold)
        print(f"\rStress HAR: {shown:05.2f} / {threshold:.2f} s", end="", flush=True)
        if elapsed >= threshold:
            break
        time.sleep(min(0.05, threshold - elapsed))
    print(" — soglia temporale raggiunta.", flush=True)
    print("Verifica di sensor_stale nel run corrente su MySQL…", flush=True)
    try:
        with db(config(), user="activitylink", database="activitylink") as connection:
            deadline = time.monotonic() + 10
            while True:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT time,sensor_stale,command_led FROM metrics "
                        "WHERE run_id=%s AND time>=%s AND sensor_stale=1 ORDER BY time LIMIT 1",
                        (response["run_id"], response["fault_start"]),
                    )
                    row = cursor.fetchone()
                if row:
                    detected = row["time"] - response["fault_start"]
                    print(f"SENSOR STALE = 1 — confermato dal backend in MySQL "
                          f"a +{detected:.2f} s dal blocco; command_led={row['command_led']}.", flush=True)
                    print("Grafana lo mostrerà al prossimo refresh. "
                          "Lo stress resta attivo fino a: ./scripts/demo.sh stress off", flush=True)
                    return
                if time.monotonic() >= deadline:
                    raise RuntimeError("sensor_stale=1 non ancora confermato nel run corrente")
                time.sleep(0.1)
    except Exception as exc:
        raise RuntimeError(f"{exc}. Il blocco resta attivo: usare stress status oppure stress off.") from exc


def start_manual(out, mode):
    # A worker owns the experiment; each subsequent shell command only changes its phase.
    try:
        current = control_request("status")
    except (OSError, ValueError):
        pass
    else:
        raise RuntimeError(f"Prova già attiva: {current['run_id']}")
    out.parent.mkdir(parents=True, exist_ok=True)
    log_path = out.with_suffix(".log")
    with log_path.open("x") as log:
        worker = subprocess.Popen(
            [sys.executable, "-u", str(Path(__file__).resolve()), "--out", str(out), "--manual", mode],
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        )
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if worker.poll() is not None:
            raise RuntimeError(f"Avvio fallito; consultare {log_path}")
        try:
            response = control_request("status")
        except (OSError, ValueError):
            time.sleep(0.2)
        else:
            print(json.dumps(response, ensure_ascii=False), flush=True)
            print(f"Log: {log_path}\nComandi: stress on → stress off → stress stop", flush=True)
            return
    worker.terminate()
    worker.wait(timeout=20)
    raise RuntimeError(f"Timeout di avvio; consultare {log_path}")


class ManualPhases:
    """One operator-controlled loss window, followed by recovery."""

    def __init__(self):
        self.state = "normal"
        self.fault_start = None
        self.fault_end = None

    def apply(self, command, now):
        if command == "on" and self.state == "normal":
            self.fault_start = now
            self.state = "stress"
            return "STRESS ATTIVO: da ora le nuove telemetrie HAR vengono scartate."
        if command == "off" and self.state == "stress":
            self.fault_end = now
            self.state = "recovery"
            return "NORMALE: inoltro HAR ripristinato; osservare il recupero."
        if command == "stop" and self.state == "recovery":
            self.state = "finished"
            return "FINE: raccolta conclusa; verifica e ripristino del controllo ordinario."
        raise ValueError("Usare in ordine: stress on → stress off → stress stop. Nessun cambio automatico.")


def scenario(out, credentials, adaptive, repeat, manual=False):
    session_id = hashlib.sha256(str(out.parent.resolve()).encode()).hexdigest()[:10]
    name = f"hw-{'adaptive' if adaptive else 'baseline'}-{session_id}-{repeat}"
    start = time.time()

    # Each run contains 10 normal seconds, 15 seconds of selective loss, then 15 seconds of recovery
    fault_start, fault_end, end = start + 10, start + 25, start + 40
    records, errors = [], []
    lock = threading.Lock()
    phases = ManualPhases() if manual else None
    fault_started_monotonic = None
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
        with lock:
            now = time.time()
            # Withhold only HAR telemetry; commands and node2 telemetry keep flowing.
            blocked = phases.state == "stress" if manual else fault_start <= now < fault_end
            drop = msg.topic == "activitylink/node1/telemetry" and blocked
        record(
            {
                "time": now,
                "kind": "telemetry",
                "topic": msg.topic,
                "payload": msg.payload.decode(),
                "dropped": drop,
            }
        )
        if not drop:
            relay.publish(msg.topic, msg.payload, qos=0, retain=False)

    def command(client, userdata, msg):
        record(
            {
                "time": time.time(),
                "kind": "command",
                "topic": msg.topic,
                "payload": msg.payload.decode(),
            }
        )

        # Forward backend commands to the real actuator through the ordinary broker
        actual.publish(msg.topic, msg.payload, qos=0, retain=False)

    actual.on_connect, relay.on_connect = actual_connected, relay_connected
    actual.on_subscribe = lambda *args: actual_ready.set()
    relay.on_subscribe = lambda *args: relay_ready.set()
    actual.on_message, relay.on_message = receive, command
    proc = None
    control_server = None
    try:
        relay.connect("127.0.0.1", 18884, 15)
        relay.loop_start()
        actual.connect("::1", 1883, 15)
        actual.loop_start()
        if not actual_ready.wait(5) or not relay_ready.wait(5):
            raise RuntimeError("relay subscription timeout")
        start = time.time()
        fault_start, fault_end, end = start + 10, start + 25, start + 40
        env = dict(
            os.environ,
            PYTHONPATH=os.pathsep.join((str(PYTHON_DEPS), str(ROOT))),
            DB_HOST="127.0.0.1",
            DB_PORT="13306",
            DB_PASSWORD=credentials["app"],
            MQTT_HOST="127.0.0.1",
            MQTT_PORT="18884",
            ADAPTIVE=str(adaptive),
            RUN_ID=name,
        )
        with (out / "cloud.log").open("x") as log:
            proc = subprocess.Popen(
                [sys.executable, "-m", "backend.app"],
                cwd=ROOT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
        if manual:
            CONTROL_SOCKET.unlink(missing_ok=True)
            control_server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            control_server.bind(str(CONTROL_SOCKET))
            CONTROL_SOCKET.chmod(0o600)
            control_server.listen(4)
            print(f"START {name}: MODALITÀ MANUALE, inoltro normale, nessuna scadenza.", flush=True)
            print("Comandi shell: stress on, stress off, stress stop; stress cancel per annullare.", flush=True)
        else:
            print(f"START {name}: fault from +10s to +25s, total 40s", flush=True)
        while (phases.state != "finished" if manual else time.time() < end):
            if proc.poll() is not None:
                raise RuntimeError("experiment backend exited")
            if manual:
                if not select.select([control_server], [], [], 0.2)[0]:
                    continue
                connection, _ = control_server.accept()
                with connection:
                    connection.settimeout(2)
                    with connection.makefile("r") as incoming:
                        command_name = incoming.readline(64).strip()
                    response = {"ok": True, "run_id": name, "results": str(out.parent)}
                    with lock:
                        try:
                            if command_name == "status":
                                message = "Prova attiva"
                            elif command_name == "cancel":
                                message = "Annullamento richiesto; ripristino del controllo ordinario."
                            else:
                                message = phases.apply(command_name, time.time())
                                if command_name == "on":
                                    fault_started_monotonic = time.monotonic()
                                fault_start, fault_end = phases.fault_start, phases.fault_end
                                event = {"time": time.time(), "kind": "phase", "state": phases.state}
                                records.append(event)
                                stream.write(json.dumps(event) + "\n")
                        except ValueError as exc:
                            message = str(exc)
                            response["ok"] = False
                        response.update(message=message, phase=phases.state)
                        response.update(fault_start=phases.fault_start,
                                        fault_started_monotonic=fault_started_monotonic)
                    try:
                        connection.sendall((json.dumps(response) + "\n").encode())
                    except BrokenPipeError:
                        pass
                print(message, flush=True)
                if command_name == "cancel":
                    raise KeyboardInterrupt
            else:
                time.sleep(0.2)
    finally:
        if control_server:
            control_server.close()
            CONTROL_SOCKET.unlink(missing_ok=True)
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
    sensor_before = [
        r
        for r in records
        if r["kind"] == "telemetry"
        and r["topic"] == "activitylink/node1/telemetry"
        and r["time"] < fault_start
    ]
    detection = stale[0]["time"] - sensor_before[-1]["time"] if stale and sensor_before else None
    recovered = any(m["time"] > fault_end + 2 and not m["sensor_stale"] for m in metrics)

    # Assess reported LED states after allowing time for stale detection and propagation
    reported = [
        json.loads(r["payload"])["led"]
        for r in records
        if r["kind"] == "telemetry"
        and r["topic"] == "activitylink/node2/telemetry"
        and fault_start + 9 <= r["time"] < fault_end
    ]
    result = {
        "run_id": name,
        "adaptive": adaptive,
        "manual": manual,
        "start": start,
        "fault_start": fault_start,
        "fault_end": fault_end,
        "end": time.time(),
        "fault_kind": "selective node1 message loss at cloud ingress; actual radio nodes remain active",
        "sensor_messages_dropped": len(dropped),
        "stale_samples": len(stale),
        "stale_command_red": sum(m["command_led"] == 3 for m in stale),
        "reported_leds_during_stale": reported,
        "detection_seconds_from_last_forwarded": detection,
        "recovered": recovered,
        "last_counts": metrics[-1] if metrics else None,
    }
    result["passed"] = bool(
        dropped
        and stale
        and reported
        and recovered
        and metrics[-1]["invalid"] == 0
        and metrics[-1]["queue_drops"] == 0
        and all((m["command_led"] == 3) == bool(adaptive) for m in stale)
        and all((led == 3) == bool(adaptive) for led in reported)
    )
    (out / "summary.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--manual", choices=("baseline", "adaptive"),
                        help="Worker mode controlled by shell commands")
    parser.add_argument("--control", choices=("start", "on", "off", "stop", "status", "cancel"))
    parser.add_argument("--mode", choices=("baseline", "adaptive"), default="baseline")
    args = parser.parse_args()
    if args.control:
        if args.control == "start":
            if not args.out:
                parser.error("--out required with --control start")
            start_manual(args.out.resolve(), args.mode)
        else:
            response = control_request(args.control)
            print(json.dumps(response, ensure_ascii=False), flush=True)
            if args.control == "on":
                try:
                    show_stress_timer(response)
                except KeyboardInterrupt:
                    print("\nTimer interrotto. Lo stress resta attivo: usare stress off per ripristinare.", flush=True)
                    return 130
            if args.control in ("stop", "cancel"):
                # Wait for cleanup, including restoration of the ordinary controller.
                with (STATE / "stress.lock").open("a") as session_lock:
                    deadline = time.monotonic() + 30
                    while True:
                        try:
                            fcntl.flock(session_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            break
                        except BlockingIOError:
                            if time.monotonic() >= deadline:
                                raise RuntimeError("Ripristino ancora in corso: consultare il log della prova")
                            time.sleep(0.2)
                print("Prova chiusa. Controllare il riepilogo e lo stato dei servizi.", flush=True)
                if args.control == "stop":
                    summary_path = Path(response["results"]) / "summary.json"
                    if not summary_path.exists():
                        raise RuntimeError(f"Riepilogo assente: controllare {Path(response['results']).with_suffix('.log')}")
                    summary = json.loads(summary_path.read_text())
                    print(f"Risultato: passed={summary['passed']} — {summary_path}", flush=True)
                    return int(not summary["passed"])
        return 0
    if not args.out:
        parser.error("--out required")
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    # Keep simultaneous stress commands from replacing each other's controller.
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / "stress.lock").open("a") as session_lock:
        try:
            fcntl.flock(session_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("Un'altra prova stress è già in corso")

        def interrupted(signum, frame):
            raise KeyboardInterrupt

        signal.signal(signal.SIGTERM, interrupted)
        args.out.mkdir(parents=True, exist_ok=False)
        credentials = config()
        free_port(18884)
        conf = args.out / "relay-broker.conf"
        conf.write_text("listener 18884 127.0.0.1\nallow_anonymous true\npersistence false\n")
        results = []

        # Avoid a second controller publishing commands while the experiment backend is active
        stop_backend()
        broker = None
        try:
            with (args.out / "relay-broker.log").open("x") as log:
                broker = subprocess.Popen(
                    [
                        str(WORK / "tools/local-broker/build-no-tls/src/mosquitto"),
                        "-c",
                        str(conf.resolve()),
                        "-v",
                    ],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )

            def ready():
                import socket

                with socket.create_connection(("127.0.0.1", 18884), timeout=1):
                    return True

            wait_for(ready, 10)
            for repeat in range(1, (1 if args.manual else args.repeats) + 1):

                # Show baseline first in the demo; alternate order across repeated pairs
                modes = (int(args.manual == "adaptive"),) if args.manual else ((0, 1) if repeat % 2 else (1, 0))
                for adaptive in modes:
                    results.append(
                        scenario(
                            args.out / f"pair-{repeat}-{'adaptive' if adaptive else 'baseline'}",
                            credentials,
                            adaptive,
                            repeat,
                            manual=bool(args.manual),
                        )
                    )
        finally:
            if broker:
                broker.terminate()
                broker.wait(timeout=10)

            # Restore ordinary adaptive control after the experiment, including on failure
            start_backend(credentials, 1, "hardware-native-post-stress")
        summary = {
            "scope": "real MQTT/SQL/actuator, host ingress loss, paired trials; no physical power failure",
            "pairs": 0 if args.manual else args.repeats,
            "manual_mode": args.manual,
            "runs": results,
            "passed": all(r["passed"] for r in results),
        }
        (args.out / "summary.json").write_text(json.dumps(summary, indent=2))
        return int(not summary["passed"])


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Prova interrotta; eseguito il ripristino del controllo ordinario.", flush=True)
        raise SystemExit(130)
    except (OSError, RuntimeError) as exc:
        print(f"Errore: {exc}", file=sys.stderr)
        raise SystemExit(1)
