"""Environment configuration (.env / future Addon options)."""

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
    # 通断 ACL（access）
    h3c_acl_id: int = 3000
    access_permit_rule_base: int = 10
    access_permit_rule_step: int = 10
    access_deny_rule_base: int = 15
    access_deny_rule_step: int = 10
    # 策略路由 ACL 3001；规则号与通断 deny 错开（默认 100/110/…）
    route_acl_id: int = 3001
    route_rule_base: int = 100
    route_rule_step: int = 10
    # 逗号分隔接口名（记录用；PBR 挂载不由本 Agent 改）
    acl_apply_interfaces: str = "Vlan-interface1"

    mqtt_host: str = "192.168.1.249"
    mqtt_port: int = 1883
    mqtt_user: str = ""
    mqtt_password: str = ""
    mqtt_prefix: str = "h3c/tv"
    mqtt_route_prefix: str = "h3c/route"
    mqtt_client_id: str = "h3c-tv-agent"

    log_level: str = "INFO"
    log_format: str = "json"  # json | console
    poll_interval_sec: int = 0

    feedback_mode: str = "h3c_syslog"
    syslog_udp_port: int = 514
    h3c_syslog_path: str = ""  # debug-only file tail

    # 设备清单；空则试 /config/devices.yaml、./devices.yaml 等
    devices_config_path: str = ""
    # 兼容旧变量名
    tvs_config_path: str = ""

    def devices_path(self) -> str:
        return self.devices_config_path or self.tvs_config_path
