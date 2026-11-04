import json
import unittest
from backend.core import validate, decide


class ProtocolTests(unittest.TestCase):
    def message(self, **changes):
        m = dict(
            node="node1", boot="0123456789abcdef", seq=1, uptime=1, activity=1, enabled=1, led=1
        )
        m.update(changes)
        return m

    def test_invalid_payloads(self):
        good = json.dumps(self.message())
        for payload in [
            b"\xff",
            "[]",
            "null",
            "{",
            "x" * 513,
            good[:-1] + ',"seq":2}',
            good[:-1] + ',"extra":0}',
        ]:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    validate("activitylink/node1/telemetry", payload)

    def test_invalid_types_bounds_and_states(self):
        for change in [
            dict(seq=True),
            dict(seq=0),
            dict(seq=2**32),
            dict(uptime=-1),
            dict(activity=7),
            dict(boot="bad"),
            dict(led=3),
            dict(enabled=0),
            dict(activity=0),
        ]:
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    validate("activitylink/node1/telemetry", json.dumps(self.message(**change)))

    def test_all_sensor_classes_and_pause(self):
        for activity in range(7):
            m = self.message(
                activity=activity,
                enabled=int(activity != 0),
                led=0 if activity == 0 else 1 if activity <= 3 else 2,
            )
            self.assertEqual(validate("activitylink/node1/telemetry", json.dumps(m)), m)

    def test_actuator_contract(self):
        for led in range(4):
            m = self.message(node="node2", activity=0, led=led)
            self.assertEqual(validate("activitylink/node2/telemetry", json.dumps(m)), m)
        for change in [dict(activity=1), dict(enabled=0)]:
            with self.assertRaises(ValueError):
                validate(
                    "activitylink/node2/telemetry",
                    json.dumps(
                        self.message(node="node2", activity=0, **change)
                        if "activity" not in change
                        else self.message(node="node2", **change)
                    ),
                )

    def test_stale_boundary_and_recovery(self):
        row = dict(received=100, activity=4, enabled=1)
        self.assertEqual(decide(row, 106, True), (2, False))
        self.assertEqual(decide(row, 106.001, True), (3, True))
        self.assertEqual(decide(row, 106.001, False), (2, True))
        row["received"] = 107
        self.assertEqual(decide(row, 107, True), (2, False))
