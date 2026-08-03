"""Unit tests for H3C syslog ACL line parsing."""

from h3c_tv_agent.syslog_watcher import parse_h3c_syslog_line


def test_parse_undo_rule():
    line = (
        "2026-08-03T06:30:28+00:00 H3C %%10SHELL/6/SHELL_CMD: "
        "-DevIP=192.168.1.254; Command is undo rule 15"
    )
    assert parse_h3c_syslog_line(line) == ("master_bedroom", "ON")


def test_parse_deny_rule():
    line = (
        "2026-08-03T06:30:32+00:00 H3C %%10SHELL/6/SHELL_CMD: "
        "-DevIP=192.168.1.254; Command is rule 15 deny ip source 192.168.1.24 0"
    )
    assert parse_h3c_syslog_line(line) == ("master_bedroom", "OFF")


def test_parse_unrelated():
    assert parse_h3c_syslog_line("IFNET link up") is None


def test_ignore_login_failed_with_command_as_username():
    line = (
        "<189>Aug  3 15:07:42 2026 H3C %%10LOGIN/5/LOGIN_FAILED: "
        "-DevIP=192.168.1.254; rule 15 deny ip source 192.168.1.24 0 "
        "destination any failed to log in from 192.168.5.182."
    )
    assert parse_h3c_syslog_line(line) is None
