"""Agent runtime: MQTT + Telnet worker; feedback from in-process H3C syslog UDP."""

from __future__ import annotations

import queue
import threading
import time

from .config import Settings
from .log_feedback import clear_log_feedback, make_mqtt_feedback_publisher, register_log_feedback
from .logging_setup import get_logger, setup_logging
from .models import Command, TVS, TVState
from .mqtt_app import MqttBridge
from .syslog_watcher import H3CSyslogTailer, H3CSyslogUdpServer
from .telnet_switch import H3CSwitch, SwitchError

log = get_logger("service")


class AgentService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.switch = H3CSwitch(
            settings.h3c_host,
            settings.h3c_user,
            settings.h3c_password,
            port=settings.h3c_port,
            acl_id=settings.h3c_acl_id,
        )
        self.commands: queue.Queue[Command | None] = queue.Queue()
        self.switch_lock = threading.Lock()
        self._stop = threading.Event()
        self.mqtt = MqttBridge(
            host=settings.mqtt_host,
            port=settings.mqtt_port,
            username=settings.mqtt_user,
            password=settings.mqtt_password,
            prefix=settings.mqtt_prefix,
            client_id=settings.mqtt_client_id,
            on_set=self.enqueue_set,
        )
        self._syslog_udp: H3CSyslogUdpServer | None = None
        self._syslog_tail: H3CSyslogTailer | None = None
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

        self._worker = threading.Thread(target=self._worker_loop, name="h3c-worker", daemon=True)
        self._poller: threading.Thread | None = None
        if settings.poll_interval_sec > 0:
            self._poller = threading.Thread(
                target=self._poller_loop, name="h3c-poller", daemon=True
            )

    def _on_syslog_state(self, tv: str, state: TVState, attrs: dict | None) -> None:
        self.mqtt.publish_status("online")
        self.mqtt.publish_state(tv, state, attrs=attrs)

    def enqueue_set(self, tv: str, want: TVState) -> None:
        self.commands.put(Command(tv=tv, want=want, source="mqtt"))

    def start(self) -> None:
        self.mqtt.connect()
        self._worker.start()
        if self._poller is not None:
            self._poller.start()
        if self._syslog_udp is not None:
            self._syslog_udp.start()
        if self._syslog_tail is not None:
            self._syslog_tail.start()
        # 启动时查一次 ACL，直接发 MQTT（初始对齐；之后靠 syslog）
        self.commands.put(Command(tv="*", want="ON", source="bootstrap"))
        log.info(
            "agent started",
            h3c=self.settings.h3c_host,
            mqtt=f"{self.settings.mqtt_host}:{self.settings.mqtt_port}",
            tvs=list(TVS),
            feedback_mode=self.settings.feedback_mode,
            syslog_udp_port=self.settings.syslog_udp_port,
            syslog_path=self.settings.h3c_syslog_path or None,
        )

    def stop(self) -> None:
        self._stop.set()
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
                states = self.switch.get_statuses()
            except SwitchError as exc:
                self.mqtt.publish_status("offline")
                log.error("bootstrap status failed", action="poll", result="fail", error=str(exc))
                return
        self.mqtt.publish_status("online")
        self.mqtt.publish_all_states(states)

    def _do_set(self, cmd: Command) -> None:
        with self.switch_lock:
            try:
                # 只下发；状态反馈等 H3C syslog（或 structured_log 模式）
                self.switch.set_internet(cmd.tv, cmd.want)
            except SwitchError as exc:
                log.error(
                    "set failed",
                    tv=cmd.tv,
                    action="allow" if cmd.want == "ON" else "deny",
                    result="fail",
                    error=str(exc),
                )
                try:
                    states = self.switch.get_statuses()
                    self.mqtt.publish_all_states(states)
                except Exception:
                    pass


def run_status_once(settings: Settings) -> int:
    setup_logging(settings.log_level)
    sw = H3CSwitch(
        settings.h3c_host,
        settings.h3c_user,
        settings.h3c_password,
        port=settings.h3c_port,
        acl_id=settings.h3c_acl_id,
    )
    states = sw.get_statuses()
    for key, state in states.items():
        tv = TVS[key]
        print(f"{key}: {tv.name} {tv.ip} -> {state}")
    return 0
