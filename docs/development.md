# h3c-tv-agent 开发说明

Docker 单容器：Telnet 改 H3C ACL + MQTT + 进程内 syslog UDP；镜像打包 HA 儿童插件，可由 MQTT 按钮经 SSH 部署。

仓库：https://github.com/shuangyangyu/h3c-tv-agent  

运维：[agent/README.md](../agent/README.md) · 根 [README.md](../README.md) · 儿童 [hass/README.md](../hass/README.md)  
交换机 PBR/ACL：[`lan/h3c-s5550/h3c-pbr-mihomo.md`](../../../lan/h3c-s5550/h3c-pbr-mihomo.md)

---

## 1. 目标与原则

| 项 | 说明 |
|----|------|
| 控制面 | Python 多线程；**Telnet** 读写 ACL（通断 3000 / 策略 3001+3002） |
| 与 HA | **MQTT** Discovery（Switch / Button / Sensor） |
| 部署 | **单容器**（内嵌 syslog UDP；现网 `127.0.0.1:1516→514`） |
| 反馈 | 交换机 **SHELL_CMD syslog** → Agent → MQTT `state` |
| 儿童策略 | 不在 Agent 内计时；源码 `hass/h3c_tv_child/`，SSH 装到 HA |
| 语言 | Python 3.11+（镜像 3.12） |

**不做**：HA 进程内 Telnet；独立 syslog-ng / Loki；儿童计时进 Agent。

---

## 2. 总体架构

```text
┌──────────────────────────────┐     MQTT      ┌──────────────────────────────┐
│  Home Assistant (.249)       │◄────────────►│  h3c-tv-agent (.241 容器)     │
│  · MQTT Switch（通断/PBR）   │  set/state   │  · MQTT（paho）               │
│  · h3c_tv_child（儿童策略）  │              │  · Telnet worker + 锁         │
│  · button 安装儿童管理       │──PRESS──────►│  · Syslog UDP                 │
│                              │              │  · hass_install（paramiko）   │
└──────────────────────────────┘              └───────┬──────────────▲────────┘
        ▲ SSH 部署插件+卡片                            │ Telnet :23   │ UDP 514
        └──────────────────────────────────────────────┤              │
                                                       ▼              │
                                              ┌─────────────────┐     │
                                              │  H3C S5550      │─────┘
                                              │  ACL / PBR      │
                                              └─────────────────┘
```

1. HA Switch → MQTT **set** → Agent Telnet 改 ACL  
2. **SHELL_CMD** syslog → Agent → MQTT **state**  
3. 儿童策略在 HA 计时；到期 `call_service` 打 MQTT 代理开关  
4. `button.h3c_install_child` → SSH 部署 `h3c_tv_child` + Lovelace 资源 + `ha core restart`

---

## 3. 技术选型

| 能力 | 选型 |
|------|------|
| 运行时 | Python 3.12（Docker） |
| 容器 | Compose，**构建上下文 = 仓库根** |
| HA 通讯 | MQTT 3.1.1 + Discovery |
| 交换机 | `telnetlib3.telnetlib` |
| 一键安装 | **paramiko** SSH/SFTP |
| 并发 | `threading` + `queue` |
| 日志 | `structlog` JSON（排错，非 Switch 反馈源） |

```text
paho-mqtt>=2.1.0,<3
structlog>=24.1.0
pydantic-settings>=2.2.0
telnetlib3>=2.0.0
PyYAML>=6.0.1
paramiko>=3.4.0,<4
```

---

## 4. MQTT 约定

### 4.1 通断（前缀 `h3c/tv`）

| 方向 | Topic | Payload |
|------|-------|---------|
| HA → Agent | `h3c/tv/{key}/set` | `ON` / `OFF` |
| Agent → HA | `h3c/tv/{key}/state` | `ON` / `OFF` |
| Agent → HA | `h3c/tv/{key}/attr` | JSON |
| Agent → HA | `h3c/tv/status` | `online` / `offline`（LWT） |

Discovery：`homeassistant/switch/h3c_tv_{slug}/config`  
`slug` = mac 字母数字，否则 IP 去点（`192.168.1.24` → `192168124`）。

现网电视 deny（ACL 3000）：`.24/.25/.26/.27` → 15/25/35/45。

### 4.2 策略路由（前缀 `h3c/route`）

`h3c/route/{key}/set|state|attr`；Discovery `homeassistant/switch/h3c_route_{slug}/config`。

### 4.3 儿童插件安装

配置 `HA_SSH_*` 后启用：

| 实体 | 说明 |
|------|------|
| `button.h3c_install_child` | `h3c/tv/install_child/set` ← `PRESS` |
| `sensor.h3c_child_install_status` | `h3c/tv/install_child/state` JSON |

`status`：`not_installed` / `installed` / `installing` / `ok` / `error`。

---

## 5. Syslog 反馈

```text
改 ACL → SHELL_CMD → Agent UDP → parse → MQTT state
```

- 须含 `Command is` / `Commandline is`  
- `info-center source SHELL loghost level informational`  
- 现网映射见 `docker-compose.yml`（`1516:514/udp`）

---

## 6. 多线程

```text
Main
 ├─ MQTT：set → 队列；install_child → 安装线程
 ├─ Worker：Telnet（switch_lock）
 ├─ Syslog UDP
 ├─ 启动 probe 儿童插件是否已装
 └─ structlog
```

---

## 7. 配置

| 文件 | 用途 |
|------|------|
| `agent/.env` | H3C / MQTT / ACL / `HA_SSH_*` / `HASS_PACKAGE_PATH` |
| `agent/devices.yaml` | `devices` + `access` / `policy_route` |

`HA_SSH_PASSWORD` 为空则不发布安装按钮。完整变量见 `agent/.env.example`。

---

## 8. Docker

```text
h3c-tv-agent/
  agent/
  hass/h3c_tv_child/     → 镜像 /app/hass/h3c_tv_child
  docker-compose.yml     context: .  dockerfile: agent/Dockerfile
  docs/
```

```bash
docker compose up -d --build   # 仓库根目录
```

安装器打包跳过 `frontend/`，只部署 `.py` / `www` / translations。

---

## 9. 里程碑

| 阶段 | 交付 | 状态 |
|------|------|------|
| 控制面 | Telnet / MQTT / syslog / 锁队列 | ✅ |
| 儿童 | `hass/h3c_tv_child` + MQTT 一键安装 | ✅ |
| Addon | HA Addon 包装 | 待做 |

---

## 10. 测试清单

- [x] MQTT 通断 / PBR → ACL + syslog 回写  
- [x] 一键安装 → 集成 → 通断 + 策略拦截  
- [x] 安装按钮 / 状态传感器  
- [ ] Telnet 失败 → `status=offline`  
- [ ] 并发多台排队  

---

## 11. 参考

- [agent/README.md](../agent/README.md)  
- [hass/docs/](../hass/docs/)  
- [`lan/h3c-s5550/h3c-pbr-mihomo.md`](../../../lan/h3c-s5550/h3c-pbr-mihomo.md)  
