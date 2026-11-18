import argparse
import time

import paho.mqtt.client as mqtt

# The user selects a HAR command; the broker host can be overridden from the terminal
p = argparse.ArgumentParser()
p.add_argument('action', choices=['pause', 'resume'])
p.add_argument('--host', default='localhost')
a = p.parse_args()

# Send one ASCII byte (P or R), with the default QoS 0 and retain=False
c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
c.connect(a.host, 1883)
c.loop_start()
r = c.publish('activitylink/node1/command', 'P' if a.action == 'pause' else 'R')
r.wait_for_publish(timeout=5)
c.disconnect()
c.loop_stop()

# Publishing does not confirm execution; the next telemetry must report the requested state
expected = 0 if a.action == 'pause' else 1
state = 'paused' if a.action == 'pause' else 'running'
print(
    f'Command sent. Check telemetry with ./scripts/demo.sh watch. '
    f'Expected on HAR (node1): enabled={expected} ({state}).'
)
