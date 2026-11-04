"""Read the observed dongle ports and print assignments for the shell."""
import json
from pathlib import Path
import shlex

ROOT = Path(__file__).resolve().parents[1]
hardware = json.loads((ROOT / "config/hardware.json").read_text())
ports = {node["role"]: node["application_port"] for node in hardware["nodes"]}
names = {"HAR": "HAR", "feedback": "FEEDBACK", "border-router": "BORDER_ROUTER"}

assignments = [f"export {name}={shlex.quote(ports[role])}"
               for role, name in names.items()]
print("\n".join(assignments))
