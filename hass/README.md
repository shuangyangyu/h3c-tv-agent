# H3C TV Child（随 Agent 分发）

儿童策略集成与 Lovelace 卡片已并入 **`h3c-tv-agent`**：

| 路径 | 说明 |
|------|------|
| [`hass/h3c_tv_child/`](./h3c_tv_child/) | HA `custom_components` 包（含 `www` 卡片） |
| [`docs/`](./docs/) | 需求 / 卡片说明 |
| Agent MQTT 按钮 | `button.h3c_install_child` → SSH 自动部署到 HA |

日常安装/更新：在 HA 打开 **H3C Network Agent** 设备，按「安装/更新儿童管理」。

详见仓库根目录 [README.md](../README.md) 与 [docs/rewrite_development.md](../docs/rewrite_development.md)。
