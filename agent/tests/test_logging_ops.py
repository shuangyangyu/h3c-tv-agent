"""Tests for login banner classification and syslog feedback watch."""

from h3c_tv_agent.syslog_watcher import SyslogFeedbackWatch
from h3c_tv_agent.telnet_switch import classify_login_banner


def test_classify_login_banner_ok():
    assert classify_login_banner("<H3C>") is None
    assert classify_login_banner("\r\n<H3C>system-view") is None


def test_classify_login_banner_auth():
    assert classify_login_banner("% Login failed.") == "auth"
    assert classify_login_banner("Login: ") == "auth"
    assert classify_login_banner("Username:") == "auth"
    assert classify_login_banner("Password:") == "auth"


def test_syslog_feedback_watch_matched_clears():
    watch = SyslogFeedbackWatch(timeout_sec=30)
    watch.expect("主卧电视", "access", "OFF")
    assert ("主卧电视", "access") in watch._pending
    watch.matched("主卧电视", "access")
    assert watch._pending == {}


def test_syslog_feedback_watch_disabled():
    watch = SyslogFeedbackWatch(timeout_sec=0)
    assert not watch.enabled
    watch.expect("客厅电视", "access", "ON")
    assert watch._pending == {}


def test_syslog_feedback_expected_state():
    watch = SyslogFeedbackWatch(timeout_sec=30)
    assert watch.expected_state("主卧电视", "access") is None
    watch.expect("主卧电视", "access", "OFF")
    assert watch.expected_state("主卧电视", "access") == "OFF"
    watch.matched("主卧电视", "access")
    assert watch.expected_state("主卧电视", "access") is None
