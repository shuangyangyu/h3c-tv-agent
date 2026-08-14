"""Agent runtime: MQTT + Telnet worker; feedback from in-process H3C syslog UDP."""

from __future__ import annotations

import queue
import threading
import time
from typing import Literal

from pathlib import Path

from .config import Settings
from .hass_install import HassChildInstaller, InstallStatus
from .log_feedback import clear_log_feedback, make_mqtt_feedback_publisher, register_log_feedback
from .logging_setup import get_logger, setup_logging
from .models import ACCESS_KEYS, POLICY_ROUTE_KEYS, Command, TVState, access_devices, policy_route_devices
from .mqtt_app import MqttBridge
from .syslog_watcher import H3CSyslogTailer, H3CSyslogUdpServer, SyslogFeedbackWatch
from .telnet_switch import H3CSwitch, SwitchError

log = get_logger("service")

ControlKind = Literal["access", "route"]


class AgentService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.switch = H3CSwitch(
            settings.h3c_host,
            settings.h3c_user,
            settings.h3c_password,
            port=settings.h3c_port,
            acl_id=settings.h3c_acl_id,
            route_acl_id=settings.route_acl_id,
            route_bypass_acl_id=settings.route_bypass_acl_id,
            pbr_name=settings.pbr_name,
            pbr_deny_node=settings.pbr_deny_node,
            tvs=access_devices(),
            route_tvs=policy_route_devices(),
            route_bypass_cidrs=settings.route_bypass_cidrs,
        )
        self.commands: queue.Queue[Command | None] = queue.Queue()
        self.switch_lock = threading.Lock()
        self._stop = threading.Event()
        self.installer: HassChildInstaller | None = None
        if settings.child_install_enabled:
            self.installer = HassChildInstaller(
                package_dir=Path(settings.hass_package_path),
                host=settings.ha_ssh_host,
                port=settings.ha_ssh_port,
                username=settings.ha_ssh_user,
                password=settings.ha_ssh_password,
                remote_components=settings.ha_custom_components,
                restart_ha=settings.ha_restart_after_install,
                on_status=self._on_install_status,
            )
        self.mqtt = MqttBridge(
            host=settings.mqtt_host,
            port=settings.mqtt_port,
            username=settings.mqtt_user,
            password=settings.mqtt_password,
            prefix=settings.mqtt_prefix,
            route_prefix=settings.mqtt_route_prefix,
            client_id=settings.mqtt_client_id,
            on_set=self.enqueue_set,
            on_install_child=self._enqueue_install_child if self.installer else None,
            enable_child_install=self.installer is not None,
        )
        self._syslog_udp: H3CSyslogUdpServer | None = None
        self._syslog_tail: H3CSyslogTailer | None = None
        self._syslog_watch = SyslogFeedbackWatch(0.0)
        clear_log_feedback()
        if settings.feedback_mode == "structured_log":
            register_log_feedback(
                make_mqtt_feedback_publisher(
                    self.mqtt.publish_state,
                    self.mqtt.publish_status,
                )
            )
        elif settings.feedback_mode == "h3c_syslog":
            if settings.syslog_udp_port > 0:
                self._syslog_udp = H3CSyslogUdpServer(
                    settings.syslog_udp_port,
                    on_state=self._on_syslog_state,
                )
            if settings.h3c_syslog_path:
                self._syslog_tail = H3CSyslogTailer(
                    settings.h3c_syslog_path,
                    on_state=self._on_syslog_state,
                )
            self._syslog_watch = SyslogFeedbackWatch(
                settings.syslog_feedback_timeout_sec
            )

        self._worker = threading.Thread(target=self._worker_loop, name="h3c-worker", daemon=True)
        self._poller: threading.Thread | None = None
        if settings.poll_interval_sec > 0:
            self._poller = threading.Thread(
                target=self._poller_loop, name="h3c-poller", daemon=True
            )

    def _on_syslog_state(
        self,
        key: str,
        state: TVState,
        attrs: dict | None,
        kind: ControlKind = "access",
    ) -> None:
        # 关网命令顺序是 undo(→ON) + deny(→OFF)；忽略中间的 undo，避免 HA 开关弹回
        expected = self._syslog_watch.expected_state(key, kind)
        if expected is not None and state != expected:
            log.info(
                "syslog interim state ignored",
                tv=key,
                control=kind,
                state=state,
                expected=expected,
            )
            return
        self._syslog_watch.matched(key, kind)
        self.mqtt.publish_status("online")
        if kind == "route":
            self.mqtt.publish_route_state(key, state, attrs=attrs)
        else:
            self.mqtt.publish_state(key, state, attrs=attrs)

    def enqueue_set(self, key: str, want: TVState, kind: ControlKind = "access") -> None:
        # 同一设备同类指令只保留最新，避免连点排队把状态打乱
        self._coalesce_pending(key, kind)
        # Telnet 可能还在排队：先回写 state，HA 开关立刻跟手
        if kind == "route":
            tv = policy_route_devices().get(key)
            self.mqtt.publish_route_state(
                key,
                want,
                attrs={
                    "name": tv.name if tv else key,
                    "ip": tv.ip if tv else "",
                    "route_rule": tv.route_rule if tv else None,
                    "control": "route",
                    "feedback_source": "mqtt_queued",
                    "action": "route_on" if want == "ON" else "route_off",
                },
            )
        else:
            self._syslog_watch.expect(key, "access", want)
            tv = access_devices().get(key)
            self.mqtt.publish_state(
                key,
                want,
                attrs={
                    "name": tv.name if tv else key,
                    "ip": tv.ip if tv else "",
                    "deny_rule": tv.deny_rule if tv else None,
                    "control": "access",
                    "feedback_source": "mqtt_queued",
                    "action": "allow" if want == "ON" else "deny",
                },
            )
        self.commands.put(Command(tv=key, want=want, source="mqtt", kind=kind))

    def _coalesce_pending(self, key: str, kind: ControlKind) -> None:
        kept: list[Command | None] = []
        dropped = 0
        try:
            while True:
                item = self.commands.get_nowait()
                if item is None:
                    kept.append(None)
                    continue
                if item.tv == key and item.kind == kind and item.source == "mqtt":
                    dropped += 1
                    continue
                kept.append(item)
        except queue.Empty:
            pass
        for item in kept:
            self.commands.put(item)
        if dropped:
            log.info(
                "mqtt commands coalesced",
                tv=key,
                kind=kind,
                dropped=dropped,
            )

    def start(self) -> None:
        self.mqtt.connect()
        self._worker.start()
        if self._poller is not None:
            self._poller.start()
        if self._syslog_udp is not None:
            self._syslog_udp.start()
        if self._syslog_tail is not None:
            self._syslog_tail.start()
        self._syslog_watch.start()
        self.commands.put(Command(tv="*", want="ON", source="bootstrap"))
        if self.installer is not None:
            threading.Thread(
                target=self._probe_install_status,
                name="hass-child-probe",
                daemon=True,
            ).start()
        log.info(
            "agent started",
            h3c=self.settings.h3c_host,
            mqtt=f"{self.settings.mqtt_host}:{self.settings.mqtt_port}",
            tvs=list(ACCESS_KEYS),
            policy_route=list(POLICY_ROUTE_KEYS),
            feedback_mode=self.settings.feedback_mode,
            syslog_udp_port=self.settings.syslog_udp_port,
            syslog_path=self.settings.h3c_syslog_path or None,
            syslog_feedback_timeout_sec=self.settings.syslog_feedback_timeout_sec,
            route_acl=self.settings.route_acl_id,
            bypass_acl=self.settings.route_bypass_acl_id,
            pbr=f"{self.settings.pbr_name}/deny{self.settings.pbr_deny_node}",
            route_bypass=self.settings.route_bypass_cidrs,
            child_install=self.installer is not None,
        )

    def _on_install_status(self, status: InstallStatus) -> None:
        self.mqtt.publish_child_install_status(status.to_payload())

    def _probe_install_status(self) -> None:
        time.sleep(2)
        if self.installer is not None:
            self.installer.probe()

    def _enqueue_install_child(self) -> None:
        if self.installer is None:
            return
        self.installer.install_async()

    def stop(self) -> None:
        self._stop.set()
        self._syslog_watch.stop()
        if self._syslog_udp is not None:
            self._syslog_udp.stop()
        if self._syslog_tail is not None:
            self._syslog_tail.stop()
        self.commands.put(None)
        clear_log_feedback()
        self.mqtt.stop()

    def run_forever(self) -> None:
        self.start()
        try:
            while not self._stop.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            log.info("shutdown requested")
        finally:
            self.stop()

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            cmd = self.commands.get()
            if cmd is None:
                break
            try:
                if cmd.source in {"poll", "bootstrap"} or cmd.tv == "*":
                    self._do_bootstrap_status()
                else:
                    self._do_set(cmd)
            except Exception as exc:
                log.error("worker error", error=str(exc), tv=getattr(cmd, "tv", None))
            finally:
                self.commands.task_done()

    def _poller_loop(self) -> None:
        time.sleep(2)
        while not self._stop.is_set():
            self.commands.put(Command(tv="*", want="ON", source="poll"))
            self._stop.wait(self.settings.poll_interval_sec)

    def _do_bootstrap_status(self) -> None:
        with self.switch_lock:
            try:
                # 把手工/旧号（如 10/15）迁到 100/110，后续 OFF 的 undo 才能走 syslog→route
                self.switch.normalize_route_rules()
                states = self.switch.get_statuses()
                route_states = self.switch.get_route_statuses()
            except SwitchError as exc:
                self.mqtt.publish_status("offline")
                log.error(
                    "bootstrap status failed",
                    action="poll",
                    result="fail",
                    reason=getattr(exc, "reason", None),
                    error=str(exc),
                )
                return
        self.mqtt.publish_status("online")
        self.mqtt.publish_all_states(states)
        self.mqtt.publish_all_route_states(route_states)

    def _do_set(self, cmd: Command) -> None:
        with self.switch_lock:
            try:
                if cmd.kind == "route":
                    tv = policy_route_devices().get(cmd.tv)
                    self.mqtt.publish_route_state(
                        cmd.tv,
                        cmd.want,
                        attrs={
                            "name": tv.name if tv else cmd.tv,
                            "ip": tv.ip if tv else "",
                            "route_rule": tv.route_rule if tv else None,
                            "control": "route",
                            "feedback_source": "mqtt_cmd",
                            "action": "route_on" if cmd.want == "ON" else "route_off",
                        },
                    )
                    _state, collisions = self.switch.set_policy_route(cmd.tv, cmd.want)
                    self.mqtt.publish_route_state(
                        cmd.tv,
                        cmd.want,
                        attrs={
                            "name": tv.name if tv else cmd.tv,
                            "ip": tv.ip if tv else "",
                            "route_rule": tv.route_rule if tv else None,
                            "control": "route",
                            "feedback_source": "telnet_ack",
                            "action": "route_on" if cmd.want == "ON" else "route_off",
                        },
                    )
                    if collisions:
                        try:
                            self.mqtt.publish_all_states(self.switch.get_statuses())
                        except Exception:
                            pass
                else:
                    # 先登记期望态并立刻回写 state（不用 HA optimistic/双闪电，也不用人为延迟）
                    self._syslog_watch.expect(cmd.tv, "access", cmd.want)
                    tv = access_devices().get(cmd.tv)
                    self.mqtt.publish_state(
                        cmd.tv,
                        cmd.want,
                        attrs={
                            "name": tv.name if tv else cmd.tv,
                            "ip": tv.ip if tv else "",
                            "deny_rule": tv.deny_rule if tv else None,
                            "control": "access",
                            "feedback_source": "mqtt_cmd",
                            "action": "allow" if cmd.want == "ON" else "deny",
                        },
                    )
                    self.switch.set_internet(cmd.tv, cmd.want)
                    self.mqtt.publish_state(
                        cmd.tv,
                        cmd.want,
                        attrs={
                            "name": tv.name if tv else cmd.tv,
                            "ip": tv.ip if tv else "",
                            "deny_rule": tv.deny_rule if tv else None,
                            "control": "access",
                            "feedback_source": "telnet_ack",
                            "action": "allow" if cmd.want == "ON" else "deny",
                        },
                    )
            except SwitchError as exc:
                if cmd.kind == "access":
                    self._syslog_watch.matched(cmd.tv, "access")
                log.error(
                    "set failed",
                    tv=cmd.tv,
                    kind=cmd.kind,
                    action=cmd.want,
                    result="fail",
                    reason=getattr(exc, "reason", None),
                    error=str(exc),
                )
                try:
                    if cmd.kind == "route":
                        self.mqtt.publish_all_route_states(self.switch.get_route_statuses())
                    else:
                        self.mqtt.publish_all_states(self.switch.get_statuses())
                except Exception:
                    pass


def run_status_once(settings: Settings) -> int:
    setup_logging(settings.log_level)
    tvs = access_devices()
    routes = policy_route_devices()
    sw = H3CSwitch(
        settings.h3c_host,
        settings.h3c_user,
        settings.h3c_password,
        port=settings.h3c_port,
        acl_id=settings.h3c_acl_id,
        route_acl_id=settings.route_acl_id,
        route_bypass_acl_id=settings.route_bypass_acl_id,
        pbr_name=settings.pbr_name,
        pbr_deny_node=settings.pbr_deny_node,
        tvs=tvs,
        route_tvs=routes,
        route_bypass_cidrs=settings.route_bypass_cidrs,
    )
    states = sw.get_statuses()
    for key, state in states.items():
        tv = tvs[key]
        print(f"access {key}: {tv.name} {tv.ip} -> {state}")
    route_states = sw.get_route_statuses()
    for key, state in route_states.items():
        tv = routes[key]
        print(f"route  {key}: {tv.name} {tv.ip} rule={tv.route_rule} -> {state}")
    return 0
