# h3c-tv-agent

Docker 服务：Telnet 改 H3C S5550 ACL（电视通断 + 策略路由）+ MQTT；内嵌 syslog UDP；**并带 HA 儿童管理插件包，可通过 MQTT 按钮一键安装/更新**。

> 旧 Telnet 集成 `h3c_tv_control` 已放弃并冻结：  
> https://github.com/shuangyangyu/h3c_s5550_hass → **新地址** https://github.com/shuangyangyu/h3c-tv-agent

## 目录

| 路径 | 说明 |
|------|------|
| `agent/` | Python 服务、`.env.example`、`devices.yaml` |
| `hass/h3c_tv_child/` | HA 儿童策略集成 + Lovelace 卡片（随镜像打包） |
| `docker-compose.yml` | 构建上下文为仓库根目录 |
| `docs/rewrite_development.md` | 开发说明 |
| [`../../lan/h3c-s5550/h3c-pbr-mihomo.md`](../../lan/h3c-s5550/h3c-pbr-mihomo.md) | PBR / ACL |

## 快速开始

```bash
cp agent/.env.example agent/.env   # 填写 H3C_* / MQTT_*；可选 HA_SSH_*
cp agent/devices.yaml.example agent/devices.yaml
docker compose up -d --build
```

## 儿童管理一键安装

配置 `agent/.env`：

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

运维细节：[agent/README.md](agent/README.md)
