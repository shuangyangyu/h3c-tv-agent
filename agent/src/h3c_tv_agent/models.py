"""Device inventory + which keys use access vs policy-route."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

AccessState = Literal["ON", "OFF"]
TVState = AccessState
WantState = AccessState


@dataclass(frozen=True)
class DeviceConfig:
    """身份：YAML；通断/策略路由规则号由 inventory 分配。"""

    key: str
    name: str
    ip: str
    mac: str
    permit_rule: int = 0  # ACL 3000 permit（对照）
    deny_rule: int = 0  # ACL 3000 deny → 通断 OFF
    route_rule: int = 0  # ACL 3001 permit → 策略路由 ON


TVConfig = DeviceConfig


def _builtin_devices() -> dict[str, DeviceConfig]:
    rows = [
        ("master_bedroom", "主卧电视", "192.168.1.24", "cc98-8b23-abaa", 10, 15),
        ("living_room", "客厅电视", "192.168.1.25", "88c9-e8d1-bcb0", 20, 25),
        ("elder_room", "老人房电视", "192.168.1.26", "cc98-8b36-afc7", 30, 35),
        ("study_room", "书房电视", "192.168.1.27", "7026-05e6-0afd", 40, 45),
    ]
    return {
        key: DeviceConfig(key=key, name=name, ip=ip, mac=mac, permit_rule=pr, deny_rule=dr)
        for key, name, ip, mac, pr, dr in rows
    }


DEVICES: dict[str, DeviceConfig] = _builtin_devices()
TVS = DEVICES
DEFAULT_DEVICES: dict[str, DeviceConfig] = dict(DEVICES)
DEFAULT_TVS = DEFAULT_DEVICES

# 通断 / 策略路由引用的 key（由 inventory 填充）
ACCESS_KEYS: list[str] = list(DEVICES.keys())
POLICY_ROUTE_KEYS: list[str] = []
DEFAULT_ACCESS_KEYS: list[str] = list(ACCESS_KEYS)
DEFAULT_POLICY_ROUTE_KEYS: list[str] = []


@dataclass(frozen=True)
class InventoryPolicy:
    """devices.yaml 里对设备能力的引用。"""

    access_keys: list[str] = field(default_factory=list)
    policy_route_keys: list[str] = field(default_factory=list)


def access_devices() -> dict[str, DeviceConfig]:
    """仅通断控制的设备（MQTT Switch / ACL 3000）。"""
    return {k: DEVICES[k] for k in ACCESS_KEYS if k in DEVICES}


def policy_route_devices() -> dict[str, DeviceConfig]:
    """仅策略路由的设备（ACL 3001 / PBR）。"""
    return {k: DEVICES[k] for k in POLICY_ROUTE_KEYS if k in DEVICES}


@dataclass(frozen=True)
class Command:
    tv: str
    want: WantState
    source: str = "mqtt"
    kind: Literal["access", "route"] = "access"


def parse_want(payload: str | bytes) -> WantState | None:
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8", errors="ignore")
    text = payload.strip()
    upper = text.upper()
    if upper in {"ON", "OFF"}:
        return upper  # type: ignore[return-value]
    if text.startswith("{"):
        import json

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        state = str(data.get("state", "")).upper()
        if state in {"ON", "OFF"}:
            return state  # type: ignore[return-value]
    return None
