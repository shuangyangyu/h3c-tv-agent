"""Unit tests for H3C syslog ACL line parsing."""

from h3c_tv_agent.inventory import RuleAllocation, apply_device_inventory
from h3c_tv_agent.models import DEFAULT_ACCESS_KEYS, DEFAULT_DEVICES, DEFAULT_POLICY_ROUTE_KEYS
from h3c_tv_agent.models import ACCESS_KEYS, DEVICES, POLICY_ROUTE_KEYS
from h3c_tv_agent.syslog_watcher import SyslogMatch, parse_h3c_syslog_line


def _reset_builtin():
    DEVICES.clear()
    DEVICES.update(DEFAULT_DEVICES)
    ACCESS_KEYS.clear()
    ACCESS_KEYS.extend(DEFAULT_ACCESS_KEYS)
    POLICY_ROUTE_KEYS.clear()
    POLICY_ROUTE_KEYS.extend(DEFAULT_POLICY_ROUTE_KEYS)


def test_parse_undo_rule():
    _reset_builtin()
    line = (
        "2026-08-03T06:30:28+00:00 H3C %%10SHELL/6/SHELL_CMD: "
        "-DevIP=192.168.1.254; Command is undo rule 15"
    )
    assert parse_h3c_syslog_line(line) == SyslogMatch("master_bedroom", "ON", "access")


def test_parse_deny_rule():
    _reset_builtin()
    line = (
        "2026-08-03T06:30:32+00:00 H3C %%10SHELL/6/SHELL_CMD: "
        "-DevIP=192.168.1.254; Command is rule 15 deny ip source 192.168.1.24 0"
    )
    assert parse_h3c_syslog_line(line) == SyslogMatch("master_bedroom", "OFF", "access")


def test_parse_route_permit(tmp_path):
    p = tmp_path / "devices.yaml"
    p.write_text(
        "devices:\n"
        "  - key: phone\n"
        "    name: Phone\n"
        "    ip: 192.168.1.36\n"
        "    mac: aabbccddee01\n"
        "access: []\n"
        "policy_route:\n"
        "  - phone\n",
        encoding="utf-8",
    )
    apply_device_inventory(str(p), rules=RuleAllocation(route_base=100, route_step=10))
    line = (
        "H3C %%10SHELL/6/SHELL_CMD: "
        "Command is rule 100 permit ip source 192.168.1.36 0"
    )
    assert parse_h3c_syslog_line(line) == SyslogMatch("phone", "ON", "route")
    undo = "H3C %%10SHELL/6/SHELL_CMD: Command is undo rule 100"
    assert parse_h3c_syslog_line(undo) == SyslogMatch("phone", "OFF", "route")
    _reset_builtin()


def test_parse_unrelated():
    assert parse_h3c_syslog_line("IFNET link up") is None


def test_ignore_route_bypass_deny_with_destination():
    line = (
        "H3C %%10SHELL/6/SHELL_CMD: "
        "Command is rule 98 deny ip source 192.168.1.249 0 "
        "destination 192.168.0.0 0.0.255.255"
    )
    assert parse_h3c_syslog_line(line) is None


def test_ignore_login_failed_with_command_as_username():
    line = (
        "<189>Aug  3 15:07:42 2026 H3C %%10LOGIN/5/LOGIN_FAILED: "
        "-DevIP=192.168.1.254; rule 15 deny ip source 192.168.1.24 0 "
        "destination any failed to log in from 192.168.5.182."
    )
    assert parse_h3c_syslog_line(line) is None
