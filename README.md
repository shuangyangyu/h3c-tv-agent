# h3c-tv-agent

Docker 服务：通过 Telnet 修改 H3C S5550 ACL（电视通断 + 策略路由），MQTT 对接 Home Assistant；交换机 syslog UDP 做状态反馈。

> HA 自定义集成 `h3c_tv_control`（儿童策略卡片等）在原仓库：  
> https://github.com/shuangyangyu/h3c_s5550_hass

## 目录

| 路径 | 说明 |
|------|------|
| `agent/` | Python 服务、Dockerfile、`devices.yaml`、`.env.example` |
| `docker-compose.yml` | 单容器部署（映射 `514/udp`） |
| `docs/switch_pbr.md` | 交换机 PBR/ACL 与 Agent 对照 |
| `docs/h3c-pbr-mihomo.md` | PBR → mihomo 交换机配置逻辑 |
| `docs/pbr-vpn-exceptions.md` | 双 VPN / Hass 回程场景 |
| `docs/rewrite_development.md` | 开发说明 |

## 快速开始

```bash
cp agent/.env.example agent/.env   # 填写 H3C_* / MQTT_*
cp agent/devices.yaml.example agent/devices.yaml
docker compose up -d --build
```

交换机需：`info-center loghost` 指向本机，且 `SHELL` → loghost 为 informational。  
PBR：`permit node` + 接口挂载需事先存在；Agent 维护 ACL 3001/3002 并补齐 deny node。详见 [docs/h3c-pbr-mihomo.md](docs/h3c-pbr-mihomo.md)。

运维细节：[agent/README.md](agent/README.md)
