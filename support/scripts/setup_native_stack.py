"""Download the pinned native Mac services into this project; never use sudo."""

import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
# Local development files are kept outside the presentation tree.
WORK = ROOT / "workspace" if (ROOT / "workspace").is_dir() else ROOT
BASE = WORK / "tools/native-stack"
DOWNLOADS = BASE / "downloads"
PACKAGES = [
    (
        "mysql-8.0.31-macos12-x86_64",
        "https://cdn.mysql.com/archives/mysql-8.0/mysql-8.0.31-macos12-x86_64.tar.gz",
        "f148632c405c0d49c1bd4ee92f3b8bd0705ff0776e82f20fede9f1ee6af10199",
        "bin/mysqld",
    ),
    (
        "grafana-v11.6.0",
        "https://dl.grafana.com/oss/release/grafana-11.6.0.darwin-amd64.tar.gz",
        "f9718154edc42c6ebaf6c760e75b948e983db2f4ce1b9477cd58e33003fe146f",
        "bin/grafana",
    ),
]
if platform.system() != "Darwin" or platform.machine() != "x86_64":
    raise SystemExit(
        "This native setup targets Intel macOS"
    )
DOWNLOADS.mkdir(parents=True, exist_ok=True)
for folder, url, expected, binary in PACKAGES:
    archive = DOWNLOADS / url.rsplit("/", 1)[1]
    if not archive.exists() or hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        partial = archive.with_suffix(archive.suffix + ".part")
        print("Downloading", url, flush=True)
        with urllib.request.urlopen(url, timeout=60) as source, partial.open("wb") as destination:
            while chunk := source.read(1024 * 1024):
                destination.write(chunk)
        assert (
            hashlib.sha256(partial.read_bytes()).hexdigest() == expected
        ), "Archive checksum mismatch"
        os.replace(partial, archive)
    if not (BASE / folder / binary).exists():
        with tarfile.open(archive) as source:
            for member in source.getmembers():
                target = (BASE / member.name).resolve()
                assert target.is_relative_to(BASE.resolve()), "Unsafe archive path"
                if member.issym() or member.islnk():
                    linked = (
                        (target.parent if member.issym() else BASE) / member.linkname
                    ).resolve()
                    assert linked.is_relative_to(BASE.resolve()), "Unsafe archive link"
            source.extractall(BASE, filter="data")
    subprocess.run([str(BASE / folder / binary), "--version"], check=True)
print(json.dumps({"status": "ready", "services": [p[0] for p in PACKAGES]}))
