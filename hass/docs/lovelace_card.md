# H3C 电视儿童管理卡片（MQTT）

`h3c_tv_child` 自带 `custom:h3c-tv-child-card`。每张卡片管理一台电视，通过设备注册表解析上网开关、儿童策略与统计实体。

## 前提

- 已安装 `h3c_tv_child`，且 `h3c-tv-agent` MQTT 开关在线
- 已在集成配置中绑定对应 `media_player`（否则时长类显示不可用）

## 资源

- URL：`/h3c_tv_child/lovelace/h3c-tv-child-card.js?v=0.1.1`
- 类型：JavaScript 模块

## YAML 示例

```yaml
type: custom:h3c-tv-child-card
device_id: 你的电视设备ID
```

## 卡片能力

与旧 `h3c_tv_control` 卡片一致：电视电源、上网、儿童控制、本次/今日/冷却、时长与时段设置、今日初始化。
