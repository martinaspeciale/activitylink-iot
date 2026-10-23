#include "contiki.h"
#include "mqtt.h"
#include "dev/leds.h"
#include "dev/button-hal.h"
#include "lib/random.h"
#include "sys/rtimer.h"
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#ifndef NODE_ROLE
#define NODE_ROLE 1
#endif
#if NODE_ROLE == 1
#include "model.h"
#include "samples.h"
#define NODE_NAME "node1"
#else
#define NODE_NAME "node2"
#endif
PROCESS(activitylink_process,"ActivityLink MQTT node");
AUTOSTART_PROCESSES(&activitylink_process);
static struct mqtt_connection conn;
static struct etimer tick;
static char payload[240],boot[17];
static uint32_t seq;
static unsigned activity,led,enabled=1,connected,subscribed;
static unsigned last_connect;
#if NODE_ROLE == 1
static unsigned sample_idx;
#else
static unsigned muted,last_command;
#endif
static void set_led(unsigned v) {
  led=v; leds_off(LEDS_ALL);
  if(v==1) leds_on(LEDS_GREEN);
  else if(v==2) leds_on(LEDS_BLUE);
  else if(v==3) leds_on(LEDS_RED);
}
static void event(struct mqtt_connection *m,mqtt_event_t ev,void *data) {
  (void)m;
  if(ev==MQTT_EVENT_CONNECTED) { connected=1; subscribed=0; printf("AL connected node=%s\n",NODE_NAME); }
  if(ev==MQTT_EVENT_DISCONNECTED || ev==MQTT_EVENT_CONNECTION_REFUSED_ERROR) {connected=0;subscribed=0;printf("AL disconnected node=%s event=%u\n",NODE_NAME,(unsigned)ev);}
  if(ev==MQTT_EVENT_PUBLISH) {
    struct mqtt_message *msg=data;
    /* Commands contain one ASCII byte. */
    if(msg->payload_length==1 && msg->payload_chunk_length==1) {
      char c=msg->payload_chunk[0];
      printf("AL command node=%s byte=%u\n",NODE_NAME,(unsigned char)c);
#if NODE_ROLE == 1
      if(c=='P') enabled=0;
      if(c=='R') enabled=1;
#else
      if(c>='0' && c<='3') {last_command=clock_seconds();if(!muted) set_led(c-'0');}
#endif
    }
  }
}
PROCESS_THREAD(activitylink_process,ev,data) {
  PROCESS_BEGIN();
  snprintf(boot,sizeof(boot),"%04x%04x%04x%04x",random_rand(),random_rand(),random_rand(),random_rand());
  mqtt_register(&conn,&activitylink_process,"activitylink-" NODE_NAME,event,128);
  conn.auto_reconnect=0;
  printf("AL boot node=%s boot=%s rtimer_hz=%lu\n",NODE_NAME,boot,(unsigned long)RTIMER_SECOND);
  last_connect=(unsigned)-10;
  etimer_set(&tick,CLOCK_SECOND);
  while(1) {
    PROCESS_WAIT_EVENT();
    /* Toggle on press; only log release. */
    if(ev==button_hal_release_event) {
      printf("AL button node=%s event=release\n",NODE_NAME);
    }
    if(ev==button_hal_press_event) {
#if NODE_ROLE == 1
      enabled=!enabled;
      if(!enabled) {activity=0;set_led(0);}
      printf("AL button node=%s event=press enabled=%u\n",NODE_NAME,enabled);
#else
      muted=!muted; if(muted) set_led(0);
      printf("AL button node=%s event=press muted=%u\n",NODE_NAME,muted);
#endif
    }
    if(ev==PROCESS_EVENT_TIMER && data==&tick) {
      etimer_reset(&tick);
      if(!connected && clock_seconds()-last_connect>=5) {
        last_connect=clock_seconds();
        mqtt_connect(&conn,BROKER_IP,1883,15,MQTT_CLEAN_SESSION_ON);
      }
#if NODE_ROLE == 1
      if(enabled) {
        rtimer_clock_t started=RTIMER_NOW();
        activity=har_predict(samples[sample_idx]);
        rtimer_clock_t elapsed=(rtimer_clock_t)(RTIMER_NOW()-started);
        printf("AL inference sample=%u class=%u ticks=%lu\n",sample_idx,activity,(unsigned long)elapsed);
        sample_idx=(sample_idx+1)%SAMPLE_COUNT;set_led(activity<=3?1:2);
      } else {activity=0;set_led(0);}
#else
      if(!muted && clock_seconds()-last_command>8) set_led(3);
#endif
      if(connected && mqtt_ready(&conn) && conn.out_buffer_sent) {
        if(!subscribed) {
          if(mqtt_subscribe(&conn,NULL,"activitylink/" NODE_NAME "/command",MQTT_QOS_LEVEL_0)==MQTT_STATUS_OK) subscribed=1;
        } else {
          ++seq;
          snprintf(payload,sizeof(payload),"{\"node\":\"%s\",\"boot\":\"%s\",\"seq\":%lu,\"uptime\":%lu,\"activity\":%u,\"enabled\":%u,\"led\":%u}",NODE_NAME,boot,(unsigned long)seq,(unsigned long)clock_seconds(),activity,enabled,led);
          mqtt_status_t status=mqtt_publish(&conn,NULL,"activitylink/" NODE_NAME "/telemetry",(uint8_t *)payload,strlen(payload),MQTT_QOS_LEVEL_0,MQTT_RETAIN_OFF);
          printf("AL publish node=%s seq=%lu status=%u activity=%u led=%u\n",NODE_NAME,(unsigned long)seq,(unsigned)status,activity,led);
        }
      }
    }
  }
  PROCESS_END();
}
