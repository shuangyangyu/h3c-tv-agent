# 运行时配置（与 `docker-compose.yml` 并列）

用户只改这里；源码在 `agent/` / `hass/`。

| 文件 | 作用 |
|------|------|
| **`.env`** | 连接与密钥：交换机 Telnet、MQTT、ACL 规则号、可选 `HA_SSH_*` |
| **`devices.yaml`** | 设备清单：`devices` + `access` / `policy_route` |

首次：

```bash
cp config/.env.example config/.env
cp config/devices.yaml.example config/devices.yaml
# 编辑后：
docker compose up -d --build
```

`.env` 含密码，不进 git。字段说明见仓库根 / `agent/README.md`。
