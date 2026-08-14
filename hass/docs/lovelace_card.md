# H3C 电视儿童管理卡片（MQTT）

`h3c_tv_child` 自带 `custom:h3c-tv-child-card`。每张卡片管理一台电视，通过设备注册表解析上网开关、儿童策略与统计实体。

## 前提

- 已用 Agent「安装/更新儿童管理」或手动部署 `h3c_tv_child`
- `h3c-tv-agent` MQTT 开关在线
- 集成配置中已绑定对应 `media_player`（否则时长统计不可用）
- Lovelace 资源已存在（安装器会写入；也可手动添加）

## 资源

- URL：`/h3c_tv_child/lovelace/h3c-tv-child-card.js?v=0.1.1`
- 类型：JavaScript 模块

若下拉无设备：确认资源指向 **h3c_tv_child**（不是已删除的 `h3c_tv_control`），并强制刷新浏览器。

## YAML 示例

```yaml
type: custom:h3c-tv-child-card
device_id: 你的电视设备ID
```

## 卡片能力

与旧 `h3c_tv_control` 卡片一致：电视电源、上网、儿童控制、本次/今日/冷却、时长与时段设置、今日初始化。
