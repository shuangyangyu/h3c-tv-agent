"""Receive / parse H3C syslog → access / policy-route MQTT state."""

from __future__ import annotations

import re
import socket
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .logging_setup import get_logger
from .models import TVState, access_devices, policy_route_devices

log = get_logger("syslog")

# 必须带 Command/Commandline is，避免 LOGIN_FAILED 把命令当用户名误匹配
_RE_UNDO = re.compile(r"(?i)command(?:line)?\s+is\s+undo\s+rule\s+(\d+)")
_RE_DENY = re.compile(
    r"(?i)command(?:line)?\s+is\s+rule\s+(\d+)\s+deny\s+ip\s+source\s+(\d+\.\d+\.\d+\.\d+)"
)
_RE_PERMIT = re.compile(
    r"(?i)command(?:line)?\s+is\s+rule\s+(\d+)\s+permit\s+ip\s+source\s+(\d+\.\d+\.\d+\.\d+)"
)

ControlKind = Literal["access", "route"]


@dataclass(frozen=True)
class SyslogMatch:
    key: str
    state: TVState
    kind: ControlKind


PublishFn = Callable[[str, TVState, dict | None, ControlKind], None]


def _access_deny_index() -> dict[int, str]:
    return {tv.deny_rule: key for key, tv in access_devices().items() if tv.deny_rule}


def _access_ip_index() -> dict[str, str]:
    return {tv.ip: key for key, tv in access_devices().items()}


def _route_rule_index() -> dict[int, str]:
    return {tv.route_rule: key for key, tv in policy_route_devices().items() if tv.route_rule}


def _route_ip_index() -> dict[str, str]:
    return {tv.ip: key for key, tv in policy_route_devices().items()}


def parse_h3c_syslog_line(line: str) -> SyslogMatch | None:
    """Parse SHELL_CMD for access deny/undo or route permit/undo."""
    permit = _RE_PERMIT.search(line)
    if permit:
        rule = int(permit.group(1))
        ip = permit.group(2)
        by_rule = _route_rule_index().get(rule)
        by_ip = _route_ip_index().get(ip)
        key = by_rule or by_ip
        if key and (by_ip is None or by_rule is None or by_rule == by_ip):
            return SyslogMatch(key, "ON", "route")
        if by_ip:
            return SyslogMatch(by_ip, "ON", "route")
        if by_rule:
            return SyslogMatch(by_rule, "ON", "route")
        return None

    undo = _RE_UNDO.search(line)
    if undo:
        rule = int(undo.group(1))
        # 规则号空间：access deny 15/25… vs route 100/110…（配置保证不重叠）
        access_key = _access_deny_index().get(rule)
        if access_key:
            return SyslogMatch(access_key, "ON", "access")
        route_key = _route_rule_index().get(rule)
        if route_key:
            return SyslogMatch(route_key, "OFF", "route")
        return None

    deny = _RE_DENY.search(line)
    if deny:
        # PBR 私网例外：deny … destination …，不是通断 ACL 3000
        if re.search(r"(?i)\bdestination\b", line[deny.start() : deny.start() + 160]):
            return None
        rule = int(deny.group(1))
        ip = deny.group(2)
        by_rule = _access_deny_index().get(rule)
        by_ip = _access_ip_index().get(ip)
        key = by_rule or by_ip
        if key and (by_ip is None or by_rule is None or by_rule == by_ip):
            return SyslogMatch(key, "OFF", "access")
        if by_ip:
            return SyslogMatch(by_ip, "OFF", "access")
        if by_rule:
            return SyslogMatch(by_rule, "OFF", "access")
    return None


def emit_syslog_match(line: str, on_state: PublishFn) -> bool:
    """Parse one line; publish if matched. Returns True when handled."""
    parsed = parse_h3c_syslog_line(line)
    if not parsed:
        return False
    if parsed.kind == "access":
        tv_cfg = access_devices()[parsed.key]
        attrs = {
            "name": tv_cfg.name,
            "ip": tv_cfg.ip,
            "deny_rule": tv_cfg.deny_rule,
            "control": "access",
            "feedback_source": "h3c_syslog",
            "action": "allow" if parsed.state == "ON" else "deny",
        }
        action = "allow" if parsed.state == "ON" else "deny"
        extra = {"deny_rule": tv_cfg.deny_rule}
    else:
        tv_cfg = policy_route_devices()[parsed.key]
        attrs = {
            "name": tv_cfg.name,
            "ip": tv_cfg.ip,
            "route_rule": tv_cfg.route_rule,
            "control": "route",
            "feedback_source": "h3c_syslog",
            "action": "route_on" if parsed.state == "ON" else "route_off",
        }
        action = "route_on" if parsed.state == "ON" else "route_off"
        extra = {"route_rule": tv_cfg.route_rule}

    log.info(
        "syslog matched",
        tv=parsed.key,
        state=parsed.state,
        action=action,
        result="ok",
        control=parsed.kind,
        feedback_source="h3c_syslog",
        line=line.strip()[:200],
        **extra,
    )
    on_state(parsed.key, parsed.state, attrs, parsed.kind)
    return True


class SyslogFeedbackWatch:
    """Warn when access ACL Telnet succeeded but no matching SHELL syslog arrives."""

    def __init__(self, timeout_sec: float = 20.0) -> None:
        self.timeout_sec = max(0.0, float(timeout_sec))
        self._pending: dict[tuple[str, ControlKind], tuple[float, TVState]] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def enabled(self) -> bool:
        return self.timeout_sec > 0

    def start(self) -> None:
        if not self.enabled or self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run, name="h3c-syslog-watch", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def expect(self, key: str, kind: ControlKind, state: TVState) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._pending[(key, kind)] = (
                time.monotonic() + self.timeout_sec,
                state,
            )

    def expected_state(self, key: str, kind: ControlKind) -> TVState | None:
        """Return pending wanted state, if any."""
        with self._lock:
            item = self._pending.get((key, kind))
            return item[1] if item else None

    def matched(self, key: str, kind: ControlKind) -> None:
        with self._lock:
            self._pending.pop((key, kind), None)

    def _run(self) -> None:
        while not self._stop.is_set():
            now = time.monotonic()
            expired: list[tuple[str, ControlKind, TVState]] = []
            with self._lock:
                for (key, kind), (deadline, state) in list(self._pending.items()):
                    if now >= deadline:
                        expired.append((key, kind, state))
                        del self._pending[(key, kind)]
            for key, kind, state in expired:
                log.warning(
                    "syslog feedback timeout",
                    tv=key,
                    control=kind,
                    state=state,
                    timeout_sec=self.timeout_sec,
                    detail="Telnet ok but no SHELL_CMD; check fanout/info-center informational",
                )
            self._stop.wait(2.0)


class H3CSyslogUdpServer:
    """Listen UDP syslog inside the agent (single-container / future HA addon)."""

    def __init__(self, port: int, on_state: PublishFn, host: str = "0.0.0.0") -> None:
        self.host = host
        self.port = port
        self.on_state = on_state
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._sock: socket.socket | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="h3c-syslog-udp", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass

    def _run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.settimeout(1.0)
        self._sock = sock
        log.info("syslog UDP listener started", host=self.host, port=self.port)
        try:
            while not self._stop.is_set():
                try:
                    data, _addr = sock.recvfrom(65535)
                except socket.timeout:
                    continue
                except OSError:
                    if self._stop.is_set():
                        break
                    raise
                text = data.decode("utf-8", errors="ignore").strip("\x00")
                for line in text.splitlines() or [text]:
                    line = line.strip()
                    if line:
                        emit_syslog_match(line, self.on_state)
        except Exception as exc:
            log.error("syslog UDP error", error=str(exc), port=self.port)
        finally:
            try:
                sock.close()
            except OSError:
                pass
            log.info("syslog UDP listener stopped", port=self.port)


class H3CSyslogTailer:
    """Optional: follow a syslog file (debug / migration). Prefer UDP server for addon."""

    def __init__(self, path: str, on_state: PublishFn) -> None:
        self.path = Path(path)
        self.on_state = on_state
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="h3c-syslog-tail", daemon=True)
        self._thread.start()
        log.info("syslog tailer started", path=str(self.path))

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        position = 0
        inode: int | None = None
        while not self._stop.is_set() and not self.path.exists():
            time.sleep(1)

        while not self._stop.is_set():
            try:
                if not self.path.exists():
                    time.sleep(1)
                    continue
                st = self.path.stat()
                if inode is None:
                    inode = st.st_ino
                    position = st.st_size
                elif st.st_ino != inode or st.st_size < position:
                    inode = st.st_ino
                    position = 0
                    log.info("syslog file rotated, reopening", path=str(self.path))

                with self.path.open("r", encoding="utf-8", errors="ignore") as fh:
                    fh.seek(position)
                    while not self._stop.is_set():
                        line = fh.readline()
                        if not line:
                            position = fh.tell()
                            break
                        emit_syslog_match(line, self.on_state)
                    position = fh.tell()
            except Exception as exc:
                log.error("syslog tail error", error=str(exc), path=str(self.path))
            self._stop.wait(0.5)
