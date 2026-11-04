import itertools
import json
import queue
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from backend import app


class BackendQueueTests(unittest.TestCase):
    def test_full_queue_counts_drops_and_drains_after_sql_reconnect(self):
        stop = threading.Event()
        connected = threading.Event()
        inbox = queue.Queue(maxsize=1000)
        client = MagicMock()
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = dict(received=app.time.time(), activity=1,
                                           enabled=1, led=1)
        stored_sequences = []

        # Feed the real MQTT callback while the SQL consumer has not started
        def receive_burst():
            client.on_connect(client, None, None,
                              SimpleNamespace(is_failure=False), None)
            for seq in range(1, 1006):
                message = dict(node="node1", boot="0123456789abcdef", seq=seq,
                               uptime=seq, activity=1, enabled=1, led=1)
                client.on_message(client, None, SimpleNamespace(
                    topic="activitylink/node1/telemetry",
                    payload=json.dumps(message).encode(), retain=False))
            self.assertEqual(inbox.qsize(), 1000)

        # Observe FIFO consumption without requiring a real MySQL instance
        def store_message(db, message, received):
            stored_sequences.append(message["seq"])
            if len(stored_sequences) == 1000:
                stop.set()
            return "accepted"

        client.loop_start.side_effect = receive_burst
        ticks = itertools.count(step=2)
        unavailable = app.pymysql.err.OperationalError(2003, "test SQL outage")
        with patch.object(app.mqtt, "Client", return_value=client), \
                patch.object(app.queue, "Queue", return_value=inbox) as make_queue, \
                patch.object(app.threading, "Event", side_effect=[stop, connected]), \
                patch.object(app.signal, "signal"), \
                patch.object(app, "connect_database",
                             side_effect=[unavailable, connection]) as connect, \
                patch.object(app, "store", side_effect=store_message), \
                patch.object(app.time, "monotonic", side_effect=lambda: next(ticks)), \
                patch.object(stop, "wait", return_value=False), \
                patch.object(app.logging, "info"), \
                patch.object(app.logging, "warning"):
            app.main()

        make_queue.assert_called_once_with(maxsize=1000)
        self.assertEqual(connect.call_count, 2)
        self.assertEqual(stored_sequences, list(range(1, 1001)))
        self.assertTrue(inbox.empty())
        metrics = [call.args[1] for call in cursor.execute.call_args_list
                   if call.args[0].startswith("INSERT INTO metrics")]
        self.assertTrue(metrics)

        # Counts are accepted, duplicates, invalid, out_of_order and queue_drops
        self.assertEqual(metrics[-1][-5:], (1000, 0, 0, 0, 5))
        client.disconnect.assert_called_once()
        client.loop_stop.assert_called_once()
        connection.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
