# Sony 电视上网控制说明

## 目标

在 Home Assistant 中为 4 台 Sony 电视建立上网控制开关。

- 打开开关：允许对应电视上网
- 关闭开关：禁止对应电视上网
- 内网访问保持允许
- 实际控制通过 H3C 交换机 ACL 完成

## 推荐目录

Home Assistant 中建议使用下面的目录结构：

```text
/config/
  configuration.yaml
  packages/
    tv_internet/
      tv_internet.yaml
  scripts/
    tv_internet/
      tv_internet_control.py
  docs/
    tv_internet.md
```

职责划分：

- `packages/tv_internet/tv_internet.yaml`：放电视上网控制相关的 HA 配置，例如 `switch`、`automation`、`script`、`input_boolean` 等。
- `scripts/tv_internet/tv_internet_control.py`：放 Python 控制逻辑，负责 Telnet 登录 H3C 并修改 ACL。
- `docs/tv_internet.md`：放长期维护说明。

## 本地项目文件说明

当前本地项目中的主要文件：

```text
h3c_s5550_hass/
  packages/
    tv_internet/
      tv_internet.yaml
  scripts/
    tv_internet/
      tv_internet_control.py
  docs/
    tv_internet.md
  to_hass_webhook.py
  test_telnet.py
```

文件角色：

- `scripts/tv_internet/tv_internet_control.py`：正式控制脚本。负责 Telnet 登录交换机、查询 ACL、允许/禁止电视上网、输出 `status-json`。
- `packages/tv_internet/tv_internet.yaml`：正式 Home Assistant package。当前采用“主动轮询 JSON 状态 + template switch”的方案。
- `docs/tv_internet.md`：长期维护文档。
- `to_hass_webhook.py`：交换机侧 webhook 实验脚本。手动运行可通知 HA，但 RTM/EAA 直接调用 Python 已验证不可用，暂作为实验和备用文件。
- `test_telnet.py`：早期 Telnet 连通性测试脚本。当前正式逻辑已由 `tv_internet_control.py` 替代，不再是运行必需文件。建议保留为排错工具，或移动到 `tools/` / `archive/` 目录归档。

## configuration.yaml

需要确保 `configuration.yaml` 中已经启用 packages：

```yaml
homeassistant:
  packages: !include_dir_named packages
```

`!include_dir_named packages` 会递归加载 `packages` 目录及其子目录中的 `.yaml` 文件。

注意：

- package 文件必须使用 `.yaml` 后缀。
- package 文件名建议全局唯一，即使位于不同子目录中也不要重名。

## tv_internet.yaml 示例

文件位置：

```text
/config/packages/tv_internet/tv_internet.yaml
```

内容示例：

```yaml
# Sony 电视上网控制
# 打开开关 = 允许对应电视上网
# 关闭开关 = 禁止对应电视上网
# 控制脚本：/config/scripts/tv_internet/tv_internet_control.py

command_line:
  - sensor:
      name: Sony TV Internet Status
      unique_id: sony_tv_internet_status
      command: "python3 /config/scripts/tv_internet/tv_internet_control.py status-json"
      command_timeout: 30
      scan_interval: 60
      value_template: "{{ now().isoformat() }}"
      json_attributes:
        - master_bedroom
        - living_room
        - elder_room
        - study_room

shell_command:
  sony_tv_study_room_internet_on: "python3 /config/scripts/tv_internet/tv_internet_control.py enable study_room"
  sony_tv_study_room_internet_off: "python3 /config/scripts/tv_internet/tv_internet_control.py disable study_room"

template:
  - switch:
      - name: 书房 Sony 电视上网
        unique_id: sony_tv_study_room_internet
        state: "{{ state_attr('sensor.sony_tv_internet_status', 'study_room') == true }}"
        turn_on:
          - service: shell_command.sony_tv_study_room_internet_on
        turn_off:
          - service: shell_command.sony_tv_study_room_internet_off
```

## 电视与 ACL 映射

| key | 房间 | IP | MAC | 允许内网 rule | 禁止上网 rule |
| --- | --- | --- | --- | --- | --- |
| `master_bedroom` | 主卧室 Sony 电视 | `192.168.1.24` | `cc98-8b23-abaa` | `10` | `15` |
| `living_room` | 客厅 Sony 电视 | `192.168.1.25` | `88c9-e8d1-bcb0` | `20` | `25` |
| `elder_room` | 老人房 Sony 电视 | `192.168.1.26` | `cc98-8b36-afc7` | `30` | `35` |
| `study_room` | 书房 Sony 电视 | `192.168.1.27` | `7026-05e6-0afd` | `40` | `45` |

H3C ACL：

```text
acl advanced 3000
description Block_TV_Internet_Permit_Internal
```

控制逻辑：

- 允许上网：删除对应电视的 `deny` 规则，例如 `undo rule 45`
- 禁止上网：恢复对应电视的 `deny` 规则，例如 `rule 45 deny ip source 192.168.1.27 0`

保留内网访问的规则不动，例如：

```text
rule 40 permit ip source 192.168.1.27 0 destination 192.168.0.0 0.0.255.255
```

## 手动测试命令

在 Home Assistant 终端中测试：

```bash
python3 /config/scripts/tv_internet/tv_internet_control.py status
```

JSON 状态轮询测试：

```bash
python3 /config/scripts/tv_internet/tv_internet_control.py status-json
```

预期输出：

```json
{
  "master_bedroom": true,
  "living_room": false,
  "elder_room": false,
  "study_room": true
}
```

允许书房电视上网：

```bash
python3 /config/scripts/tv_internet/tv_internet_control.py enable study_room
```

禁止书房电视上网：

```bash
python3 /config/scripts/tv_internet/tv_internet_control.py disable study_room
```

如果当前 SSH 插件环境没有 `python3`，需要确认 Home Assistant Core 的 `command_line` 环境是否可执行 Python，或改用可用的 Python 路径。

## Home Assistant 检查与重启

修改 YAML 后先检查配置：

```bash
ha core check
```

确认无误后重启：

```bash
ha core restart
```

## 主动轮询状态方案

当前推荐方案是：

```text
HA command_line sensor 每 60 秒执行 status-json
  -> 一次 Telnet 登录读取 display acl all
  -> 输出四台电视状态 JSON
  -> template switch 根据 sensor attribute 显示真实状态
  -> shell_command 负责执行 enable/disable 控制
```

优点：

- 每分钟只登录交换机一次，不是四个开关各登录一次。
- 可以显示普通滑动开关。
- HA 重启后可以通过下一次轮询恢复真实 ACL 状态。
- 如果有人手动在交换机上改 ACL，最多 60 秒内同步到 HA。
- 不依赖 RTM/EAA 或 webhook。

状态语义：

```text
true  = 允许上网
false = 禁止上网
```

相关实体：

```text
sensor.sony_tv_internet_status
switch.sony_tv_master_bedroom_internet
switch.sony_tv_living_room_internet
switch.sony_tv_elder_room_internet
switch.sony_tv_study_room_internet
```

## 当前限制

当前主动轮询方案仍有以下限制：

- 状态最多有 60 秒延迟。
- 如果脚本执行失败，HA 前端可能仍然显示已切换。
- 暂时没有把 4 个开关注册到同一个 HA 设备下。

后续可以增强：

- 将轮询间隔按需要调整为 30 秒或 120 秒。
- 增加脚本失败通知。
- 最终改成 Home Assistant 自定义集成，并通过 `device_info` 注册为一个设备。

## H3C RTM/EAA 反馈测试记录

### 已验证成功的链路

交换机上的 Python 脚本可以直接发送 webhook 到 Home Assistant：

```text
python flash:/to_hass_webhook.py study_room off
python flash:/to_hass_webhook.py study_room on
```

已验证链路：

```text
H3C Python -> HA webhook -> HA automation -> input_boolean
```

也就是说，手动执行 `to_hass_webhook.py` 时，HA 中的 `书房 Sony 电视实际上网状态` 可以变化。

### RTM/EAA 官方语法要点

H3C RTM/EAA 可以通过 CLI policy 配置事件和动作。

CLI 事件语法：

```text
event cli { async [ skip ] | sync } mode { execute | help | tab } pattern regular-exp
```

Syslog 事件语法：

```text
event syslog priority { priority | all } msg msg occurs times period period
```

注意：

- 一个 RTM policy 只能有一个 event。
- 修改 policy 后必须重新执行 `commit`。
- RTM 自己产生的 syslog 不会再次触发 RTM，避免循环。
- Syslog event 依赖 EAA-monitored log buffer，不等于 `display logbuffer` 中所有日志都一定能触发。

### 已尝试的 CLI event 策略

曾尝试监听 ACL 子视图中的命令：

```text
rtm cli tv_study_room_on
 event cli async mode execute pattern undo rule 45
 action 0 cli python flash:/to_hass_webhook.py study_room on
 commit
```

以及：

```text
rtm cli tv_study_room_off
 event cli async mode execute pattern rule 45 deny ip source 192.168.1.27 0
 action 0 cli python flash:/to_hass_webhook.py study_room off
 commit
```

测试结果：

```text
acl advanced 3000
rule 45 deny ip source 192.168.1.27 0
undo rule 45
```

HA input 没有变化。初步判断：这台设备的 `event cli` 没有成功监听 ACL 子视图里的 `rule` / `undo rule` 命令，或者 pattern 匹配不到实际命令上下文。

### 已尝试的 Syslog event 策略

先配置 RTM syslog buffer：

```text
system-view
rtm event syslog buffer-size 1024
```

再配置 off 策略：

```text
rtm cli tv_study_room_off_syslog
 event syslog priority all msg 192.168.1.27 occurs 1 period 5
 action 0 cli python flash:/to_hass_webhook.py study_room off
 action 1 syslog priority 5 facility local0 msg RTM_study_room_off_syslog_triggered
 commit
quit
```

配置 on 策略：

```text
rtm cli tv_study_room_on_syslog
 event syslog priority all msg undo occurs 1 period 5
 action 0 cli python flash:/to_hass_webhook.py study_room on
 action 1 syslog priority 5 facility local0 msg RTM_study_room_on_syslog_triggered
 commit
quit
```

测试命令：

```text
acl advanced 3000
rule 45 deny ip source 192.168.1.27 0
undo rule 45
```

判断标准：

- 如果 HA input 变化，说明 RTM -> Python -> webhook 链路成功。
- 如果 `display logbuffer | include RTM_study_room` 中出现 `RTM_study_room_*_triggered`，说明 RTM action 至少执行了 syslog 动作。
- 如果只看到 `Command is action 1 syslog ...`，那只是配置 action 时产生的 shell 日志，不代表 RTM 被触发。

当前观察：

- 手动 Python webhook 成功。
- RTM CLI event 没有让 HA input 变化。
- RTM syslog event 仍未确认能触发 Python action。
- `display logbuffer` 能看到 `SHELL_CMD`，但不代表该日志一定进入 EAA-monitored syslog buffer。

### RTM 相关查看命令

查看 RTM 配置概览：

```text
display current-configuration | include rtm
```

查看 active policy：

```text
display rtm policy active
```

查看某个 policy 内容：

```text
system-view
rtm cli tv_study_room_off_syslog
display this
quit
```

查看 RTM syslog 触发日志：

```text
display logbuffer | include RTM_study_room
```

### 当前建议

短期建议继续使用已稳定的 HA command_line 控制方案。RTM/EAA 只作为手动改交换机 ACL 时的补充反馈实验。

如果 RTM 方案最终仍无法监听 `rule` / `undo rule`，更稳的替代方案是：

```text
HA switch 控制成功后 -> 直接同步 HA input_boolean
```

或者后续研究周期任务：

```text
RTM period -> 定时检查 ACL 状态 -> webhook 到 HA
```

## 常见排错

### command not found: python3

说明当前执行环境里没有 `python3`。需要确认：

- HA Core 环境是否有 `python3`
- `command_line` 是否能直接执行 `python3`
- 是否需要使用完整 Python 路径

### Telnet 连接失败

检查交换机：

```text
telnet server enable
local-user hass_robot class manage
 service-type telnet terminal
line vty 0 4
 authentication-mode scheme
 protocol inbound ssh telnet
```

### ACL 命令失败

正确进入 ACL 的命令是：

```text
system-view
acl advanced 3000
```

不是：

```text
acl name Block_TV_Internet_Permit_Internal
```

### 状态没有变化

检查 ACL 是否应用到了正确的 VLAN 或接口方向。脚本只负责修改 ACL 规则，如果 ACL 没有绑定到流量路径上，就不会产生控制效果。

## 维护建议

- HA 配置放在 `packages/tv_internet/tv_internet.yaml`
- Python 控制脚本放在 `scripts/tv_internet/tv_internet_control.py`
- 详细说明放在 `docs/tv_internet.md`
- 交换机密码不要提交到 GitHub，部署时通过 `H3C_SWITCH_PASSWORD` 环境变量提供
