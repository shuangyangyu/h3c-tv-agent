"""Load devices.yaml: identity + access / policy_route key lists."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .logging_setup import get_logger
from .models import (
    ACCESS_KEYS,
    DEFAULT_ACCESS_KEYS,
    DEFAULT_DEVICES,
    DEFAULT_POLICY_ROUTE_KEYS,
    DEVICES,
    DeviceConfig,
    InventoryPolicy,
    POLICY_ROUTE_KEYS,
)

log = get_logger("inventory")

_DEFAULT_CANDIDATES = (
    "/config/devices.yaml",
    "devices.yaml",
    "/app/devices.yaml",
    "/config/tvs.yaml",
    "tvs.yaml",
    "/app/tvs.yaml",
)


@dataclass(frozen=True)
class RuleAllocation:
    permit_base: int = 10
    permit_step: int = 10
    deny_base: int = 15
    deny_step: int = 10
    # 与通断 deny 15/25… 错开，避免 syslog「undo rule N」歧义
    route_base: int = 100
    route_step: int = 10


def normalize_mac(mac: str) -> str:
    raw = mac.strip().lower().replace(".", "").replace(":", "").replace("-", "")
    if not raw:
        return ""
    if len(raw) == 12 and all(c in "0123456789abcdef" for c in raw):
        return f"{raw[0:4]}-{raw[4:8]}-{raw[8:12]}"
    return mac.strip()


def _parse_key_list(raw: object, *, field: str) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{field} must be a list of device keys")
    keys: list[str] = []
    for i, item in enumerate(raw):
        if isinstance(item, str):
            key = item.strip()
        elif isinstance(item, dict) and "key" in item:
            key = str(item["key"]).strip()
        else:
            raise ValueError(f"{field}[{i}] must be a string key")
        if not key:
            raise ValueError(f"{field}[{i}] empty key")
        if key in keys:
            raise ValueError(f"{field}: duplicate key {key}")
        keys.append(key)
    return keys


def parse_devices_yaml(
    data: object,
    *,
    rules: RuleAllocation | None = None,
) -> tuple[dict[str, DeviceConfig], InventoryPolicy]:
    """
    devices: 身份表
    access / access_control / 网络断开: 通断引用 key
    policy_route / 策略路由: 策略路由引用 key
    无 access 段时：全部 devices 视为通断（兼容旧 YAML）
    """
    alloc = rules or RuleAllocation()
    if not isinstance(data, dict):
        raise ValueError("config root must be a mapping")

    raw = data.get("devices")
    if raw is None:
        raw = data.get("tvs")
    if not isinstance(raw, list) or not raw:
        raise ValueError("config must contain a non-empty 'devices' list")

    devices: dict[str, DeviceConfig] = {}
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"devices[{i}] must be a mapping")
        try:
            key = str(item["key"]).strip()
            ip = str(item["ip"]).strip()
            mac = normalize_mac(str(item.get("mac") or ""))
        except KeyError as exc:
            raise ValueError(f"devices[{i}] missing required field: {exc}") from exc
        # name 可省略：默认等于 key（推荐 key 直接写中文名）
        raw_name = item.get("name")
        name = str(raw_name).strip() if raw_name is not None else key
        if not key or not ip:
            raise ValueError(f"devices[{i}] key/ip must be non-empty")
        if not name:
            name = key
        if not mac:
            raise ValueError(f"devices[{i}] mac is required")
        if key in devices:
            raise ValueError(f"duplicate device key: {key}")
        devices[key] = DeviceConfig(
            key=key,
            name=name,
            ip=ip,
            mac=mac,
            permit_rule=int(item["permit_rule"]) if item.get("permit_rule") is not None else 0,
            deny_rule=int(item["deny_rule"]) if item.get("deny_rule") is not None else 0,
            route_rule=int(item["route_rule"]) if item.get("route_rule") is not None else 0,
        )

    access_raw = (
        data.get("access")
        if "access" in data
        else data.get("access_control")
        if "access_control" in data
        else data.get("网络断开")
    )
    route_raw = (
        data.get("policy_route")
        if "policy_route" in data
        else data.get("策略路由")
    )

    if access_raw is None and route_raw is None and "tvs" in data:
        # 纯旧格式：全体通断
        access_keys = list(devices.keys())
        route_keys: list[str] = []
    elif access_raw is None and route_raw is None:
        access_keys = list(devices.keys())
        route_keys = []
    else:
        access_keys = _parse_key_list(access_raw, field="access")
        route_keys = _parse_key_list(route_raw, field="policy_route")

    for key in access_keys:
        if key not in devices:
            raise ValueError(f"access references unknown device key: {key}")
    for key in route_keys:
        if key not in devices:
            raise ValueError(f"policy_route references unknown device key: {key}")

    # 通断 / 策略路由规则号：按各自列表顺序递加
    assigned: dict[str, DeviceConfig] = {key: d for key, d in devices.items()}
    for i, key in enumerate(access_keys):
        d = assigned[key]
        deny = d.deny_rule if d.deny_rule else alloc.deny_base + i * alloc.deny_step
        permit = d.permit_rule if d.permit_rule else alloc.permit_base + i * alloc.permit_step
        assigned[key] = DeviceConfig(
            key=d.key,
            name=d.name,
            ip=d.ip,
            mac=d.mac,
            permit_rule=permit,
            deny_rule=deny,
            route_rule=d.route_rule,
        )
    for i, key in enumerate(route_keys):
        d = assigned[key]
        route = d.route_rule if d.route_rule else alloc.route_base + i * alloc.route_step
        assigned[key] = DeviceConfig(
            key=d.key,
            name=d.name,
            ip=d.ip,
            mac=d.mac,
            permit_rule=d.permit_rule,
            deny_rule=d.deny_rule,
            route_rule=route,
        )

    return assigned, InventoryPolicy(access_keys=access_keys, policy_route_keys=route_keys)


def load_devices_file(
    path: Path, *, rules: RuleAllocation | None = None
) -> tuple[dict[str, DeviceConfig], InventoryPolicy]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return parse_devices_yaml(data, rules=rules)


def resolve_devices_path(configured: str) -> Path | None:
    if configured.strip():
        p = Path(configured).expanduser()
        return p if p.is_file() else None
    for cand in _DEFAULT_CANDIDATES:
        p = Path(cand)
        if p.is_file():
            return p
    return None


def apply_device_inventory(
    configured_path: str = "",
    *,
    rules: RuleAllocation | None = None,
) -> dict[str, DeviceConfig]:
    """Replace DEVICES / ACCESS_KEYS / POLICY_ROUTE_KEYS in place."""
    path = resolve_devices_path(configured_path)
    if path is None:
        DEVICES.clear()
        DEVICES.update(DEFAULT_DEVICES)
        ACCESS_KEYS.clear()
        ACCESS_KEYS.extend(DEFAULT_ACCESS_KEYS)
        POLICY_ROUTE_KEYS.clear()
        POLICY_ROUTE_KEYS.extend(DEFAULT_POLICY_ROUTE_KEYS)
        if configured_path.strip():
            log.warning(
                "devices config not found, using built-in defaults",
                path=configured_path,
                access=list(ACCESS_KEYS),
                policy_route=list(POLICY_ROUTE_KEYS),
            )
        else:
            log.info(
                "using built-in device inventory",
                access=list(ACCESS_KEYS),
                policy_route=list(POLICY_ROUTE_KEYS),
            )
        return DEVICES

    loaded, policy = load_devices_file(path, rules=rules)
    DEVICES.clear()
    DEVICES.update(loaded)
    ACCESS_KEYS.clear()
    ACCESS_KEYS.extend(policy.access_keys)
    POLICY_ROUTE_KEYS.clear()
    POLICY_ROUTE_KEYS.extend(policy.policy_route_keys)
    log.info(
        "loaded device inventory",
        path=str(path),
        devices=list(DEVICES),
        access=list(ACCESS_KEYS),
        policy_route=list(POLICY_ROUTE_KEYS),
        access_rules={
            k: {"deny": DEVICES[k].deny_rule, "permit": DEVICES[k].permit_rule}
            for k in ACCESS_KEYS
        },
        route_rules={k: DEVICES[k].route_rule for k in POLICY_ROUTE_KEYS},
    )
    return DEVICES


parse_tvs_yaml = parse_devices_yaml
apply_tv_inventory = apply_device_inventory
