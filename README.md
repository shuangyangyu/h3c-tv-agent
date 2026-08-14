# h3c-tv-agent

Docker 服务：Telnet 改 H3C S5550 ACL（电视通断 + 策略路由）+ MQTT；内嵌 syslog UDP；**并带 HA 儿童管理插件包，可通过 MQTT 按钮一键安装/更新**。

> 旧 Telnet 集成 `h3c_tv_control` 已放弃并冻结：  
> https://github.com/shuangyangyu/h3c_s5550_hass → **新地址** https://github.com/shuangyangyu/h3c-tv-agent

## 目录

| 路径 | 说明 |
|------|------|
| **`config/`** | **用户配置**（与 compose 并列）：`.env` + `devices.yaml` |
| `agent/` | Python 源码、Dockerfile |
| `hass/h3c_tv_child/` | HA 儿童策略集成 + Lovelace 卡片（随镜像打包） |
| `docker-compose.yml` | 构建上下文为仓库根目录 |
| `docs/development.md` | 开发说明 |
| [`../../lan/h3c-s5550/h3c-pbr-mihomo.md`](../../lan/h3c-s5550/h3c-pbr-mihomo.md) | PBR / ACL |

## 文档入口

| 文档 | 内容 |
|------|------|
| [config/README.md](config/README.md) | 配置目录说明 |
| [agent/README.md](agent/README.md) | 运维：配置字段、部署、环境变量、儿童安装 |
| [docs/development.md](docs/development.md) | 架构 / MQTT / syslog / 里程碑 |
| [hass/README.md](hass/README.md) | 儿童集成与卡片 |

## 使用条件

上线前需同时满足下列条件，否则通断/反馈/发现会不完整。

### 1. 交换机（H3C）

| 要求 | 说明 |
|------|------|
| Telnet 管理 | Agent 用账号登录改 ACL（现网如 `hass_robot`） |
| ACL 通断 | ACL **3000** 已存在；各电视 deny rule 与 `config/devices.yaml` / `.env` 递加规则一致 |
| 策略路由（可选） | PBR 名（如 `mihomo`）的 **permit node + 接口挂载已事先配好**；Agent 维护 3001/3002 并补 deny node |
| Syslog 回传 | `info-center loghost` 指向 Agent 可达地址；**`SHELL` → loghost 为 informational**（否则无 `SHELL_CMD`，MQTT 状态不更新） |

PBR/ACL 细节：[`lan/h3c-s5550/h3c-pbr-mihomo.md`](../../lan/h3c-s5550/h3c-pbr-mihomo.md)

### 2. MQTT

| 要求 | 说明 |
|------|------|
| Broker | HA 已安装并启用 MQTT（现网 Mosquitto @ `.249:1883`） |
| 账号 | `config/.env` 中 `MQTT_USER` / `MQTT_PASSWORD` 可读写 |
| Discovery | HA MQTT 集成开启 Discovery；Agent 上线后自动出现 Switch / Button |
| 网络 | Agent 主机能访问 Broker；HA 能收 Discovery / state |

### 3. 部署主机（Docker）

| 要求 | 说明 |
|------|------|
| Docker Compose | 在仓库根目录 `docker compose up -d --build` |
| 到交换机 | 能 Telnet 交换机管理口 |
| Syslog 端口 | 容器需收到交换机 SHELL 日志（现网常经 fanout → `1516:514/udp`） |
| 配置 | 已从 example 生成并填好 `config/.env`、`config/devices.yaml` |

### 4. 儿童管理（可选）

| 要求 | 说明 |
|------|------|
| HA SSH | `config/.env` 配置 `HA_SSH_*`（能登录 HAOS SSH 插件并执行 `ha`） |
| 主机上有 `jq` | 安装器改 Lovelace 资源时用 |
| 首次 | 一键部署后仍须在 HA **添加集成**「H3C TV Child (MQTT)」并绑定 MQTT 开关与 `media_player` |

## 快速开始

```bash
cp config/.env.example config/.env          # 填写 H3C_* / MQTT_*；可选 HA_SSH_*
cp config/devices.yaml.example config/devices.yaml
docker compose up -d --build
```

配置只放在 **`config/`**（与 `docker-compose.yml` 同级）。  
线上 241：`/home/shuangyang/docker/smarthome/h3c-tv-agent/`（见 [`smarthome/`](../../smarthome/)）。

## 儿童管理一键安装

配置 `config/.env`：

```bash
HA_SSH_HOST=192.168.1.249
HA_SSH_USER=root
HA_SSH_PASSWORD=********
```

Agent 启动后 MQTT Discovery 出现：

| 实体 | 作用 |
|------|------|
| `button.h3c_install_child` | 安装/更新：SSH 部署 `h3c_tv_child` + Lovelace 资源 + 重启 HA |
| `sensor.h3c_child_install_status` | 安装状态（installed / ok / error…） |

说明：HA 的 MQTT 发现**不能**直接装自定义集成；按钮由 Agent 执行部署。首次部署后若尚未添加集成，到「设备与服务」添加 **H3C TV Child (MQTT)**。

运维细节：[agent/README.md](agent/README.md)（含 **日志清单 / LogQL**）
