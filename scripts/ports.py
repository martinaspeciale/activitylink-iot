"""Read the observed dongle ports and print assignments for the shell."""
import json
from pathlib import Path
import shlex

# Resolve the inventory from this script location, regardless of the current directory.
ROOT = Path(__file__).resolve().parents[1]
hardware = json.loads((ROOT / "config/hardware.json").read_text())
ports = {node["role"]: node["application_port"] for node in hardware["nodes"]}
# Keep observed role names in the JSON and expose readable shell variable names.
names = {"HAR": "HAR", "feedback": "FEEDBACK", "border-router": "BORDER_ROUTER"}

# Print shell assignments for source <(python scripts/ports.py); Python cannot update its parent shell.
assignments = [f"export {name}={shlex.quote(ports[role])}"
               for role, name in names.items()]
print("\n".join(assignments))
