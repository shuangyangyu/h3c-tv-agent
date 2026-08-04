"""Tests for device inventory YAML + access / policy_route."""

from pathlib import Path

import pytest

from h3c_tv_agent.inventory import (
    RuleAllocation,
    apply_device_inventory,
    normalize_mac,
    parse_devices_yaml,
)
from h3c_tv_agent.models import (
    ACCESS_KEYS,
    DEFAULT_ACCESS_KEYS,
    DEFAULT_DEVICES,
    DEFAULT_POLICY_ROUTE_KEYS,
    DEVICES,
    POLICY_ROUTE_KEYS,
    access_devices,
)


def test_normalize_mac():
    assert normalize_mac("CC:98:8B:23:AB:AA") == "cc98-8b23-abaa"


def test_access_and_route_sections():
    data = {
        "devices": [
            {"key": "tv1", "name": "TV1", "ip": "1.1.1.1", "mac": "aabbccddeeff"},
            {"key": "phone", "name": "Phone", "ip": "1.1.1.2", "mac": "aabbccddee01"},
        ],
        "access": ["tv1"],
        "policy_route": ["phone"],
    }
    devices, policy = parse_devices_yaml(data, rules=RuleAllocation())
    assert policy.access_keys == ["tv1"]
    assert policy.policy_route_keys == ["phone"]
    assert devices["tv1"].deny_rule == 15
    assert devices["tv1"].permit_rule == 10
    assert devices["phone"].deny_rule == 0  # 不通断，不分配 deny
    assert devices["phone"].route_rule == 100


def test_name_optional_defaults_to_key():
    data = {
        "devices": [
            {"key": "主卧电视", "ip": "192.168.1.24"},
        ],
        "access": ["主卧电视"],
    }
    devices, policy = parse_devices_yaml(data)
    assert policy.access_keys == ["主卧电视"]
    assert devices["主卧电视"].name == "主卧电视"
    assert devices["主卧电视"].ip == "192.168.1.24"
    assert devices["主卧电视"].mac == ""


def test_chinese_section_aliases():
    data = {
        "devices": [
            {"key": "a", "name": "A", "ip": "1.1.1.1", "mac": "aabbccddeeff"},
        ],
        "网络断开": ["a"],
        "策略路由": [],
    }
    _, policy = parse_devices_yaml(data)
    assert policy.access_keys == ["a"]


def test_legacy_all_access():
    data = {
        "devices": [
            {"key": "a", "name": "A", "ip": "1.1.1.1", "mac": "aabbccddeeff"},
            {"key": "b", "name": "B", "ip": "1.1.1.2", "mac": "aabbccddee01"},
        ],
    }
    devices, policy = parse_devices_yaml(data)
    assert policy.access_keys == ["a", "b"]
    assert devices["b"].deny_rule == 25


def test_unknown_access_key():
    with pytest.raises(ValueError, match="unknown device"):
        parse_devices_yaml(
            {
                "devices": [{"key": "a", "name": "A", "ip": "1.1.1.1", "mac": "aabbccddeeff"}],
                "access": ["nope"],
            }
        )


def test_apply_file(tmp_path: Path):
    p = tmp_path / "devices.yaml"
    p.write_text(
        "devices:\n"
        "  - key: tv\n"
        "    name: TV\n"
        "    ip: 10.0.0.1\n"
        "    mac: 112233445566\n"
        "  - key: ph\n"
        "    name: Phone\n"
        "    ip: 10.0.0.2\n"
        "    mac: 112233445567\n"
        "access:\n"
        "  - tv\n"
        "policy_route:\n"
        "  - ph\n",
        encoding="utf-8",
    )
    apply_device_inventory(str(p))
    assert ACCESS_KEYS == ["tv"]
    assert POLICY_ROUTE_KEYS == ["ph"]
    assert list(access_devices()) == ["tv"]
    apply_device_inventory("/nonexistent/devices.yaml")
    DEVICES.clear()
    DEVICES.update(DEFAULT_DEVICES)
    ACCESS_KEYS.clear()
    ACCESS_KEYS.extend(DEFAULT_ACCESS_KEYS)
    POLICY_ROUTE_KEYS.clear()
    POLICY_ROUTE_KEYS.extend(DEFAULT_POLICY_ROUTE_KEYS)
