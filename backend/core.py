"""Telemetry validation and feedback policy."""
import json
import re

FIELDS = {"node", "boot", "seq", "uptime", "activity", "enabled", "led"}


# Reject repeated keys instead of silently keeping the last JSON value
def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate JSON field: " + key)
        obj[key] = value
    return obj


def validate(topic, payload):
    if not isinstance(payload, (bytes, str)):
        raise ValueError("expected UTF-8 JSON")
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    if len(raw) > 512:
        raise ValueError("oversized telemetry")

    # Only the exact telemetry schema is accepted; extra fields are rejected too
    m = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    if not isinstance(m, dict) or set(m) != FIELDS:
        raise ValueError("unexpected telemetry fields")

    # The node declared in the payload must match its MQTT topic
    node = m["node"]
    if node not in ("node1", "node2") or topic != f"activitylink/{node}/telemetry":
        raise ValueError("unknown node/topic")
    if not isinstance(m["boot"], str) or not re.fullmatch("[0-9a-f]{16}", m["boot"]):
        raise ValueError("invalid boot")

    # Unsigned 32-bit values range up to 2**32 - 1; seq starts at 1, uptime can be 0
    bounds = {"seq": (1, 2**32 - 1), "uptime": (0, 2**32 - 1),
              "activity": (0, 6), "enabled": (0, 1), "led": (0, 3)}
    for key, (low, high) in bounds.items():

        # Use the exact int type because Python also treats booleans as integers
        if type(m[key]) is not int or not low <= m[key] <= high:
            raise ValueError("invalid " + key)

    # HAR reports its local LED: movement is green, posture is blue, pause is off
    if node == "node1":
        if bool(m["activity"]) != bool(m["enabled"]):
            raise ValueError("inconsistent activity/enabled")
        expected_led = (1 if m["activity"] <= 3 else 2) if m["enabled"] else 0
        if m["led"] != expected_led:
            raise ValueError("inconsistent sensor feedback")

    # The feedback node does not classify activities; mute does not disable telemetry
    elif m["activity"] != 0 or m["enabled"] != 1:
        raise ValueError("invalid actuator state")
    return m


def decide(row, now, adaptive, timeout=6):

    # Freshness uses the backend receive time, not the device uptime
    stale = row is None or now - row["received"] > timeout

    # Adaptive mode signals stale data before considering the last activity
    if stale and adaptive:
        return 3, True

    # Baseline can keep an old state, but cannot infer one when no row exists
    if row is None:
        return 3, True
    if not row["enabled"]:
        return 0, stale
    return (1 if row["activity"] <= 3 else 2), stale
