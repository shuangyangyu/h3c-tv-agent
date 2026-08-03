"""Receive / parse H3C syslog → TV switch state (UDP in-process; optional file tail)."""

from __future__ import annotations

import re
import socket
import threading
import time
from collections.abc import Callable
from pathlib import Path

from .logging_setup import get_logger
from .models import TVS, TVState

log = get_logger("syslog")

# 必须带 Command/Commandline is，避免 LOGIN_FAILED 把命令当用户名误匹配
# Command is undo rule 15
# Commandline is rule 15 deny ip source 192.168.1.24 0
_RE_UNDO = re.compile(r"(?i)command(?:line)?\s+is\s+undo\s+rule\s+(\d+)")
_RE_DENY = re.compile(
    r"(?i)command(?:line)?\s+is\s+rule\s+(\d+)\s+deny\s+ip\s+source\s+(\d+\.\d+\.\d+\.\d+)"
)

PublishFn = Callable[[str, TVState, dict | None], None]


def _rule_index() -> dict[int, str]:
    return {tv.deny_rule: key for key, tv in TVS.items()}


def _ip_index() -> dict[str, str]:
    return {tv.ip: key for key, tv in TVS.items()}


def parse_h3c_syslog_line(line: str) -> tuple[str, TVState] | None:
    """Return (tv_key, state) if line describes TV ACL allow/deny."""
    undo = _RE_UNDO.search(line)
    if undo:
        rule = int(undo.group(1))
        tv = _rule_index().get(rule)
        if tv:
            return tv, "ON"

    deny = _RE_DENY.search(line)
    if deny:
        rule = int(deny.group(1))
        ip = deny.group(2)
        by_rule = _rule_index().get(rule)
        by_ip = _ip_index().get(ip)
        tv = by_rule or by_ip
        if tv and (by_ip is None or by_rule is None or by_rule == by_ip):
            return tv, "OFF"
        if by_ip:
            return by_ip, "OFF"
        if by_rule:
            return by_rule, "OFF"
    return None


def emit_syslog_match(line: str, on_state: PublishFn) -> bool:
    """Parse one line; publish if matched. Returns True when handled."""
    parsed = parse_h3c_syslog_line(line)
    if not parsed:
        return False
    tv, state = parsed
    tv_cfg = TVS[tv]
    log.info(
        "syslog matched",
        tv=tv,
        state=state,
        action="allow" if state == "ON" else "deny",
        result="ok",
        deny_rule=tv_cfg.deny_rule,
        feedback_source="h3c_syslog",
        line=line.strip()[:200],
    )
    on_state(
        tv,
        state,
        {
            "name": tv_cfg.name,
            "ip": tv_cfg.ip,
            "deny_rule": tv_cfg.deny_rule,
            "feedback_source": "h3c_syslog",
            "action": "allow" if state == "ON" else "deny",
        },
    )
    return True


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
