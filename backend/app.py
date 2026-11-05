"""MQTT telemetry -> validated SQL rows -> SQL-based feedback control."""

import json
import logging
import os
from pathlib import Path
import queue
import signal
import threading
import time

import paho.mqtt.client as mqtt
import pymysql

from .core import decide, validate

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")


def connect_database():
    connection = pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "activitylink"),
        password=os.environ["DB_PASSWORD"],
        database=os.getenv("DB_NAME", "activitylink"),
        autocommit=True,
        connect_timeout=3,
        read_timeout=3,
        write_timeout=3,
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with connection.cursor() as cursor:

            # The boot ID lets sequence numbers restart after a device reboot
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS telemetry (node VARCHAR(16), boot CHAR(16), seq BIGINT, received DOUBLE NOT NULL, uptime BIGINT, activity INT, enabled INT, led INT, PRIMARY KEY(node,boot,seq), INDEX latest(node,received))"
            )
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS metrics (id BIGINT AUTO_INCREMENT PRIMARY KEY, time DOUBLE, run_id VARCHAR(64), adaptive INT, sensor_stale INT, actuator_stale INT, command_led INT, reported_led INT, accepted BIGINT, duplicates BIGINT, invalid BIGINT, out_of_order BIGINT, queue_drops BIGINT)"
            )
    except Exception:
        connection.close()
        raise
    return connection


def store(connection, message, received):
    """Retry the same identity after an uncertain SQL write."""
    with connection.cursor() as cursor:

        # Check ordering within one node and one boot session
        identity = (message["node"], message["boot"])
        cursor.execute("SELECT MAX(seq) AS seq FROM telemetry WHERE node=%s AND boot=%s", identity)
        last = cursor.fetchone()["seq"]

        # Duplicates and late messages must not refresh the stored receive time
        if last is not None and message["seq"] <= last:
            cursor.execute(
                "SELECT seq FROM telemetry WHERE node=%s AND boot=%s AND seq=%s",
                (*identity, message["seq"]),
            )
            return "duplicates" if cursor.fetchone() else "out_of_order"
        cursor.execute(
            "INSERT INTO telemetry VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                *identity,
                message["seq"],
                received,
                message["uptime"],
                message["activity"],
                message["enabled"],
                message["led"],
            ),
        )
        return "accepted"


def main():
    cfg = json.loads(Path("config/devices.json").read_text())

    # Buffer MQTT input in RAM while SQL is busy; this queue is bounded and not persistent
    inbox = queue.Queue(maxsize=1000)

    # Counters cover both nodes and restart with this backend process
    counts = dict(accepted=0, duplicates=0, invalid=0, out_of_order=0, queue_drops=0)
    stop = threading.Event()
    connected = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="activitylink-cloud")

    def on_connect(c, userdata, flags, reason, properties):
        if not reason.is_failure:
            connected.set()

            # The wildcard receives both nodes; validate() still checks each node/topic pair
            c.subscribe("activitylink/+/telemetry", qos=0)
            logging.info("MQTT connected; telemetry subscription requested")

    def on_disconnect(c, userdata, flags, reason, properties):
        connected.clear()
        logging.warning("MQTT disconnected reason=%s; reconnect enabled", reason)

    def on_message(c, userdata, msg):
        try:

            # Keep SQL work out of the MQTT network callback and timestamp arrival here
            inbox.put_nowait((msg.topic, bytes(msg.payload), time.time(), msg.retain))
        except queue.Full:
            counts["queue_drops"] += 1

    client.on_connect, client.on_disconnect, client.on_message = (
        on_connect,
        on_disconnect,
        on_message,
    )
    client.reconnect_delay_set(min_delay=1, max_delay=5)
    client.connect_async(
        os.getenv("MQTT_HOST", cfg["broker"]), int(os.getenv("MQTT_PORT", cfg["port"])), 30
    )
    client.loop_start()

    # The launch environment selects the mode; the JSON adaptive field is not used
    adaptive = os.getenv("ADAPTIVE", "1") == "1"
    run = os.getenv("RUN_ID", "demo")[:64]
    connection, pending, next_control = None, None, 0
    try:
        while not stop.is_set():
            try:
                if connection is None:
                    connection = connect_database()
                    logging.info("SQL connected; buffered=%s", inbox.qsize())
                if pending is None:
                    try:
                        pending = inbox.get(timeout=0.1)
                    except queue.Empty:
                        pass
                if pending is not None:
                    topic, payload, received, retained = pending
                    try:

                        # A retained replay must not be accepted as a new live observation
                        if retained:
                            raise ValueError("retained telemetry not accepted")
                        message = validate(topic, payload)
                    except (ValueError, TypeError, KeyError):
                        counts["invalid"] += 1
                    else:
                        counts[store(connection, message, received)] += 1

                    # Clear the pending item only after validation or a completed storage attempt
                    pending = None
                if time.monotonic() >= next_control:

                    # This deadline controls both command publication and metric insertion
                    next_control = time.monotonic() + 1
                    now = time.time()
                    with connection.cursor() as cursor:

                        # Read the decision input from SQL, rather than directly from the MQTT callback
                        cursor.execute(
                            "SELECT * FROM telemetry WHERE node=%s ORDER BY received DESC LIMIT 1",
                            (cfg["sensor"],),
                        )
                        sensor = cursor.fetchone()
                        cursor.execute(
                            "SELECT * FROM telemetry WHERE node=%s ORDER BY received DESC LIMIT 1",
                            (cfg["actuator"],),
                        )
                        actuator = cursor.fetchone()
                        led, stale = decide(sensor, now, adaptive, cfg["stale_seconds"])
                        actuator_stale = (
                            actuator is None or now - actuator["received"] > cfg["stale_seconds"]
                        )

                        # Without SQL, stop commands and let the device watchdog take over
                        if connected.is_set():
                            client.publish(
                                f"activitylink/{cfg['actuator']}/command",
                                str(led),
                                qos=0,
                                retain=False,
                            )

                        # A reported LED of -1 means the actuator state is missing or stale
                        cursor.execute(
                            "INSERT INTO metrics (time,run_id,adaptive,sensor_stale,actuator_stale,command_led,reported_led,accepted,duplicates,invalid,out_of_order,queue_drops) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                            (
                                now,
                                run,
                                int(adaptive),
                                int(stale),
                                int(actuator_stale),
                                led,
                                -1 if actuator_stale else actuator["led"],
                                *counts.values(),
                            ),
                        )
                    logging.info(
                        "run=%s sensor_stale=%s command=%s reported=%s counts=%s",
                        run,
                        stale,
                        led,
                        None if actuator_stale else actuator["led"],
                        counts,
                    )

            # Keep the pending message for retry; no new control command is issued without SQL
            except (pymysql.err.OperationalError, pymysql.err.InterfaceError) as exc:
                logging.warning(
                    "SQL unavailable (%s); retaining pending telemetry, retry in 1s",
                    exc.args[0] if exc.args else type(exc).__name__,
                )
                if connection is not None:
                    connection.close()
                connection = None
                stop.wait(1)
    finally:
        client.disconnect()
        client.loop_stop()
        if connection is not None:
            connection.close()
        logging.info(
            "cloud stopped; pending=%s buffered=%s counts=%s",
            pending is not None,
            inbox.qsize(),
            counts,
        )


if __name__ == "__main__":
    main()
