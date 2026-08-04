# h3c-tv-agent

Docker 服务：Telnet 改 H3C ACL（通断 + 策略路由），MQTT 对接 HA；交换机 syslog UDP 做状态反馈。

## 两个配置文件

| 文件 | 内容 |
|------|------|
| **`.env`** | 连接/密钥、通断/策略路由 ACL 参数、slog |
| **`devices.yaml`** | 设备身份 + **access / policy_route** 引用 key |

### `devices.yaml` 结构

```yaml
devices:
  - key: 主卧电视
    ip: 192.168.1.24
  - key: 测试手机
    ip: 192.168.1.36

access:           # 网络通断 → ACL 3000 + MQTT h3c/tv
  - 主卧电视

policy_route:     # 策略路由 → ACL 3001 + MQTT h3c/route
  - 测试手机
```

`mac` / `name` 可省略（name 默认等于 key；未填 mac 时 Discovery 用 IP 生成实体 id）。

## 数据流

```text
通断：HA MQTT h3c/tv/{key}/set → Telnet ACL 3000 → SHELL syslog → h3c/tv/{key}/state
策略：HA MQTT h3c/route/{key}/set → Telnet ACL 3001 → SHELL syslog → h3c/route/{key}/state
```

- 策略 ON：
  - ACL **3001**：`permit` 源 IP → PBR permit node → mihomo
  - ACL **3002**：`permit` 源+私网目的 → PBR **deny node** → 普通路由（局域网 / WG / IPsec）
- 策略 OFF：清空该源在 3001/3002 上的相关 rule
- Agent 会幂等创建 `policy-based-route mihomo deny node 5` + `if-match acl 3002`（permit node 需已存在）
- 例外网段：`ROUTE_BYPASS_CIDRS`；见 [`network/pbr-vpn-exceptions.md`](../../network/pbr-vpn-exceptions.md)

## 部署

```bash
cp agent/.env.example agent/.env
cp agent/devices.yaml.example agent/devices.yaml
docker compose up -d --build
```

交换机：`info-center loghost …` + `SHELL … informational`。  
**PBR permit node + 接口挂载需事先存在**；Agent 维护 ACL 3001/3002，并幂等补齐 deny node。  

交换机逻辑详解：[`../../network/h3c-pbr-mihomo.md`](../../network/h3c-pbr-mihomo.md) · 仓库索引 [`../docs/switch_pbr.md`](../docs/switch_pbr.md)

若现网 3001 仍用旧 rule 号，首次开/关会迁到 100/110，并校正可能的通断误报。

## Addon options ↔ `.env`

| option / env | 说明 |
|--------------|------|
| `H3C_*` / `MQTT_*` | 连接 |
| `ACCESS_*_RULE_*` | 通断规则递加 |
| `ROUTE_ACL_ID` / `ROUTE_RULE_*` | 策略路由 ACL 3001 / 规则号 |
| `ROUTE_BYPASS_ACL_ID` / `ROUTE_BYPASS_CIDRS` | 旁路 ACL 3002 / 私网 CIDR |
| `PBR_NAME` / `PBR_DENY_NODE` | 默认 `mihomo` / `5` |
| `MQTT_PREFIX` / `MQTT_ROUTE_PREFIX` | 默认 `h3c/tv` / `h3c/route` |
| `DEVICES_CONFIG_PATH` | 设备 YAML |
| `SYSLOG_UDP_PORT` / `FEEDBACK_MODE` | 反馈 |

## 与旧插件

旧 `h3c_tv_control` 约 60s 轮询，与 MQTT 开关互不同步。稳定后禁用旧集成。
