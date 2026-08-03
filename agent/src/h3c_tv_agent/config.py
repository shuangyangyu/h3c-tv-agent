"""Environment configuration."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    h3c_host: str = "192.168.1.254"
    h3c_port: int = 23
    h3c_user: str = "hass_robot"
    h3c_password: str = ""
    h3c_acl_id: int = 3000

    mqtt_host: str = "192.168.1.249"
    mqtt_port: int = 1883
    mqtt_user: str = ""
    mqtt_password: str = ""
    mqtt_prefix: str = "h3c/tv"
    mqtt_client_id: str = "h3c-tv-agent"

    log_level: str = "INFO"
    poll_interval_sec: int = 0

    # h3c_syslog = 进程内收交换机 syslog；structured_log = 旧的 Agent slog（调试用）
    feedback_mode: str = "h3c_syslog"
    # UDP 514（单容器 / 将来 HA addon）；0 = 不监听
    syslog_udp_port: int = 514
    # 可选：额外 tail 文件（调试）；默认真空，只靠 UDP
    h3c_syslog_path: str = ""
