# h3c-tv-agent

Docker 服务：Telnet 改 H3C ACL（通断 + 策略路由），MQTT 对接 HA；交换机 syslog UDP 做状态反馈。

## 两个配置文件

| 文件 | 内容 |
|------|------|
| **`.env`** | 连接/密钥、通断/策略路由 ACL 参数、slog |
| **`devices.yaml`** | 设备身份 + **access / policy_route** 引用 key |

### `devices.yaml` 结构

```yaml
devices:          # 所有设备身份
  - key: master_bedroom
    name: 主卧电视
    ip: 192.168.1.24
    mac: cc98-8b23-abaa
  - key: phone_test
    name: 测试手机
    ip: 192.168.1.36
    mac: e49c-67d1-f4a4

access:           # 网络通断 → ACL 3000 + MQTT h3c/tv
  - master_bedroom

policy_route:     # 策略路由 → ACL 3001 + MQTT h3c/route
  - phone_test
```

也可用中文段名：`网络断开` / `策略路由`。  
通断 deny 按 access 顺序 15/25/…；策略路由 permit 按 policy_route 顺序 **100/110/…**（与通断错开，避免 syslog `undo rule N` 歧义）。

## 数据流

```text
通断：HA MQTT h3c/tv/{key}/set → Telnet ACL 3000 → SHELL syslog → h3c/tv/{key}/state
策略：HA MQTT h3c/route/{key}/set → Telnet ACL 3001 → SHELL syslog → h3c/route/{key}/state
```

- 策略 ON = ACL 3001 有该源 IP 的 `permit`（PBR 命中 → mihomo）
- 策略 OFF = 删除该 permit（回普通路由）

## 部署

```bash
cp agent/.env.example agent/.env
cp agent/devices.yaml.example agent/devices.yaml
docker compose up -d --build
```

交换机：`info-center loghost …` + `SHELL … informational`。PBR 策略（`policy-based-route mihomo`）需已挂好；Agent 只改 ACL 3001 成员。

若现网 3001 仍用 rule 10/15，首次 MQTT 开/关会迁到 100/110，并校正可能的通断误报。

## Addon options ↔ `.env`

| option / env | 说明 |
|--------------|------|
| `H3C_*` / `MQTT_*` | 连接 |
| `ACCESS_*_RULE_*` | 通断规则递加 |
| `ROUTE_ACL_ID` / `ROUTE_RULE_*` | 策略路由 ACL / 规则号 |
| `MQTT_PREFIX` / `MQTT_ROUTE_PREFIX` | 默认 `h3c/tv` / `h3c/route` |
| `DEVICES_CONFIG_PATH` | 设备 YAML |
| `SYSLOG_UDP_PORT` / `FEEDBACK_MODE` | 反馈 |

## 与旧插件

旧 `h3c_tv_control` 约 60s 轮询，与 MQTT 开关互不同步。稳定后禁用旧集成。
