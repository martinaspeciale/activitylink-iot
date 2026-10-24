import argparse,time
import paho.mqtt.client as mqtt
p=argparse.ArgumentParser();p.add_argument('action',choices=['pause','resume']);p.add_argument('--host',default='localhost');a=p.parse_args()
c=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2);c.connect(a.host,1883);c.loop_start();r=c.publish('activitylink/node1/command','P' if a.action=='pause' else 'R');r.wait_for_publish(timeout=5);c.disconnect();c.loop_stop()
print('Command sent; verify the reported enabled field in MySQL/Grafana.')
