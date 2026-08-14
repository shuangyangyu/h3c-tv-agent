# h3c-tv-agent 开发文档

> **仓库**：https://github.com/shuangyangyu/h3c-tv-agent  
> 由原 `h3c_s5550_hass` rewrite 分出；旧仓已 Archived：https://github.com/shuangyangyu/h3c_s5550_hass  
> **形态**：Docker 单容器 — Telnet 改 ACL + MQTT + 进程内 syslog UDP；镜像内打包 HA 儿童插件，可由 MQTT 按钮 SSH 部署。

运维速查：[agent/README.md](../agent/README.md) · 根 [README.md](../README.md)  
儿童插件：[hass/README.md](../hass/README.md)  
交换机 PBR/ACL：[`lan/h3c-s5550/h3c-pbr-mihomo.md`](../../../lan/h3c-s5550/h3c-pbr-mihomo.md)

---

## 1. 目标与原则

| 项 | 说明 |
|----|------|
| 控制面 | Python 多线程；**Telnet** 读写 H3C ACL（通断 3000 / 策略 3001+3002） |
| 与 HA | **MQTT** Discovery（Switch / Button / Sensor） |
| 部署 | **单容器**（内嵌 syslog UDP；现网宿主机映射 `127.0.0.1:1516→514`） |
| 反馈 | 交换机 **SHELL_CMD syslog** → Agent → MQTT `state` |
| 儿童策略 | 不在 Agent 进程内计时；源码在 `hass/h3c_tv_child/`，经 SSH 装到 HA |
| 语言 | Python 3.11+（镜像 3.12） |

**不做**：HA 进程内 Telnet；独立 syslog-ng / Loki；把儿童计时塞进 Agent。

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

数据流：

1. HA Switch → MQTT **set** → Agent Telnet 改 ACL  
2. 交换机 **SHELL_CMD** syslog → Agent → MQTT **state**  
3. 儿童策略在 HA 内计时；到期则 `call_service` 打 MQTT 代理开关  
4. 按 `button.h3c_install_child` → Agent SSH 覆盖 `/config/custom_components/h3c_tv_child` + Lovelace 资源 + `ha core restart`

---

## 3. 技术选型

| 能力 | 选型 |
|------|------|
| 运行时 | Python 3.12（Docker） |
| 容器 | Compose，**构建上下文 = 仓库根**（`dockerfile: agent/Dockerfile`） |
| HA 通讯 | MQTT 3.1.1 + Discovery |
| 交换机 | `telnetlib3.telnetlib` |
| 一键安装 | **paramiko** SSH/SFTP → HA |
| 并发 | `threading` + `queue` |
| 日志 | `structlog` JSON（排错，非 Switch 反馈源） |

### 3.1 依赖

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

### 4.1 通断（默认前缀 `h3c/tv`）

| 方向 | Topic | Payload |
|------|-------|---------|
| HA → Agent | `h3c/tv/{key}/set` | `ON` / `OFF` |
| Agent → HA | `h3c/tv/{key}/state` | `ON` / `OFF` |
| Agent → HA | `h3c/tv/{key}/attr` | JSON |
| Agent → HA | `h3c/tv/status` | `online` / `offline`（LWT） |

Discovery：`homeassistant/switch/h3c_tv_{slug}/config`  
`slug` = mac 字母数字，否则 IP 去点（如 `192.168.1.24` → `192168124`）→ 实体常为 `switch.h3c_tv_192168124`。

现网电视（ACL 3000 deny）：

| devices.yaml key | IP | Deny |
|------------------|-----|------|
| 主卧电视等中文 key | .24/.25/.26/.27 | 15/25/35/45 |

### 4.2 策略路由（前缀 `h3c/route`）

| 方向 | Topic |
|------|-------|
| set / state / attr | `h3c/route/{key}/set` 等 |

Discovery：`homeassistant/switch/h3c_route_{slug}/config`。

### 4.3 儿童插件安装

配置 `HA_SSH_*` 后启用：

| 实体 | Topic / 说明 |
|------|----------------|
| `button.h3c_install_child` | `h3c/tv/install_child/set` ← `PRESS` |
| `sensor.h3c_child_install_status` | `h3c/tv/install_child/state`（JSON：`status`/`message`/`version`） |

`status`：`not_installed` / `installed` / `installing` / `ok` / `error`。

---

## 5. Switch 反馈：H3C syslog

```text
改 ACL → SHELL_CMD syslog → Agent UDP → parse → MQTT state
```

- 须含 `Command is` / `Commandline is`  
- `info-center source SHELL loghost level informational`（warning 会丢 SHELL_CMD）  
- 现网常经 syslog-fanout；容器映射见 `docker-compose.yml`（`1516:514/udp`）

---

## 6. 多线程模型

```text
Main
 ├─ MQTT：set → 队列；install_child → HassChildInstaller 线程
 ├─ Worker：Telnet（switch_lock）
 ├─ Syslog UDP
 ├─ 启动后 probe 儿童插件是否已装
 └─ structlog → stdout
```

---

## 7. 配置

| 文件 | 用途 |
|------|------|
| `agent/.env` | H3C / MQTT / ACL / **HA_SSH_*** / `HASS_PACKAGE_PATH` |
| `agent/devices.yaml` | `devices` + `access` / `policy_route` |

儿童安装相关 env 见 `agent/.env.example`（`HA_SSH_HOST` 等）。空密码则不发布安装按钮。

---

## 8. Docker

```text
h3c-tv-agent/
  agent/                 # 代码、.env、devices.yaml
  hass/h3c_tv_child/     # 打进镜像 /app/hass/h3c_tv_child
  docker-compose.yml     # context: .  dockerfile: agent/Dockerfile
  docs/
```

```bash
# 在仓库根目录
docker compose up -d --build
```

镜像内 `COPY hass/h3c_tv_child`；安装器打包时跳过 `frontend/` 源码，只部署 `.py` / `www` / translations。

---

## 9. 里程碑

| 阶段 | 交付 | 状态 |
|------|------|------|
| M0–M4 | Telnet / MQTT / syslog / 锁队列 | ✅ |
| M5 | `hass/h3c_tv_child` + MQTT 一键安装 | ✅ 现网验证 |
| — | HA Addon 包装 | 待做 |

---

## 10. 与旧方案

| 代际 | 形态 | 状态 |
|------|------|------|
| v1 | `h3c_tv_control` HA 内 Telnet | **已放弃**，仓 Archived |
| **本仓库** | Agent MQTT + syslog；儿童在 HA | **现行** |

不要再装旧集成；线上已移除。

---

## 11. 测试清单

- [x] MQTT 通断 / PBR → ACL + syslog 回写  
- [x] 儿童：清理后一键安装 → 添加集成 → 通断 + 夜间策略拦截  
- [x] Discovery 安装按钮 / 状态传感器  
- [ ] Telnet 失败 → `status=offline`  
- [ ] 并发多台排队  

---

## 12. 参考

- 运维：[agent/README.md](../agent/README.md)  
- 儿童需求 / 卡片：[hass/docs/](../hass/docs/)  
- PBR：[`lan/h3c-s5550/h3c-pbr-mihomo.md`](../../../lan/h3c-s5550/h3c-pbr-mihomo.md)  
- 旧仓（冻结）：https://github.com/shuangyangyu/h3c_s5550_hass  
