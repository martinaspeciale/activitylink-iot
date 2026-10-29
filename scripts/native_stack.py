"""Manage the local Mosquitto, MySQL, backend and Grafana processes."""
import argparse
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import time
import urllib.request

import pymysql

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "runtime/native-stack"
MYSQL = ROOT / "tools/native-stack/mysql-8.0.31-macos12-x86_64"
GRAFANA = ROOT / "tools/native-stack/grafana-v11.6.0"
PYTHON_DEPS = ROOT / "tools/python-deps"
SIGNATURES = {"mysql": str(MYSQL / "bin/mysqld"), "grafana": str(GRAFANA / "bin/grafana"),
              "cloud": "-m backend.app", "broker": "tools/local-broker/build-no-tls/src/mosquitto"}


def config():
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = STATE / "credentials.json"
    if not path.exists():
        data = {name: secrets.token_hex(24) for name in ("root", "app", "grafana_db", "grafana_admin")}
        with open(path, "x", opener=lambda p, flags: os.open(p, flags, 0o600)) as stream:
            json.dump(data, stream, indent=2)
    return json.loads(path.read_text())


def pid(name):
    path = STATE / f"{name}.pid"
    if not path.exists():
        return None
    value = int(path.read_text())
    result = subprocess.run(["ps", "-p", str(value), "-o", "command="], capture_output=True, text=True)
    return value if result.returncode == 0 and SIGNATURES[name] in result.stdout else None


def launch(name, command, env=None):
    existing = pid(name)
    if existing:
        return existing
    stamp = time.strftime("%Y%m%d-%H%M%S")
    with (STATE / f"{name}-{stamp}.log").open("x") as log:
        proc = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log,
                                stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                start_new_session=True)
    (STATE / f"{name}.pid").write_text(str(proc.pid))
    return proc.pid


def db(credentials, user="root", database=None):
    return pymysql.connect(host="127.0.0.1", port=13306, user=user,
                           password=credentials["root" if user == "root" else "app"],
                           database=database, autocommit=True, connect_timeout=2,
                           cursorclass=pymysql.cursors.DictCursor)


def wait_for(check, seconds=60):
    deadline = time.monotonic() + seconds
    last = None
    while time.monotonic() < deadline:
        try:
            return check()
        except (OSError, ValueError, pymysql.MySQLError) as exc:
            last = exc
            time.sleep(0.3)
    raise RuntimeError(f"Service readiness timeout: {last}")


def free_port(port):
    with socket.socket() as sock:
        if sock.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError(f"Port {port} already belongs to an unmanaged service")


def start_broker():
    if pid("broker"):
        return
    existing = subprocess.run(["lsof", "-t", "-iTCP:1883", "-sTCP:LISTEN"], capture_output=True, text=True)
    owners = set(existing.stdout.split())
    if owners:
        if len(owners) != 1:
            raise RuntimeError("Multiple owners of MQTT port")
        value = int(owners.pop())
        command = subprocess.check_output(["ps", "-p", str(value), "-o", "command="], text=True)
        if SIGNATURES["broker"] not in command or "infra/mosquitto.conf" not in command:
            raise RuntimeError("MQTT port belongs to an unmanaged broker")
        (STATE / "broker.pid").write_text(str(value))
        return
    launch("broker", [str(ROOT / SIGNATURES["broker"]), "-c", str(ROOT / "infra/mosquitto.conf"), "-v"])
    def ready():
        with socket.create_connection(("127.0.0.1", 1883), timeout=1):
            return True
    wait_for(ready, 10)


def stop_service(name):
    value = pid(name)
    if value:
        os.kill(value, signal.SIGTERM)
        def stopped():
            if pid(name):
                raise ValueError(f"{name} still running")
            return True
        wait_for(stopped, 20)


def start_mysql(credentials):
    if pid("mysql"):
        with db(credentials):
            return
    free_port(13306)
    data = STATE / "mysql-data"
    common = [str(MYSQL / "bin/mysqld"), "--no-defaults", f"--basedir={MYSQL}", f"--datadir={data}"]
    if not data.exists():
        with (STATE / "mysql-initialize.log").open("x") as log:
            subprocess.run(common + ["--initialize-insecure"], stdout=log, stderr=subprocess.STDOUT, check=True)
    launch("mysql", common + ["--bind-address=127.0.0.1", "--port=13306", "--mysqlx=OFF",
                              f"--socket={STATE / 'mysql.sock'}", f"--pid-file={STATE / 'mysqld-server.pid'}",
                              "--innodb-buffer-pool-size=64M", "--max-connections=30"])

    def ready():
        try:
            return db(credentials)
        except pymysql.err.OperationalError as exc:
            if exc.args[0] != 1045:
                raise
            return pymysql.connect(host="127.0.0.1", port=13306, user="root", autocommit=True)

    with wait_for(ready) as connection:
        with connection.cursor() as cur:
            cur.execute("ALTER USER 'root'@'localhost' IDENTIFIED BY %s", (credentials["root"],))
            cur.execute("CREATE DATABASE IF NOT EXISTS activitylink")
            for user, key in (("activitylink", "app"), ("activitylink_grafana", "grafana_db")):
                cur.execute(f"CREATE USER IF NOT EXISTS '{user}'@'127.0.0.1' IDENTIFIED BY %s", (credentials[key],))
            cur.execute("GRANT ALL ON activitylink.* TO 'activitylink'@'127.0.0.1'")
            cur.execute("GRANT SELECT ON activitylink.* TO 'activitylink_grafana'@'127.0.0.1'")


def start_cloud(credentials, adaptive, run_id):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join((str(PYTHON_DEPS), str(ROOT))),
               DB_HOST="127.0.0.1", DB_PORT="13306", DB_PASSWORD=credentials["app"],
               MQTT_HOST="::1", ADAPTIVE=str(adaptive), RUN_ID=run_id, PYTHONUNBUFFERED="1")
    launch("cloud", [sys.executable, "-m", "backend.app"], env)


def stop_cloud():
    stop_service("cloud")


def start_grafana(credentials):
    prov = STATE / "provisioning"
    for kind in ("datasources", "dashboards"):
        (prov / kind).mkdir(parents=True, exist_ok=True)
    source = {"apiVersion": 1, "datasources": [{"name": "ActivityLink MySQL", "uid": "activitylink-mysql",
              "type": "mysql", "url": "127.0.0.1:13306", "user": "activitylink_grafana",
              "jsonData": {"database": "activitylink", "maxOpenConns": 5, "timezone": "+00:00"},
              "secureJsonData": {"password": "$MYSQL_PASSWORD"}}]}
    provider = {"apiVersion": 1, "providers": [{"name": "ActivityLink", "type": "file",
                "options": {"path": str(ROOT / "infra/grafana/dashboards")}}]}
    (prov / "datasources/mysql.yaml").write_text(json.dumps(source))
    (prov / "dashboards/default.yaml").write_text(json.dumps(provider))
    if pid("grafana"):
        return
    free_port(3000)
    env = dict(os.environ, GF_SERVER_HTTP_ADDR="127.0.0.1", GF_SERVER_HTTP_PORT="3000",
               GF_PATHS_DATA=str(STATE / "grafana-data"), GF_PATHS_LOGS=str(STATE / "grafana-logs"),
               GF_PATHS_PLUGINS=str(STATE / "grafana-plugins"), GF_PATHS_PROVISIONING=str(prov),
               GF_SECURITY_ADMIN_PASSWORD=credentials["grafana_admin"], MYSQL_PASSWORD=credentials["grafana_db"],
               GF_ANALYTICS_REPORTING_ENABLED="false", GF_ANALYTICS_CHECK_FOR_UPDATES="false",
               GF_ANALYTICS_CHECK_FOR_PLUGIN_UPDATES="false", GF_PLUGINS_PREINSTALL_DISABLED="true")
    launch("grafana", [str(GRAFANA / "bin/grafana"), "server", "--homepath", str(GRAFANA)], env)
    wait_for(lambda: json.load(urllib.request.urlopen("http://127.0.0.1:3000/api/health", timeout=3)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "status", "stop-cloud", "start-cloud", "restart-mysql", "restart-broker"))
    parser.add_argument("--adaptive", type=int, choices=(0, 1), default=1)
    parser.add_argument("--run-id", default="hardware-native")
    args = parser.parse_args()
    credentials = config()
    if args.action == "stop-cloud":
        stop_cloud()
    elif args.action == "restart-mysql":
        stop_service("mysql")
        start_mysql(credentials)
    elif args.action == "restart-broker":
        start_broker()
        stop_service("broker")
        start_broker()
    elif args.action in ("start", "start-cloud"):
        start_broker()
        start_mysql(credentials)
        start_cloud(credentials, args.adaptive, args.run_id)
        if args.action == "start":
            start_grafana(credentials)
    print(json.dumps({name: pid(name) for name in SIGNATURES}))
    print("Grafana: http://127.0.0.1:3000/d/activitylink — admin; password in runtime/native-stack/credentials.json")


if __name__ == "__main__":
    main()
