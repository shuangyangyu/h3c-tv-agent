"""H3C S5550 ACL control via telnetlib3 legacy client."""

from __future__ import annotations

import time
from typing import Mapping

# H3C works reliably with telnetlib3's stdlib-compatible shim;
# sync.TelnetConnection negotiated Login but dropped the session after password.
import telnetlib3.telnetlib as telnetlib

from .logging_setup import get_logger
from .models import TVConfig, TVS, TVState

log = get_logger("telnet")


class SwitchError(RuntimeError):
    pass


class H3CSwitch:
    """Telnet session helpers for TV internet ACL."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        *,
        port: int = 23,
        acl_id: int = 3000,
        tvs: Mapping[str, TVConfig] | None = None,
        timeout: float = 10.0,
    ) -> None:
        if not password:
            raise SwitchError("H3C_PASSWORD is empty")
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.acl_id = acl_id
        self.tvs = dict(tvs or TVS)
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
            # 命令成功即回写目标状态；周期 poll 再校正，避免二次 Telnet 拖慢反馈
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
        # H3C error lines often start with " % "
        for line in output.splitlines():
            if line.strip().startswith("%"):
                raise SwitchError(f"switch error line: {line}")
