# H3C TV Child（随 Agent 分发）

HA 自定义集成：儿童上网策略 + Lovelace 卡片；**通断走 Agent 的 MQTT Switch**，本集成不 Telnet。

| 路径 | 说明 |
|------|------|
| [`h3c_tv_child/`](./h3c_tv_child/) | 打进 Agent 镜像；一键安装目标 |
| [`docs/requirements.md`](./docs/requirements.md) | 需求（对齐旧插件） |
| [`docs/lovelace_card.md`](./docs/lovelace_card.md) | 卡片用法 |
| [`tests/`](./tests/) | `child_policy` 单测 |

## 安装方式（推荐）

1. Agent `.env` 配置 `HA_SSH_*`  
2. HA 中按 **H3C Network Agent → 安装/更新儿童管理**  
3. 添加集成 **H3C TV Child (MQTT)**，绑定四台 `switch.h3c_tv_19216812x`（或你环境中的 Discovery 实体）与 `media_player`  
4. 仪表盘加 `custom:h3c-tv-child-card`

手动复制仅作调试：把 `h3c_tv_child/` 放到 HA `/config/custom_components/` 后重启。

根说明：[../README.md](../README.md)
