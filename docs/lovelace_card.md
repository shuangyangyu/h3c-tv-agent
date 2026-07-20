# H3C 单电视儿童管理卡片

`h3c_tv_control` 自带 `custom:h3c-tv-child-card` Lovelace 卡片。每张卡片管理
一台电视，并通过 Home Assistant 设备注册表自动找到对应的上网开关、儿童策略、
时长设置和统计实体。

## 前提

- Home Assistant 2026.3.1 或更高版本
- 已安装并配置 `h3c_tv_control`
- 已在集成“配置”中为电视绑定对应的 `media_player` 实体

未绑定 `media_player` 时仍可控制 ACL 上网开关，但卡片中的使用时长统计会显示为
不可用。

## 添加前端资源

安装或更新集成并重启 Home Assistant 后：

1. 打开“设置 → 仪表盘”。
2. 右上角菜单选择“资源”。
3. 添加资源：
   - URL：`/h3c_tv_control/lovelace/h3c-tv-child-card.js?v=0.2.0`
   - 类型：`JavaScript 模块`
4. 强制刷新浏览器页面。

只需要添加一次资源。以后更新卡片时，可修改 URL 末尾的版本参数以清除浏览器缓存。

## 添加卡片

在仪表盘编辑模式中选择“H3C 电视儿童管理”，然后选择一台由
`h3c_tv_control` 创建的电视设备。

也可以使用 YAML：

```yaml
type: custom:h3c-tv-child-card
device_id: 你的电视设备ID
```

设备 ID 可以从“设置 → 设备与服务 → 设备 → 对应电视”的页面 URL 中取得。推荐使用
可视化编辑器，避免手动查找。

## 卡片功能

- 查看电视活动状态和网络状态
- 开关电视上网
- 启用或关闭儿童控制
- 查看本次剩余、今日已用和冷却剩余时间
- 调整单次、每日和冷却分钟数
- 选择全天、白天或晚上允许时段
- 查看策略自动断网原因和通信错误
- 二次确认后执行“今日初始化”

所有操作都调用 Home Assistant 标准实体服务，不会绕过集成中的儿童策略判断。

## 故障排查

### 卡片显示“Custom element doesn't exist”

- 确认资源 URL 和类型正确。
- 确认 Home Assistant 已重启。
- 使用浏览器强制刷新，或将资源 URL 的版本参数改为新的值。

### 卡片找不到实体

- 确认选择的是 `h3c_tv_control` 创建的电视设备，而不是 Sony
  `media_player` 设备。
- 在“设置 → 设备与服务 → H3C TV Control”中确认实体没有被禁用。

### 时长显示不可用

进入集成“配置”，为该电视绑定真实的 `media_player` 实体，然后重新加载集成。

## 原生卡片回退

如果不希望加载自定义 JavaScript，可以继续使用
[`dashboard_example.yaml`](dashboard_example.yaml) 中的原生 `entities` 卡片方案。
