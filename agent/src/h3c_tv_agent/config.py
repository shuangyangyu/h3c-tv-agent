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
    # 策略路由 ACL 3001（源 permit → mihomo）；规则号 100/110…
    route_acl_id: int = 3001
    route_rule_base: int = 100
    route_rule_step: int = 10
    # 旁路 ACL 3002（源+私网目的 permit）+ PBR deny node → 普通路由
    route_bypass_acl_id: int = 3002
    route_bypass_cidrs: str = "192.168.0.0/16,10.0.0.0/8"
    pbr_name: str = "mihomo"
    pbr_deny_node: int = 5
    # 逗号分隔接口名（记录用；permit node / 接口挂载需已存在）
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
    # 通断 Telnet 成功后等待 SHELL syslog 的秒数；0=关闭
    syslog_feedback_timeout_sec: float = 20.0

    # 设备清单；空则试 /config/devices.yaml、./devices.yaml 等
    devices_config_path: str = ""
    # 兼容旧变量名
    tvs_config_path: str = ""

    # HA 儿童插件一键安装（MQTT Discovery 按钮 → SSH 部署）
    hass_package_path: str = "/app/hass/h3c_tv_child"
    ha_ssh_host: str = ""
    ha_ssh_port: int = 22
    ha_ssh_user: str = "root"
    ha_ssh_password: str = ""
    ha_custom_components: str = "/config/custom_components"
    ha_restart_after_install: bool = True

    def devices_path(self) -> str:
        return self.devices_config_path or self.tvs_config_path

    @property
    def child_install_enabled(self) -> bool:
        return bool(self.ha_ssh_host and self.ha_ssh_user and self.ha_ssh_password)