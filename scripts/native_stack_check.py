"""Verify native SQL/Grafana against actual hardware telemetry, without commands."""

import argparse
import base64
import json
import time
import urllib.request
from pathlib import Path

import paho.mqtt.client as mqtt
from native_stack import db, config, wait_for


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--run-id", default="hardware-native-20261102")
    parser.add_argument(
        "--commands", action="store_true", help="verify pause/resume through SQL and cloud feedback"
    )
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    credentials = config()
    command_checks = []

    # This optional check sends real pause/resume commands, rather than only reading status
    if args.commands:
        with db(credentials, user="activitylink", database="activitylink") as connection:
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT enabled FROM telemetry WHERE node='node1' ORDER BY received DESC LIMIT 1"
                )
                initial_enabled = cur.fetchone()["enabled"]
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id="activitylink-native-control-check"
        )
        client.connect("::1", 1883, 15)
        client.loop_start()
        try:
            for value, enabled in (("P", 0), ("R", 1)):
                sent = time.time()
                client.publish(
                    "activitylink/node1/command", value.encode(), qos=0, retain=False
                ).wait_for_publish(5)

                # Require new sensor and actuator telemetry after the command, not old SQL rows
                def confirmed():
                    with db(
                        credentials, user="activitylink", database="activitylink"
                    ) as connection:
                        with connection.cursor() as cur:
                            cur.execute(
                                "SELECT * FROM telemetry WHERE node='node1' ORDER BY received DESC LIMIT 1"
                            )
                            sensor = cur.fetchone()
                            cur.execute(
                                "SELECT * FROM telemetry WHERE node='node2' ORDER BY received DESC LIMIT 1"
                            )
                            actuator = cur.fetchone()
                            cur.execute("SELECT * FROM metrics ORDER BY id DESC LIMIT 1")
                            metric = cur.fetchone()
                    if not (
                        sensor["received"] > sent
                        and sensor["enabled"] == enabled
                        and actuator["received"] > sent
                        and metric["time"] > sent
                        and metric["command_led"] in ((1, 2) if enabled else (0,))
                        and actuator["led"] == metric["command_led"]
                    ):
                        raise ValueError("waiting for SQL and physical node feedback")
                    return {
                        "command": value,
                        "sensor": sensor,
                        "actuator": actuator,
                        "metric": metric,
                    }

                command_checks.append(wait_for(confirmed, 10))
        finally:

            # Restore the HAR enabled state observed before the check
            client.publish(
                "activitylink/node1/command", b"R" if initial_enabled else b"P"
            ).wait_for_publish(5)
            client.disconnect()
            client.loop_stop()
    auth = "Basic " + base64.b64encode(("admin:" + credentials["grafana_admin"]).encode()).decode()

    def api(path, data=None):
        request = urllib.request.Request(
            "http://127.0.0.1:3000" + path,
            data=None if data is None else json.dumps(data).encode(),
            headers={"Authorization": auth, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)

    with db(credentials, user="activitylink", database="activitylink") as connection:
        with connection.cursor() as cur:
            cur.execute(
                "SELECT node,COUNT(*) AS count,MAX(received) AS latest FROM telemetry GROUP BY node"
            )
            nodes = cur.fetchall()
            assert len(nodes) == 2 and all(time.time() - n["latest"] < 5 for n in nodes), nodes
            cur.execute("SELECT * FROM metrics WHERE run_id=%s ORDER BY id", (args.run_id,))
            metrics = cur.fetchall()
            assert len(metrics) > 5, metrics
            assert metrics[-1]["accepted"] > 10 and metrics[-1]["invalid"] == 0, metrics[-1]
    (args.out / "metrics.json").write_text(json.dumps(metrics, indent=2))
    health = api("/api/health")
    source = api("/api/datasources/uid/activitylink-mysql/health")
    assert source["status"] == "OK", source
    dashboard = api("/api/dashboards/uid/activitylink")
    panels = []
    for panel in dashboard["dashboard"]["panels"]:
        query = panel["targets"][0].copy()
        query["rawSql"] = query["rawSql"].replace(
            "${run_id:sqlstring}", "'" + args.run_id.replace("'", "''") + "'"
        )
        query.update(
            datasource={"type": "mysql", "uid": "activitylink-mysql"},
            intervalMs=1000,
            maxDataPoints=1000,
        )
        result = api(
            "/api/ds/query",
            {
                "queries": [query],
                "from": str(int(metrics[0]["time"] * 1000) - 1000),
                "to": str(int(metrics[-1]["time"] * 1000) + 1000),
            },
        )["results"]["A"]
        assert not result.get("error"), result
        count = sum(
            len(frame.get("data", {}).get("values", [[]])[0]) for frame in result.get("frames", [])
        )
        assert count > 0, result
        for frame in result.get("frames", []):
            for field, values in zip(frame["schema"]["fields"], frame["data"]["values"]):
                if field["type"] == "time":
                    assert all(
                        metrics[0]["time"] * 1000 - 1000
                        <= value
                        <= metrics[-1]["time"] * 1000 + 1000
                        for value in values
                    ), "Grafana returned shifted timestamps"
        panels.append({"title": panel["title"], "rows": count, "passed": True})
    evidence = {
        "nodes": nodes,
        "latest_metric": metrics[-1],
        "command_checks": command_checks,
        "grafana": health,
        "datasource": source,
        "panels": panels,
        "scope": "actual hardware MQTT/SQL and Grafana API; browser rendering not checked",
    }
    with (args.out / "summary.json").open("x") as stream:
        json.dump(evidence, stream, indent=2)
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
