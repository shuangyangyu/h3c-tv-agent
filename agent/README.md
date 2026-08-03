# h3c-tv-agent

独立 Docker 服务：经 **Telnet** 改 H3C S5550 ACL，经 **MQTT** 对接 Home Assistant；用交换机 **syslog（UDP 514）** 做 Switch 状态反馈。  
面向将来打成 **HA Addon**（单容器）。

开发背景见 [docs/rewrite_development.md](../docs/rewrite_development.md)。

## 数据流

```text
HA MQTT Switch ──set──► Agent ──Telnet──► H3C ACL 3000
                              ▲
HA MQTT Switch ◄──state───────┘
                              │
                    H3C SHELL_CMD syslog UDP:514
```

- **下发**：`h3c/tv/{tv}/set` → Telnet `undo rule` / `rule N deny`
- **反馈**：交换机 syslog → 进程内 UDP 解析 → `h3c/tv/{tv}/state`（`attr.feedback_source=h3c_syslog`）
- 启动时 Telnet 查一次 ACL 做初始对齐；稳态靠 syslog，默认不轮询（`POLL_INTERVAL_SEC=0`）

## 目录

```text
agent/
  Dockerfile
  requirements.txt
  .env.example
  src/h3c_tv_agent/
    __main__.py          # run / status
    config.py
    service.py           # 队列 + worker + syslog
    mqtt_app.py          # Discovery + set/state
    telnet_switch.py     # telnetlib3.telnetlib
    syslog_watcher.py    # UDP 514 + 行解析
    models.py            # 四台电视表
    logging_setup.py     # structlog JSON
  tests/
```

## 部署（241 示例）

```bash
cd /path/to/h3c-s5550
cp agent/.env.example agent/.env   # 填 H3C_PASSWORD / MQTT_*
docker compose up -d --build

docker logs -f h3c-tv-agent
# 应看到：syslog UDP listener started / mqtt connected / acl polled
```

Compose 映射 **`514/udp`**。交换机：

```text
info-center loghost 192.168.1.241
info-center source SHELL loghost level informational
save force
```

> `SHELL` 若仍是 `warning`，`SHELL_CMD` 不会上送，MQTT 状态不会跟 ACL 变化。

本机调试：

```bash
cd agent
cp .env.example .env
PYTHONPATH=src python -m h3c_tv_agent status   # 查 ACL
PYTHONPATH=src python -m h3c_tv_agent run      # 需本机可绑 514 或改 SYSLOG_UDP_PORT
```

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `H3C_HOST` / `H3C_PORT` | `192.168.1.254` / `23` | 交换机 |
| `H3C_USER` / `H3C_PASSWORD` | — | Telnet 账号（勿提交） |
| `H3C_ACL_ID` | `3000` | ACL |
| `MQTT_HOST` / `MQTT_PORT` | — / `1883` | 现网多为 HA `192.168.1.249` |
| `MQTT_USER` / `MQTT_PASSWORD` | — | Mosquitto |
| `MQTT_PREFIX` | `h3c/tv` | Topic 前缀 |
| `MQTT_CLIENT_ID` | `h3c-tv-agent` | |
| `FEEDBACK_MODE` | `h3c_syslog` | `h3c_syslog` \| `structured_log`（调试） |
| `SYSLOG_UDP_PORT` | `514` | `0`=不监听 |
| `H3C_SYSLOG_PATH` | 空 | 可选文件 tail |
| `POLL_INTERVAL_SEC` | `0` | `>0` 时周期查 ACL |
| `LOG_LEVEL` | `INFO` | |

## MQTT

| Topic | 方向 | Payload |
|-------|------|---------|
| `{prefix}/{tv}/set` | HA→Agent | `ON` / `OFF` |
| `{prefix}/{tv}/state` | Agent→HA | `ON` / `OFF` |
| `{prefix}/{tv}/attr` | Agent→HA | JSON（含 `feedback_source`） |
| `{prefix}/status` | Agent→HA | `online` / `offline`（LWT） |

`tv`：`master_bedroom`(15) / `living_room`(25) / `elder_room`(35) / `study_room`(45)。

启动时发 MQTT Discovery，HA 出现设备 **H3C TV Agent**。

手工测：

```bash
mosquitto_pub -h 192.168.1.249 -t h3c/tv/master_bedroom/set -m OFF -u … -P …
mosquitto_sub -h 192.168.1.249 -t 'h3c/tv/master_bedroom/#' -v -u … -P …
```

## 与旧插件并存

| | 新 Agent | 旧 `h3c_tv_control` |
|--|----------|---------------------|
| 控制 | MQTT → Telnet | HA 内 Telnet |
| 状态 | syslog 近实时 | Coordinator **约 60s** 轮询 |
| 实体 | MQTT Discovery | 集成实体 |

两边**互不订阅**。用新开关改 ACL 后，老开关要等下次 poll 才变——属预期，不是 ACL 没改。稳定后禁用旧集成。

## 验收清单（已在现网验证过的路径）

1. MQTT `set OFF/ON` → `display acl 3000` 出现/消失对应 `rule N deny`
2. Agent 日志 `acl updated` + `syslog matched`
3. MQTT `state` / `attr.feedback_source=h3c_syslog` 同步
4. 交换机上直接 `undo rule` / `rule … deny` → 同样走 syslog → MQTT

## 解析注意

只匹配带 `Command is` / `Commandline is` 的 `SHELL_CMD` 行，避免 `LOGIN_FAILED` 把命令当用户名误触发。
