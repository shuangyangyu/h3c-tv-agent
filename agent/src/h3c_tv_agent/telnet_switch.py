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
from .route_acl import (
    DEFAULT_ROUTE_BYPASS_CIDRS,
    build_bypass_permit_commands,
    build_route_permit_command,
    expected_bypass_rule_ids,
    find_source_rule_ids,
    has_route_permit,
    parse_bypass_cidrs,
    pbr_deny_node_configured,
)

log = get_logger("telnet")

_AUTH_FAIL_MARKERS = (
    "login failed",
    "authentication failed",
    "login incorrect",
    "wrong password",
    "user name or password",
    "username or password",
    "bad password",
)
_STILL_AT_PROMPT = re.compile(r"(?i)(login|username|password)\s*:")


class SwitchError(RuntimeError):
    """Telnet / ACL failure. Optional reason: auth | unreachable | prompt | reject."""

    def __init__(self, message: str, *, reason: str | None = None) -> None:
        super().__init__(message)
        self.reason = reason


def classify_login_banner(banner: str) -> str | None:
    """Return 'auth' if banner looks like failed login; else None."""
    low = banner.lower()
    if any(m in low for m in _AUTH_FAIL_MARKERS):
        return "auth"
    if _STILL_AT_PROMPT.search(banner):
        return "auth"
    return None


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
        route_bypass_acl_id: int = 3002,
        pbr_name: str = "mihomo",
        pbr_deny_node: int = 5,
        tvs: Mapping[str, TVConfig] | None = None,
        route_tvs: Mapping[str, TVConfig] | None = None,
        route_bypass_cidrs: str | list[str] | None = None,
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
        self.route_bypass_acl_id = route_bypass_acl_id
        self.pbr_name = pbr_name
        self.pbr_deny_node = pbr_deny_node
        self.tvs = dict(tvs or TVS)
        self.route_tvs = dict(route_tvs or {})
        if isinstance(route_bypass_cidrs, list):
            self.route_bypass_cidrs = (
                list(route_bypass_cidrs)
                if route_bypass_cidrs
                else list(DEFAULT_ROUTE_BYPASS_CIDRS)
            )
        else:
            self.route_bypass_cidrs = parse_bypass_cidrs(route_bypass_cidrs)
        self.timeout = timeout
        self._pbr_deny_ensured = False

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
        """ON = ACL 3001 含该 IP 的源 permit（公网走 PBR）。"""
        started = time.perf_counter()
        try:
            acl = self._run(
                ["screen-length disable", f"display acl {self.route_acl_id}"]
            )
            statuses: dict[str, TVState] = {}
            for key, tv in self.route_tvs.items():
                statuses[key] = "ON" if has_route_permit(acl, tv.ip) else "OFF"
            log.info(
                "route acl polled",
                action="poll_route",
                result="ok",
                duration_ms=int((time.perf_counter() - started) * 1000),
                states=statuses,
                bypass_acl=self.route_bypass_acl_id,
                bypass=self.route_bypass_cidrs,
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

    def ensure_pbr_deny_node(self) -> None:
        """确保 PBR deny node + if-match 旁路 ACL（幂等）。"""
        if self._pbr_deny_ensured:
            return
        # 不带策略名更稳；带名在部分版本输出不完整会导致误判重复配置
        pbr = self._run(["screen-length disable", "display ip policy-based-route"])
        if pbr_deny_node_configured(
            pbr, node=self.pbr_deny_node, acl_id=self.route_bypass_acl_id
        ):
            self._pbr_deny_ensured = True
            log.info(
                "pbr deny node ok",
                pbr=self.pbr_name,
                node=self.pbr_deny_node,
                bypass_acl=self.route_bypass_acl_id,
            )
            return

        commands = [
            "system-view",
            f"acl advanced {self.route_bypass_acl_id}",
            "description PBR-bypass-private-dest",
            "quit",
            f"policy-based-route {self.pbr_name} deny node {self.pbr_deny_node}",
            f"if-match acl {self.route_bypass_acl_id}",
            "quit",
            "quit",
        ]
        output = self._run(commands)
        self._ensure_ok(output)
        self._pbr_deny_ensured = True
        log.info(
            "pbr deny node configured",
            pbr=self.pbr_name,
            node=self.pbr_deny_node,
            bypass_acl=self.route_bypass_acl_id,
        )

    def normalize_route_rules(self) -> None:
        """确保 deny node；已 ON 设备校正 3001/3002 规则。"""
        if not self.route_tvs:
            return
        self.ensure_pbr_deny_node()
        route_acl = self._run(
            ["screen-length disable", f"display acl {self.route_acl_id}"]
        )
        bypass_acl = self._run(
            ["screen-length disable", f"display acl {self.route_bypass_acl_id}"]
        )
        for key, tv in self.route_tvs.items():
            if not tv.route_rule:
                continue
            if not has_route_permit(route_acl, tv.ip):
                continue
            route_ids = find_source_rule_ids(route_acl, tv.ip)
            bypass_ids = find_source_rule_ids(bypass_acl, tv.ip)
            expect_bypass = expected_bypass_rule_ids(
                tv.route_rule, self.route_bypass_cidrs
            )
            permit_line = build_route_permit_command(tv.ip, tv.route_rule)
            bypass_lines = build_bypass_permit_commands(
                tv.ip, tv.route_rule, self.route_bypass_cidrs
            )
            ok = (
                route_ids == {tv.route_rule}
                and permit_line in route_acl
                and bypass_ids == expect_bypass
                and all(line in bypass_acl for line in bypass_lines)
            )
            if ok:
                continue
            log.info(
                "normalizing route rule",
                tv=key,
                ip=tv.ip,
                route_found=sorted(route_ids),
                bypass_found=sorted(bypass_ids),
                expect_bypass=sorted(expect_bypass),
            )
            self.set_policy_route(key, "ON")

    def set_policy_route(
        self, key: str, want: TVState, *, save: bool = False
    ) -> tuple[TVState, set[int]]:
        """ON = 3001 源 permit + 3002 私网 permit；OFF = 两边按源 IP 清空。

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
            if want == "ON":
                self.ensure_pbr_deny_node()

            route_text = self._run(
                ["screen-length disable", f"display acl {self.route_acl_id}"]
            )
            bypass_text = self._run(
                ["screen-length disable", f"display acl {self.route_bypass_acl_id}"]
            )

            undo_route = find_source_rule_ids(route_text, tv.ip)
            undo_bypass = find_source_rule_ids(bypass_text, tv.ip)

            undone_access_collision = (undo_route | undo_bypass) & {
                t.deny_rule for t in self.tvs.values() if t.deny_rule
            }

            if want == "OFF" and not undo_route and not undo_bypass:
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

            commands = ["system-view", f"acl advanced {self.route_acl_id}"]
            for rid in sorted(undo_route):
                commands.append(f"undo rule {rid}")
            if want == "ON":
                commands.append(build_route_permit_command(tv.ip, tv.route_rule))
            commands.append("quit")

            commands.append(f"acl advanced {self.route_bypass_acl_id}")
            for rid in sorted(undo_bypass):
                commands.append(f"undo rule {rid}")
            if want == "ON":
                commands.extend(
                    build_bypass_permit_commands(
                        tv.ip, tv.route_rule, self.route_bypass_cidrs
                    )
                )
            commands.extend(["quit", "quit"])
            if save:
                commands.append("save force")

            output = self._run(commands)
            self._ensure_ok(output)
            log.info(
                "route acl updated",
                tv=key,
                action=action,
                result="ok",
                state=want,
                route_rule=tv.route_rule,
                route_acl=self.route_acl_id,
                bypass_acl=self.route_bypass_acl_id,
                bypass=self.route_bypass_cidrs if want == "ON" else None,
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
        try:
            tn = telnetlib.Telnet(self.host, self.port, timeout=self.timeout)
        except (OSError, TimeoutError, EOFError) as exc:
            log.error(
                "switch unreachable",
                action="login",
                result="fail",
                reason="unreachable",
                host=self.host,
                port=self.port,
                error=str(exc),
            )
            raise SwitchError(
                f"switch unreachable {self.host}:{self.port}: {exc}",
                reason="unreachable",
            ) from exc
        try:
            self._login(tn)
            chunks: list[str] = []
            for command in commands:
                tn.write(command.encode("ascii") + b"\r\n")
                delay = 1.2 if command.startswith("display") else 0.35
                if "policy-based-route" in command or command.startswith("if-match"):
                    delay = 0.6
                time.sleep(delay)
                chunks.append(tn.read_very_eager().decode("utf-8", errors="ignore"))
            return "\n".join(chunks)
        finally:
            try:
                tn.write(b"quit\r\n")
            except OSError:
                pass
            tn.close()

    def _login(self, tn: telnetlib.Telnet) -> None:
        try:
            idx, _, text = tn.expect([b"[Ll]ogin:", b"[Uu]sername:"], timeout=8)
            if idx < 0:
                snippet = text.decode("utf-8", errors="ignore")[:120] if text else ""
                log.error(
                    "switch login",
                    action="login",
                    result="fail",
                    reason="prompt",
                    host=self.host,
                    user=self.username,
                    detail="login prompt not found",
                    snippet=snippet,
                )
                raise SwitchError(
                    f"login prompt not found: {text!r}", reason="prompt"
                )
            tn.write(self.username.encode("ascii") + b"\r\n")
            idx, _, text = tn.expect([b"[Pp]assword:"], timeout=8)
            if idx < 0:
                snippet = text.decode("utf-8", errors="ignore")[:120] if text else ""
                log.error(
                    "switch login",
                    action="login",
                    result="fail",
                    reason="prompt",
                    host=self.host,
                    user=self.username,
                    detail="password prompt not found",
                    snippet=snippet,
                )
                raise SwitchError(
                    f"password prompt not found: {text!r}", reason="prompt"
                )
            tn.write(self.password.encode("ascii") + b"\r\n")
            time.sleep(1.0)
            banner = tn.read_very_eager().decode("utf-8", errors="ignore")
            auth_reason = classify_login_banner(banner)
            if auth_reason:
                log.error(
                    "switch login",
                    action="login",
                    result="fail",
                    reason=auth_reason,
                    host=self.host,
                    user=self.username,
                    detail="check H3C_USER / H3C_PASSWORD",
                    banner_len=len(banner),
                )
                raise SwitchError(
                    "switch authentication failed (check H3C_USER/H3C_PASSWORD)",
                    reason="auth",
                )
            log.info(
                "switch login",
                action="login",
                result="ok",
                host=self.host,
                user=self.username,
                banner_len=len(banner),
            )
        except SwitchError:
            raise
        except (OSError, TimeoutError, EOFError) as exc:
            log.error(
                "switch login",
                action="login",
                result="fail",
                reason="unreachable",
                host=self.host,
                user=self.username,
                error=str(exc),
            )
            raise SwitchError(
                f"switch login I/O failed: {exc}", reason="unreachable"
            ) from exc

    @staticmethod
    def _ensure_ok(output: str) -> None:
        markers = (
            "Unrecognized command",
            "Too many parameters",
            "No such ACL",
            "Invalid input",
        )
        if any(m in output for m in markers):
            raise SwitchError(f"switch rejected command:\n{output}", reason="reject")
        for line in output.splitlines():
            if line.strip().startswith("%"):
                raise SwitchError(f"switch error line: {line}", reason="reject")
