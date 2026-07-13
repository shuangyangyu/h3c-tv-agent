# H3C S5550 Home Assistant TV Control

这个项目用于在 Home Assistant 中控制多台 Sony 电视是否允许访问互联网。

核心思路是：Home Assistant 显示电视上网开关，Python 脚本通过 Telnet 登录 H3C S5550 交换机，修改指定 ACL 规则，从而允许或禁止对应电视上网。

## 功能

- 在 Home Assistant 中显示 4 台电视的上网开关。
- 开启开关时，删除对应电视的 deny ACL 规则，允许上网。
- 关闭开关时，恢复对应电视的 deny ACL 规则，禁止上网。
- 通过定时轮询交换机 ACL，刷新 Home Assistant 中的真实状态。

## 主要文件

- `packages/tv_internet/tv_internet.yaml`：Home Assistant package 配置。
- `scripts/tv_internet/tv_internet_control.py`：H3C 交换机 ACL 控制脚本。
- `docs/tv_internet.md`：详细部署、调试和维护说明。
- `to_hass_webhook.py`：早期 webhook 实验脚本，当前方案不依赖它。

## 将来发展

后续可以把 H3C 交换机上的路由策略也接入 Home Assistant，让 HA 不只控制电视上网，还能控制指定设备是否走“科学上网路由器”。

计划方向包括：

- 在 Home Assistant 中为指定设备增加“科学上网”开关。
- 开启后，通过 H3C 交换机的 ACL、策略路由或静态路由，把该设备的外网流量引到科学上网路由器。
- 关闭后，恢复为普通家庭网关出口。
- 在 HA 中显示当前设备使用的出口，例如普通网关或科学上网路由器。
- 为关键状态增加提醒，例如科学上网路由器不可达、策略路由未生效、默认出口异常等。
- 将电视上网控制、ACL 状态、设备出口状态统一放到 Home Assistant 仪表盘中，作为家庭网络管理面板。

这类功能会影响设备的实际上网路径，后续实现时应先从只读状态检测开始，确认 H3C 路由策略稳定后，再逐步加入开关控制。

## 注意

交换机密码不要写入代码或提交到 GitHub。运行控制脚本前，需要通过环境变量提供密码：

```bash
export H3C_SWITCH_PASSWORD="你的交换机密码"
```
