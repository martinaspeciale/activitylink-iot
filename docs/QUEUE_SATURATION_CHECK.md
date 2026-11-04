# Queue saturation check

The individual-project specification requires node failure/intermittence and an
adaptive/baseline comparison (IoT Project 2026, pages 2–3). It does not explicitly
require saturating the backend queue. This is an additional robustness check.

`tests/test_backend_queue.py` exercises the real callbacks and processing loop in
`backend/app.py`, with MQTT and SQL replaced by test objects. It submits 1005 valid
telemetries before consumption begins. The queue keeps 1000 entries and rejects
the remaining 5 without blocking the callback. A simulated SQL connection failure
is followed by reconnection. The consumer drains the first 1000 messages in FIFO
order, and the last metric contains accepted=1000 and queue_drops=5, with the other
rejection counters zero. It also verifies that the queue is empty and connections
are closed on exit.

```sh
source .venv/bin/activate
python -m unittest discover -s tests -p 'test_backend_queue.py' -v
```

This verifies application overflow handling and counter propagation. It does not
measure radio delivery, broker throughput, real SQL recovery latency, or physical
LED behavior. Storage is mocked in this test; SQL behavior is covered separately
by `tests/backend_sql_contract.py`. The queue is in RAM and does not survive a
backend process restart.

Previously archived hardware tests reported queue_drops=0; they did not exercise
the full-queue branch. Their original results are preserved.
