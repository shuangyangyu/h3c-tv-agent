"""MQTT client for HA switch command/state."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from typing import Any

import paho.mqtt.client as mqtt

from .logging_setup import get_logger
from .models import TVS, TVState, parse_want

log = get_logger("mqtt")


class MqttBridge:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        prefix: str,
        client_id: str,
        on_set: Callable[[str, TVState], None],
    ) -> None:
        self.prefix = prefix.rstrip("/")
        self.on_set = on_set
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
        )
        if username:
            self._client.username_pw_set(username, password or None)
        self._client.will_set(self.status_topic, "offline", qos=1, retain=True)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._host = host
        self._port = port
        self._lock = threading.Lock()

    @property
    def status_topic(self) -> str:
        return f"{self.prefix}/status"

    def state_topic(self, tv: str) -> str:
        return f"{self.prefix}/{tv}/state"

    def attr_topic(self, tv: str) -> str:
        return f"{self.prefix}/{tv}/attr"

    def set_topic(self, tv: str) -> str:
        return f"{self.prefix}/{tv}/set"

    def set_topic_filter(self) -> str:
        return f"{self.prefix}/+/set"

    def discovery_topic(self, tv: str) -> str:
        return f"homeassistant/switch/h3c_tv_{tv}/config"

    def connect(self) -> None:
        self._client.connect(self._host, self._port, keepalive=60)
        self._client.loop_start()

    def stop(self) -> None:
        try:
            self.publish_status("offline")
        except Exception:
            pass
        self._client.loop_stop()
        self._client.disconnect()

    def publish_discovery(self) -> None:
        """Publish Home Assistant MQTT discovery configs (retained)."""
        for key, tv in TVS.items():
            payload = {
                "name": tv.name,
                "unique_id": f"h3c_tv_agent_{key}",
                "state_topic": self.state_topic(key),
                "command_topic": self.set_topic(key),
                "payload_on": "ON",
                "payload_off": "OFF",
                "state_on": "ON",
                "state_off": "OFF",
                "availability_topic": self.status_topic,
                "payload_available": "online",
                "payload_not_available": "offline",
                "qos": 1,
                "retain": False,
                "optimistic": False,
                "device": {
                    "identifiers": ["h3c_tv_agent"],
                    "name": "H3C TV Agent",
                    "manufacturer": "syhome",
                    "model": "S5550 ACL",
                    "sw_version": "0.1.0",
                },
                "json_attributes_topic": self.attr_topic(key),
            }
            self._publish(
                self.discovery_topic(key),
                json.dumps(payload, ensure_ascii=False),
                retain=True,
            )
        log.info("mqtt discovery published", tvs=list(TVS))

    def publish_status(self, status: str) -> None:
        self._publish(self.status_topic, status, retain=True)

    def publish_state(self, tv: str, state: TVState, *, attrs: dict[str, Any] | None = None) -> None:
        self._publish(self.state_topic(tv), state, retain=True)
        if attrs is not None:
            self._publish(self.attr_topic(tv), json.dumps(attrs, ensure_ascii=False), retain=True)

    def publish_all_states(self, states: dict[str, TVState]) -> None:
        for tv, state in states.items():
            tv_cfg = TVS.get(tv)
            attrs = {
                "name": tv_cfg.name if tv_cfg else tv,
                "ip": tv_cfg.ip if tv_cfg else "",
                "deny_rule": tv_cfg.deny_rule if tv_cfg else None,
            }
            self.publish_state(tv, state, attrs=attrs)

    def _publish(self, topic: str, payload: str, *, retain: bool = False) -> None:
        with self._lock:
            info = self._client.publish(topic, payload, qos=1, retain=retain)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            log.warning("mqtt publish failed", topic=topic, rc=info.rc)

    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        # paho-mqtt v2: reason_code is a ReasonCode object
        rc_value = getattr(reason_code, "value", reason_code)
        try:
            rc_int = int(rc_value)
        except Exception:
            rc_int = 0 if str(reason_code) in {"Success", "0"} else 1
        if rc_int != 0:
            log.error("mqtt connect failed", reason_code=str(reason_code))
            return
        client.subscribe(self.set_topic_filter(), qos=1)
        self.publish_status("online")
        self.publish_discovery()
        log.info("mqtt connected", host=self._host, prefix=self.prefix)

    def _on_message(self, client, userdata, msg) -> None:
        topic = msg.topic
        parts = topic.split("/")
        # h3c/tv/{tv}/set
        if len(parts) < 3 or parts[-1] != "set":
            return
        tv = parts[-2]
        if tv not in TVS:
            log.warning("mqtt unknown tv", tv=tv, topic=topic)
            return
        want = parse_want(msg.payload)
        if want is None:
            log.warning("mqtt bad payload", tv=tv, payload=repr(msg.payload))
            return
        log.info("mqtt command", tv=tv, action="set", state=want, result="queued")
        self.on_set(tv, want)
