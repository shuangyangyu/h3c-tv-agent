# h3c-tv-agent（运维）

Docker：Telnet 改 H3C ACL（通断 + 策略路由）+ MQTT；syslog UDP 反馈；可选 **SSH 一键安装 HA 儿童插件**。

仓库：https://github.com/shuangyangyu/h3c-tv-agent

## 使用条件

### 交换机

- 允许 Agent **Telnet** 登录改 ACL  
- **ACL 3000**（通断）规则与 `devices.yaml` 一致  
- 若用策略路由：PBR **permit node + 接口**已存在；Agent 管 3001/3002  
- Syslog：`info-center loghost <Agent可达IP>`，且  
  `info-center source SHELL loghost level informational`  
  （`warning` 会丢掉 `SHELL_CMD`，开关状态不回写）

### MQTT

- Home Assistant 侧 MQTT Broker 可用（含 Discovery）  
- `.env` 中 `MQTT_HOST` / 账号密码正确，Agent ↔ Broker 互通  

### 部署机

- Docker Compose；仓库根目录构建  
- 能访问交换机 Telnet；能收到交换机 syslog（或 fanout 转发）  

### 儿童一键安装（可选）

- `HA_SSH_HOST` / `USER` / `PASSWORD` 可 SSH 进 HA，且能跑 `ha`、`jq`  
- 部署后手动添加一次集成并绑定实体  

详见根 [README.md](../README.md#使用条件)。

## 两个配置文件

| 文件 | 内容 |
|------|------|
| **`.env`** | 连接/密钥、ACL 参数、slog、**HA_SSH_*** |
| **`devices.yaml`** | 设备身份 + `access` / `policy_route` |

### `devices.yaml` 结构

```yaml
devices:
  - key: 主卧电视
    ip: 192.168.1.24
  - key: 测试手机
    ip: 192.168.1.36

access:           # 网络通断 → ACL 3000 + MQTT h3c/tv
  - 主卧电视

policy_route:     # 策略路由 → ACL 3001/3002 + MQTT h3c/route
  - 测试手机
```

未填 `mac` 时 Discovery `slug` 用 IP 去点（`.24` → 实体常为 `switch.h3c_tv_192168124`）。

## 数据流

```text
通断：HA h3c/tv/{key}/set → Telnet ACL 3000 → SHELL syslog → state
策略：HA h3c/route/{key}/set → Telnet 3001/3002 → syslog → state
安装：HA button PRESS → h3c/tv/install_child/set → SSH 部署 h3c_tv_child → 重启 HA
```

- 策略 ON：3001 源 permit → mihomo；3002 源+私网 → PBR deny node → 普通路由  
- 例外网段：`ROUTE_BYPASS_CIDRS`；详见 syhome [`lan/h3c-s5550/h3c-pbr-mihomo.md`](../../../lan/h3c-s5550/h3c-pbr-mihomo.md)

## 部署

在**仓库根目录**（compose context 已改为 `.`）：

```bash
cp agent/.env.example agent/.env
cp agent/devices.yaml.example agent/devices.yaml
# 编辑 .env：H3C_* / MQTT_*；儿童安装再填 HA_SSH_*
docker compose up -d --build
```

交换机：`info-center loghost …` + `SHELL … informational`。  
PBR permit node + 接口挂载需事先存在。

## 环境变量（节选）

| env | 说明 |
|-----|------|
| `H3C_*` / `MQTT_*` | 交换机 / MQTT |
| `ACCESS_*_RULE_*` | 通断规则递加 |
| `ROUTE_ACL_ID` / `ROUTE_BYPASS_*` / `PBR_*` | 策略路由 |
| `MQTT_PREFIX` / `MQTT_ROUTE_PREFIX` | 默认 `h3c/tv` / `h3c/route` |
| `DEVICES_CONFIG_PATH` | 设备 YAML |
| `SYSLOG_UDP_PORT` / `FEEDBACK_MODE` | 反馈 |
| `HA_SSH_HOST` / `USER` / `PASSWORD` | 非空则启用儿童安装按钮 |
| `HA_CUSTOM_COMPONENTS` | 默认 `/config/custom_components` |
| `HA_RESTART_AFTER_INSTALL` | 默认 `true` |
| `HASS_PACKAGE_PATH` | 默认 `/app/hass/h3c_tv_child` |

## 儿童管理

1. `.env` 配置 `HA_SSH_*` 后重建/重启 Agent  
2. HA 设备 **H3C Network Agent** →「安装/更新儿童管理」  
3. 重启完成后添加集成 **H3C TV Child (MQTT)**，绑定 `switch.h3c_tv_*` 与 `media_player`  
4. Lovelace 资源由安装器写入：`/h3c_tv_child/lovelace/h3c-tv-child-card.js?v=0.1.1`  
5. 卡片：`custom:h3c-tv-child-card`

状态看 `sensor.h3c_child_install_status`。详情：[hass/README.md](../hass/README.md)

## 与旧仓库

旧 Telnet 集成已放弃并冻结：https://github.com/shuangyangyu/h3c_s5550_hass  
请只用本仓库，勿并行写交换机。
