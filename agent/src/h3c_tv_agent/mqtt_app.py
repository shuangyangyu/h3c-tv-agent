"""MQTT client for HA switch command/state (access + policy route)."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from typing import Any, Literal

import paho.mqtt.client as mqtt

from .logging_setup import get_logger
from .models import (
    ACCESS_KEYS,
    POLICY_ROUTE_KEYS,
    TVState,
    access_devices,
    parse_want,
    policy_route_devices,
)

log = get_logger("mqtt")

ControlKind = Literal["access", "route"]
OnSetFn = Callable[[str, TVState, ControlKind], None]


def _mac_slug(mac: str) -> str:
    """ASCII id for HA discovery object_id / unique_id (中文 key 不能进 topic 段)."""
    return "".join(c for c in mac.lower() if c.isalnum())


def _net_icon(state: TVState | None) -> str:
    # ON=通；OFF=断（HA 还会对 inactive 实体做暗色）
    return "mdi:lan-connect" if state != "OFF" else "mdi:lan-disconnect"


def _prb_icon(state: TVState | None) -> str:
    # ON=走策略/出境；OFF=本网直连（alt-route 在部分 HA/MDI 版本不显示）
    return "mdi:earth" if state != "OFF" else "mdi:earth-off"


class MqttBridge:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        prefix: str,
        route_prefix: str,
        client_id: str,
        on_set: OnSetFn,
    ) -> None:
        self.prefix = prefix.rstrip("/")
        self.route_prefix = route_prefix.rstrip("/")
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
        self._device = {
            "identifiers": ["h3c_tv_agent"],
            "name": "H3C Network Agent",
            "manufacturer": "syhome",
            "model": "S5550 ACL",
            "sw_version": "0.3.1",
        }

    @property
    def status_topic(self) -> str:
        return f"{self.prefix}/status"

    def state_topic(self, tv: str) -> str:
        return f"{self.prefix}/{tv}/state"

    def attr_topic(self, tv: str) -> str:
        return f"{self.prefix}/{tv}/attr"

    def set_topic(self, tv: str) -> str:
        return f"{self.prefix}/{tv}/set"

    def route_state_topic(self, key: str) -> str:
        return f"{self.route_prefix}/{key}/state"

    def route_attr_topic(self, key: str) -> str:
        return f"{self.route_prefix}/{key}/attr"

    def route_set_topic(self, key: str) -> str:
        return f"{self.route_prefix}/{key}/set"

    def discovery_topic(self, mac: str) -> str:
        return f"homeassistant/switch/h3c_tv_{_mac_slug(mac)}/config"

    def route_discovery_topic(self, mac: str) -> str:
        return f"homeassistant/switch/h3c_route_{_mac_slug(mac)}/config"

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

    def _access_discovery_payload(self, key: str, state: TVState | None = None) -> dict[str, Any]:
        tv = access_devices()[key]
        slug = _mac_slug(tv.mac)
        return {
            "name": f"NET_{tv.name}",
            "unique_id": f"h3c_tv_agent_{slug}",
            "object_id": f"h3c_tv_{slug}",
            "icon": _net_icon(state),
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
            "device": self._device,
            "json_attributes_topic": self.attr_topic(key),
        }

    def _route_discovery_payload(self, key: str, state: TVState | None = None) -> dict[str, Any]:
        tv = policy_route_devices()[key]
        slug = _mac_slug(tv.mac)
        return {
            "name": f"PRB_{tv.name}",
            "unique_id": f"h3c_route_agent_{slug}",
            "object_id": f"h3c_route_{slug}",
            "icon": _prb_icon(state),
            "state_topic": self.route_state_topic(key),
            "command_topic": self.route_set_topic(key),
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
            "device": self._device,
            "json_attributes_topic": self.route_attr_topic(key),
        }

    def publish_discovery(self) -> None:
        for key in access_devices():
            tv = access_devices()[key]
            self._publish(
                self.discovery_topic(tv.mac),
                json.dumps(self._access_discovery_payload(key), ensure_ascii=False),
                retain=True,
            )
        for key in policy_route_devices():
            tv = policy_route_devices()[key]
            self._publish(
                self.route_discovery_topic(tv.mac),
                json.dumps(self._route_discovery_payload(key), ensure_ascii=False),
                retain=True,
            )
        log.info(
            "mqtt discovery published",
            access=list(ACCESS_KEYS),
            policy_route=list(POLICY_ROUTE_KEYS),
        )

    def publish_status(self, status: str) -> None:
        self._publish(self.status_topic, status, retain=True)

    def publish_state(
        self, tv: str, state: TVState, *, attrs: dict[str, Any] | None = None
    ) -> None:
        self._publish(self.state_topic(tv), state, retain=True)
        if attrs is not None:
            self._publish(self.attr_topic(tv), json.dumps(attrs, ensure_ascii=False), retain=True)
        # 随状态换图标（MQTT Switch 无原生 icon_on/off）
        cfg = access_devices().get(tv)
        if cfg is not None:
            self._publish(
                self.discovery_topic(cfg.mac),
                json.dumps(self._access_discovery_payload(tv, state), ensure_ascii=False),
                retain=True,
            )

    def publish_route_state(
        self, key: str, state: TVState, *, attrs: dict[str, Any] | None = None
    ) -> None:
        self._publish(self.route_state_topic(key), state, retain=True)
        if attrs is not None:
            self._publish(
                self.route_attr_topic(key),
                json.dumps(attrs, ensure_ascii=False),
                retain=True,
            )
        cfg = policy_route_devices().get(key)
        if cfg is not None:
            self._publish(
                self.route_discovery_topic(cfg.mac),
                json.dumps(self._route_discovery_payload(key, state), ensure_ascii=False),
                retain=True,
            )

    def publish_all_states(self, states: dict[str, TVState]) -> None:
        tvs = access_devices()
        for tv, state in states.items():
            tv_cfg = tvs.get(tv)
            attrs = {
                "name": tv_cfg.name if tv_cfg else tv,
                "ip": tv_cfg.ip if tv_cfg else "",
                "deny_rule": tv_cfg.deny_rule if tv_cfg else None,
                "control": "access",
            }
            self.publish_state(tv, state, attrs=attrs)

    def publish_all_route_states(self, states: dict[str, TVState]) -> None:
        tvs = policy_route_devices()
        for key, state in states.items():
            tv_cfg = tvs.get(key)
            attrs = {
                "name": tv_cfg.name if tv_cfg else key,
                "ip": tv_cfg.ip if tv_cfg else "",
                "route_rule": tv_cfg.route_rule if tv_cfg else None,
                "control": "route",
            }
            self.publish_route_state(key, state, attrs=attrs)

    def _publish(self, topic: str, payload: str, *, retain: bool = False) -> None:
        with self._lock:
            info = self._client.publish(topic, payload, qos=1, retain=retain)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            log.warning("mqtt publish failed", topic=topic, rc=info.rc)

    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        rc_value = getattr(reason_code, "value", reason_code)
        try:
            rc_int = int(rc_value)
        except Exception:
            rc_int = 0 if str(reason_code) in {"Success", "0"} else 1
        if rc_int != 0:
            log.error("mqtt connect failed", reason_code=str(reason_code))
            return
        client.subscribe(f"{self.prefix}/+/set", qos=1)
        client.subscribe(f"{self.route_prefix}/+/set", qos=1)
        self.publish_status("online")
        self.publish_discovery()
        log.info(
            "mqtt connected",
            host=self._host,
            prefix=self.prefix,
            route_prefix=self.route_prefix,
        )

    def _on_message(self, client, userdata, msg) -> None:
        topic = msg.topic
        parts = topic.split("/")
        if len(parts) < 3 or parts[-1] != "set":
            return
        key = parts[-2]
        want = parse_want(msg.payload)
        if want is None:
            log.warning("mqtt bad payload", key=key, payload=repr(msg.payload))
            return

        if topic.startswith(self.route_prefix + "/") and key in POLICY_ROUTE_KEYS:
            log.info("mqtt command", tv=key, action="set_route", state=want, result="queued")
            self.on_set(key, want, "route")
            return
        if topic.startswith(self.prefix + "/") and key in ACCESS_KEYS:
            log.info("mqtt command", tv=key, action="set", state=want, result="queued")
            self.on_set(key, want, "access")
            return
        log.warning("mqtt set ignored", key=key, topic=topic)
