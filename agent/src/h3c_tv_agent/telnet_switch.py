"""H3C S5550 ACL control via telnetlib3 legacy client."""

from __future__ import annotations

import re
import time
from typing import Mapping

# H3C works reliably with telnetlib3's stdlib-compatible shim;
# sync.TelnetConnection negotiated Login but dropped the session after password.
import telnetlib3.telnetlib as telnetlib

from .logging_setup import get_logger
from .models import TVConfig, TVS, TVState

log = get_logger("telnet")

_RE_PERMIT_SRC = re.compile(
    r"(?i)rule\s+(\d+)\s+permit\s+ip\s+source\s+(\d+\.\d+\.\d+\.\d+)\s+0"
)


class SwitchError(RuntimeError):
    pass


class H3CSwitch:
    """Telnet session helpers for access ACL + policy-route ACL."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        *,
        port: int = 23,
        acl_id: int = 3000,
        route_acl_id: int = 3001,
        tvs: Mapping[str, TVConfig] | None = None,
        route_tvs: Mapping[str, TVConfig] | None = None,
        timeout: float = 10.0,
    ) -> None:
        if not password:
            raise SwitchError("H3C_PASSWORD is empty")
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.acl_id = acl_id
        self.route_acl_id = route_acl_id
        self.tvs = dict(tvs or TVS)
        self.route_tvs = dict(route_tvs or {})
        self.timeout = timeout

    def get_statuses(self) -> dict[str, TVState]:
        started = time.perf_counter()
        try:
            acl = self._run(["screen-length disable", "display acl all"])
            statuses: dict[str, TVState] = {}
            for key, tv in self.tvs.items():
                deny = f"rule {tv.deny_rule} deny ip source {tv.ip} 0"
                statuses[key] = "OFF" if deny in acl else "ON"
            log.info(
                "acl polled",
                action="poll",
                result="ok",
                duration_ms=int((time.perf_counter() - started) * 1000),
                states=statuses,
            )
            return statuses
        except Exception as exc:
            log.error(
                "acl poll failed",
                action="poll",
                result="fail",
                error=str(exc),
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            raise

    def get_route_statuses(self) -> dict[str, TVState]:
        """ON = ACL 3001 含该 IP 的 permit（走 PBR）。"""
        started = time.perf_counter()
        try:
            acl = self._run(["screen-length disable", f"display acl {self.route_acl_id}"])
            statuses: dict[str, TVState] = {}
            for key, tv in self.route_tvs.items():
                needle = f"permit ip source {tv.ip} 0"
                statuses[key] = "ON" if needle in acl else "OFF"
            log.info(
                "route acl polled",
                action="poll_route",
                result="ok",
                duration_ms=int((time.perf_counter() - started) * 1000),
                states=statuses,
            )
            return statuses
        except Exception as exc:
            log.error(
                "route acl poll failed",
                action="poll_route",
                result="fail",
                error=str(exc),
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            raise

    def set_internet(self, tv_key: str, want: TVState, *, save: bool = False) -> TVState:
        tv = self.tvs.get(tv_key)
        if tv is None:
            raise SwitchError(f"unknown tv: {tv_key}")

        action = "allow" if want == "ON" else "deny"
        started = time.perf_counter()
        try:
            if want == "ON":
                commands = [
                    "system-view",
                    f"acl advanced {self.acl_id}",
                    f"undo rule {tv.deny_rule}",
                    "quit",
                    "quit",
                ]
            else:
                commands = [
                    "system-view",
                    f"acl advanced {self.acl_id}",
                    f"undo rule {tv.deny_rule}",
                    f"rule {tv.deny_rule} deny ip source {tv.ip} 0",
                    "quit",
                    "quit",
                ]
            if save:
                commands.append("save force")
            output = self._run(commands)
            self._ensure_ok(output)
            state: TVState = want
            log.info(
                "acl updated",
                tv=tv_key,
                action=action,
                result="ok",
                state=state,
                deny_rule=tv.deny_rule,
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            return state
        except Exception as exc:
            log.error(
                "acl update failed",
                tv=tv_key,
                action=action,
                result="fail",
                deny_rule=tv.deny_rule,
                error=str(exc),
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            raise

    def normalize_route_rules(self) -> None:
        """若 ACL 3001 中源 IP 已 permit 但规则号不是配置值，重写到标准号。"""
        if not self.route_tvs:
            return
        acl = self._run(["screen-length disable", f"display acl {self.route_acl_id}"])
        for key, tv in self.route_tvs.items():
            if not tv.route_rule:
                continue
            matches = {
                int(m.group(1))
                for m in _RE_PERMIT_SRC.finditer(acl)
                if m.group(2) == tv.ip
            }
            if not matches:
                continue
            if matches == {tv.route_rule}:
                continue
            log.info(
                "normalizing route rule",
                tv=key,
                ip=tv.ip,
                found=sorted(matches),
                target=tv.route_rule,
            )
            self.set_policy_route(key, "ON")

    def set_policy_route(
        self, key: str, want: TVState, *, save: bool = False
    ) -> tuple[TVState, set[int]]:
        """ON = 写入 ACL 3001 permit；OFF = 删除该源 IP 的 permit。

        返回 (状态, 与通断 deny 同号的被 undo 规则号)。同号时 syslog 可能误报通断，调用方应校正。
        """
        tv = self.route_tvs.get(key)
        if tv is None:
            raise SwitchError(f"unknown route device: {key}")
        if not tv.route_rule:
            raise SwitchError(f"route_rule not assigned for {key}")

        action = "route_on" if want == "ON" else "route_off"
        started = time.perf_counter()
        try:
            # 先读现有规则：按 IP 清掉旧号（如手工配置的 10/15），再写标准号
            acl = self._run(["screen-length disable", f"display acl {self.route_acl_id}"])
            undo_ids = {
                int(m.group(1))
                for m in _RE_PERMIT_SRC.finditer(acl)
                if m.group(2) == tv.ip
            }

            undone_access_collision = undo_ids & {
                tv.deny_rule for tv in self.tvs.values() if tv.deny_rule
            }

            commands = [
                "system-view",
                f"acl advanced {self.route_acl_id}",
            ]
            for rid in sorted(undo_ids):
                commands.append(f"undo rule {rid}")
            if want == "ON":
                commands.append(f"rule {tv.route_rule} permit ip source {tv.ip} 0")
            commands.extend(["quit", "quit"])
            if save:
                commands.append("save force")

            # 无旧规则且要 OFF：无需改 ACL
            if want == "OFF" and not undo_ids:
                log.info(
                    "route already off",
                    tv=key,
                    action=action,
                    result="ok",
                    state="OFF",
                    route_rule=tv.route_rule,
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
                return "OFF", undone_access_collision

            output = self._run(commands)
            self._ensure_ok(output)
            log.info(
                "route acl updated",
                tv=key,
                action=action,
                result="ok",
                state=want,
                route_rule=tv.route_rule,
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            return want, undone_access_collision
        except Exception as exc:
            log.error(
                "route acl update failed",
                tv=key,
                action=action,
                result="fail",
                route_rule=tv.route_rule,
                error=str(exc),
                duration_ms=int((time.perf_counter() - started) * 1000),
            )
            raise

    def _run(self, commands: list[str]) -> str:
        tn = telnetlib.Telnet(self.host, self.port, timeout=self.timeout)
        try:
            self._login(tn)
            chunks: list[str] = []
            for command in commands:
                tn.write(command.encode("ascii") + b"\r\n")
                time.sleep(0.35 if not command.startswith("display") else 1.2)
                chunks.append(tn.read_very_eager().decode("utf-8", errors="ignore"))
            return "\n".join(chunks)
        finally:
            try:
                tn.write(b"quit\r\n")
            except OSError:
                pass
            tn.close()

    def _login(self, tn: telnetlib.Telnet) -> None:
        idx, _, text = tn.expect([b"[Ll]ogin:", b"[Uu]sername:"], timeout=8)
        if idx < 0:
            raise SwitchError(f"login prompt not found: {text!r}")
        tn.write(self.username.encode("ascii") + b"\r\n")
        idx, _, text = tn.expect([b"[Pp]assword:"], timeout=8)
        if idx < 0:
            raise SwitchError(f"password prompt not found: {text!r}")
        tn.write(self.password.encode("ascii") + b"\r\n")
        time.sleep(1.0)
        banner = tn.read_very_eager().decode("utf-8", errors="ignore")
        log.info("switch login", action="login", result="ok", banner_len=len(banner))

    @staticmethod
    def _ensure_ok(output: str) -> None:
        markers = (
            "Unrecognized command",
            "Too many parameters",
            "No such ACL",
            "Invalid input",
        )
        if any(m in output for m in markers):
            raise SwitchError(f"switch rejected command:\n{output}")
        for line in output.splitlines():
            if line.strip().startswith("%"):
                raise SwitchError(f"switch error line: {line}")
