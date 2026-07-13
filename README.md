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

## 注意

交换机密码不要写入代码或提交到 GitHub。运行控制脚本前，需要通过环境变量提供密码：

```bash
export H3C_SWITCH_PASSWORD="你的交换机密码"
```
