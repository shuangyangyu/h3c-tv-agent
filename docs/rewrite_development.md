# h3c-tv-agent 开发文档

> 独立仓库（由原 `h3c_s5550_hass` 的 rewrite 分出）：**Docker 单容器** Telnet 改 ACL + MQTT + 进程内 UDP syslog。  
> **仓库迁址**：旧 https://github.com/shuangyangyu/h3c_s5550_hass（已 Archived）→ 新 https://github.com/shuangyangyu/h3c-tv-agent  
> HA 儿童插件随本仓库 `hass/h3c_tv_child/`，MQTT 按钮一键安装。

运维速查：[agent/README.md](../agent/README.md)  
交换机 PBR/ACL：[`lan/h3c-s5550/h3c-pbr-mihomo.md`](../../../lan/h3c-s5550/h3c-pbr-mihomo.md)

---

## 1. 目标与原则

| 项 | 说明 |
|----|------|
| 控制面 | Python 多线程服务，**Telnet** 读写 H3C S5550 ACL 3000 |
| 与 HA | **MQTT**（命令 / 状态）；Discovery 生成 Switch |
| 部署 | **单容器**（内嵌 syslog UDP:514） |
| 反馈 | 交换机 **SHELL_CMD syslog** → Agent 解析 → MQTT `state` |
| 语言 | **Python 3.11+**（镜像 3.12） |

**不做（Agent 控制面）**：HA 进程内 Telnet；独立 syslog-ng / Loki 栈。  
**儿童策略**：源码随本仓库 [`hass/h3c_tv_child/`](../hass/h3c_tv_child/)；运行时由 MQTT 按钮 `button.h3c_install_child` 经 SSH 部署到 HA（见根 README）。

---

## 2. 总体架构

```text
┌─────────────────┐     MQTT      ┌──────────────────────────────┐
│  Home Assistant │◄────────────►│  h3c-tv-agent (单容器)        │
│  MQTT Switch    │  set / state │  · MQTT（paho）               │
└─────────────────┘               │  · Telnet worker + 锁         │
                                  │  · Syslog UDP :514            │
                                  │  · structlog（排错）           │
                                  └───────┬──────────────▲────────┘
                                          │ Telnet :23   │ UDP 514
                                          ▼              │
                                 ┌─────────────────┐     │
                                 │  H3C S5550      │─────┘
                                 │  ACL 3000       │  info-center loghost
                                 └─────────────────┘
```

数据流：

1. HA Switch → MQTT **set** → Agent Telnet 改 ACL  
2. 交换机 **SHELL_CMD** syslog → Agent **UDP 514**  
3. 解析 `Command is undo rule N` / `rule N deny …` → MQTT **state**  
4. 手工 / 老插件改 ACL，只要 SHELL 上送 loghost，新开关同样更新  

structlog **不是** Switch 反馈源。

---

## 3. 技术选型

| 能力 | 选型 | 说明 |
|------|------|------|
| 运行时 | Python 3.12（Docker） | 本地 3.11+ 亦可 |
| 容器 | Docker Compose | 现网：`192.168.1.241` |
| HA 通讯 | MQTT 3.1.1 + Discovery | Mosquitto 在 HA（`192.168.1.249`） |
| 交换机 | Telnet | `telnetlib3.telnetlib` |
| 并发 | `threading` + `queue` | MQTT / Worker / Syslog 分离 |
| 日志 | `structlog` JSON | 仅运维排错 |

### 3.1 运行时依赖

```text
paho-mqtt>=2.1.0,<3
structlog>=24.1.0
pydantic-settings>=2.2.0
telnetlib3>=2.0.0
PyYAML>=6.0.1
```

**不选（本期）**：`asyncio`/`aiomqtt` 全家桶、SSH、独立 syslog-ng、Celery。

### 3.2 Telnet

Python 3.13 已移除标准库 `telnetlib`。本机 S5550 上 **`telnetlib3.telnetlib`（兼容层）** 登录后可正常交互；`telnetlib3.sync.TelnetConnection` 曾出现登录后无回显，故不用。

提示符可能是 `Login:`（不是 `Username:`），代码用正则兼容。

---

## 4. MQTT 约定

默认前缀：`h3c/tv/`。

| 方向 | Topic | Payload |
|------|-------|---------|
| HA → Agent | `h3c/tv/{tv_key}/set` | `ON` / `OFF` |
| Agent → HA | `h3c/tv/{tv_key}/state` | `ON` / `OFF` |
| Agent → HA | `h3c/tv/{tv_key}/attr` | JSON（`feedback_source` 等） |
| Agent → HA | `h3c/tv/status` | `online` / `offline`（LWT） |

| Key | 名称 | IP | Deny Rule |
|-----|------|-----|-----------|
| `master_bedroom` | 主卧 | 192.168.1.24 | 15 |
| `living_room` | 客厅 | 192.168.1.25 | 25 |
| `elder_room` | 老人房 | 192.168.1.26 | 35 |
| `study_room` | 书房 | 192.168.1.27 | 45 |

ACL：`3000`。启动发布 `homeassistant/switch/.../config` Discovery。

---

## 5. Switch 反馈：H3C syslog

### 5.1 路径（已验证）

```text
任何人改 ACL → SHELL_CMD syslog → Agent UDP:514 → parse → MQTT state
```

单容器内嵌监听，**不**再部署独立 `h3c-syslog` / 旧 `/docker/syslog`（会抢 514）。

### 5.2 识别规则

必须含 `Command is` 或 `Commandline is`（避免 `LOGIN_FAILED` 误匹配）：

| syslog 片段 | MQTT |
|-------------|------|
| `Command is undo rule 15` | `master_bedroom` → `ON` |
| `Command is rule 15 deny ip source 192.168.1.24 0` | `master_bedroom` → `OFF` |
| 25 / 35 / 45 | 客厅 / 老人房 / 书房 |

### 5.3 交换机配置（必做）

```text
system-view
info-center loghost 192.168.1.241
info-center source SHELL loghost level informational
save force
```

若 `SHELL` 为 `level warning`，informational 级的 `SHELL_CMD` **不会上送**，整条反馈链失效。

### 5.4 Agent 行为

- `H3CSyslogUdpServer`：`SYSLOG_UDP_PORT`（默认 514）  
- 命中 → MQTT，`feedback_source=h3c_syslog`  
- Telnet **只下发**；状态以 syslog 为准（启动 bootstrap 查一次 ACL）  
- 可选 `H3C_SYSLOG_PATH` 文件 tail（默认关）  

---

## 6. 多线程模型

```text
Main
 ├─ MQTT（paho loop）：set → CommandQueue
 ├─ Worker（单线程）：Telnet 改 ACL（switch_lock）
 ├─ Syslog UDP：514 → parse → publish state
 ├─ Poller（可选，默认关）
 └─ structlog → stdout
```

约束：MQTT 回调禁止直接 Telnet；同一时刻一个交换机会话。

```python
def on_mqtt_message(tv_key: str, payload: str) -> None:
    command_queue.put(Command(tv=tv_key, want=payload))

def worker_loop() -> None:
    while True:
        cmd = command_queue.get()
        with switch_lock:
            telnet_apply(cmd)   # 只下发；state 由 syslog 线程发布
```

---

## 7. 配置（两个文件）

| 文件 | 用途 |
|------|------|
| `agent/.env` | 连接/密钥、ACCESS 规则递加、LOG_*、ROUTE_ACL_ID 占位、挂口白名单 |
| `agent/devices.yaml` | 设备身份 + `access`（通断）/ `policy_route`（策略路由）引用 key |


完整说明与 Addon 对照：[agent/README.md](../agent/README.md)。

```text
H3C_ACL_ID=3000
ACCESS_DENY_RULE_BASE=15
ACCESS_DENY_RULE_STEP=10
ROUTE_ACL_ID=3001
LOG_FORMAT=json
DEVICES_CONFIG_PATH=/app/devices.yaml
```

---

## 8. Docker

```text
h3c-tv-agent/
  agent/                 # .env.example + devices.yaml(.example)
  docker-compose.yml     # 514/udp + 挂载 devices.yaml
  docs/
```

```yaml
services:
  h3c-tv-agent:
    build: ./agent
    ports:
      - "514:514/udp"
    env_file: ./agent/.env
    environment:
      DEVICES_CONFIG_PATH: /app/devices.yaml
    volumes:
      - ./agent/devices.yaml:/app/devices.yaml:ro
```

---

## 9. 里程碑

| 阶段 | 交付 | 状态 |
|------|------|------|
| M0 | Telnet status / Docker | ✅ |
| M1 | MQTT state + Discovery | ✅ |
| M2 | MQTT set → ACL | ✅ |
| M3 | structlog | ✅ |
| M4 | 队列 + 锁；syslog 反馈 | ✅ 现网验证 |
| M5 | 儿童策略 → `hass/h3c_tv_child/` + MQTT 安装按钮 | 完成 |
| — | HA Addon 打包 | 待做（架构已按单容器对齐） |

---

## 10. 新旧对比与并存

| 代际 | 形态 |
|------|------|
| v0 | YAML + `command_line` 脚本 |
| v1 | `custom_components/h3c_tv_control`（HA 内 Telnet，**~60s** 轮询） |
| **Rewrite** | Docker Agent + MQTT + **syslog 反馈** |

### 10.1 并存注意

- 新、旧是**两套实体**，互不订对方状态。  
- 用 MQTT 开关改 ACL 后，旧插件要等 **~60s** poll 才变——**不是 ACL 没改**。  
- 稳定后禁用旧集成，避免双写抢 Telnet。

### 10.2 Rewrite 好处（摘要）

故障隔离、只重建 Agent、`docker logs`+MQTT 可观测、可部署在 241、将来 Addon 单容器即可。

---

## 11. 测试清单

- [x] MQTT set OFF/ON → ACL 出现/消失对应 deny  
- [x] syslog `SHELL_CMD` → `syslog matched` → MQTT state/attr  
- [x] 交换机上直接改 ACL → 新开关更新  
- [x] `SHELL` informational + `save`  
- [ ] Telnet 失败 → `status=offline`  
- [ ] 并发拨动多台电视排队无错乱  
- [ ] 容器重启后 LWT / 全量 state  
- [ ] 禁用旧集成后仅 Agent 长期稳定  

---

## 12. 参考

- Agent 运维：[agent/README.md](../agent/README.md)  
- 现网 ACL / 电视表：`docs/h3c_integration_requirements.md`  
- 旧脚本：`scripts/tv_internet/tv_internet_control.py`  
- 分支：https://github.com/shuangyangyu/h3c_s5550_hass/tree/rewrite
