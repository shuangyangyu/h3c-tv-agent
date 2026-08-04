# H3C PBR → mihomo：交换机配置逻辑

更新：2026-08-04  
设备：H3C S5550（`192.168.1.254`）· 旁路网关 mihomo（`192.168.1.230`）  
配套：[`pbr-vpn-exceptions.md`](./pbr-vpn-exceptions.md)（VPN/回程场景）· [`../agent/README.md`](../agent/README.md)（Agent）

---

## 1. 目标

| 流量 | 行为 |
|------|------|
| 指定源 IP → **私网目的**（家 / 办公室 IPsec / WG） | **不**改下一跳 → 默认路由 `1.254` |
| 同一源 IP → **其余目的**（公网） | next-hop **`1.230`（mihomo）** |
| 未加入策略的设备 | 始终走 `1.254`，与 PBR 无关 |

谁改什么：

| 角色 | 职责 |
|------|------|
| **手工 / 首次上线** | 建 PBR 名、`permit node`、接口 `ip policy-based-route`、syslog |
| **h3c-tv-agent** | 改 ACL **3001/3002** 成员；幂等补齐 **deny node 5** |
| **mihomo** | 收到后再按 rules 分流（不能代替交换机侧例外） |

---

## 2. 核心原理（必读）

### 2.1 PBR 节点顺序

```text
报文进入 Vlan-interface1（已挂 policy-based-route mihomo）
        │
        ▼
┌─────────────────────────────┐
│ node 5  deny                │  数字越小越先匹配
│   if-match acl 3002         │  ACL 中有 permit 命中 → 停止 PBR
│   （无 apply）              │  → 走普通路由表
└─────────────┬───────────────┘
              │ 未命中
              ▼
┌─────────────────────────────┐
│ node 10 permit              │
│   if-match acl 3001         │  源 IP permit 命中
│   apply next-hop 1.230      │  → 甩到 mihomo
└─────────────────────────────┘
```

### 2.2 `if-match acl` 只认 permit

高级 ACL 里的 **`deny` 规则不能当作 PBR 例外**。  
曾误用「同 ACL：先 deny 私网、再 permit 源」→ 私网仍被 `permit node` 命中 → Hass 连不上本机交换机 Telnet（`.254:23`），旧集成 `h3c_tv_control` 卡片全部 unavailable。

正确模型：

- **要绕开 mihomo** → 用另一张 ACL 的 **`permit`（源+目的）** + PBR **`deny node`**
- **要进 mihomo** → ACL **`permit`（仅源）** + PBR **`permit node` + next-hop**

### 2.3 ACL 编号分工

| ACL | 用途 | 规则形态 | 被谁 match |
|-----|------|----------|------------|
| **3000** | 电视上网通断（packet-filter） | `deny ip source <TV> 0` = 断网 | 与 PBR 无关 |
| **3001** | 进科学 | `permit ip source <IP> 0` | `permit node 10` |
| **3002** | 私网旁路 | `permit ip source <IP> 0 destination <网段> <反掩码>` | `deny node 5` |

---

## 3. 现网标准配置（CLI）

以下为**稳态**应具备的逻辑；Agent 会维护 3001/3002 成员与 deny node，**permit node / 接口挂载**需事先存在。

### 3.1 策略主体（手工一次）

```text
system-view

# 旁路 ACL（可先建空壳；成员由 Agent 写）
acl advanced 3002
 description PBR-bypass-private-dest
quit

# 进 mihomo ACL
acl advanced 3001
 description PBR-to-mihomo
quit

# PBR：先 deny 私网，再 permit 科学
policy-based-route mihomo deny node 5
 if-match acl 3002
quit

policy-based-route mihomo permit node 10
 if-match acl 3001
 apply next-hop 192.168.1.230 direct
quit

# 挂到 LAN 三层口（现网）
interface Vlan-interface1
 ip policy-based-route mihomo
quit
```

核对：

```text
display ip policy-based-route
# 期望：
#   node 5 deny:    if-match acl 3002
#   node 10 permit: if-match acl 3001 / next-hop 192.168.1.230

display acl 3001
display acl 3002
```

### 3.2 Agent 写入的规则形态（示例）

`ROUTE_RULE_BASE=100`、`STEP=10`，两台策略设备：

| key | IP | 3002（旁路） | 3001（科学） |
|-----|-----|--------------|--------------|
| iphone_shuangyang | `.36` | rule **98/99** permit 源+`192.168/16`、源+`10/8` | rule **100** permit 源 |
| hass | `.249` | rule **108/109** 同上 | rule **110** permit 源 |

通断电视仍用 ACL **3000**（deny 15/25/35/45…），与上表错开。

反掩码（H3C wildcard）：

| CIDR | network | wildcard |
|------|---------|----------|
| `192.168.0.0/16` | `192.168.0.0` | `0.0.255.255` |
| `10.0.0.0/8` | `10.0.0.0` | `0.255.255.255` |

完整命令示例（Hass ON）：

```text
acl advanced 3002
 rule 108 permit ip source 192.168.1.249 0 destination 192.168.0.0 0.0.255.255
 rule 109 permit ip source 192.168.1.249 0 destination 10.0.0.0 0.255.255.255
quit
acl advanced 3001
 rule 110 permit ip source 192.168.1.249 0
quit
```

OFF：按源 IP `undo` 掉 3001/3002 上该源的全部相关 rule。

### 3.3 Syslog（状态反馈，通断/策略共用）

```text
info-center loghost <Agent局域网IP> facility local0
info-center source SHELL channel loghost log level informational
```

Agent 容器收 UDP **514**，解析 `SHELL_CMD` 后推 MQTT。

---

## 4. Agent 与交换机的边界

| 项 | Agent 做 | Agent 不做 |
|----|----------|------------|
| ACL 3000 通断 | ✅ | |
| ACL 3001/3002 成员 | ✅ | |
| `deny node 5` + if-match 3002 | ✅ 幂等补齐 | |
| `permit node 10` + next-hop | | ❌ 需已存在 |
| 接口 `ip policy-based-route` | | ❌ 需已存在 |
| `save` | 部署时可手工 / 脚本 | 日常 MQTT 开关默认不 save |

环境变量（见 `agent/.env.example`）：

```text
ROUTE_ACL_ID=3001
ROUTE_BYPASS_ACL_ID=3002
ROUTE_BYPASS_CIDRS=192.168.0.0/16,10.0.0.0/8
PBR_NAME=mihomo
PBR_DENY_NODE=5
ROUTE_RULE_BASE=100
ROUTE_RULE_STEP=10
```

启动时：若设备已 ON 但 3001/3002 规则不齐 → `normalize` 重写。

---

## 5. 报文路径对照

### 5.1 Hass 开 PBR，访问 GitHub

```text
Hass.249 → 公网
  3002 不命中 → node 10 + 3001 命中 → next-hop .230 → mihomo → VLAN20 出网
```

### 5.2 Hass 开 PBR，回包给 WG / 办公室 / 本机交换机

```text
Hass.249 → 10.0.0.x / 192.168.5.x / 192.168.1.254
  3002 命中 → deny node → 普通路由 → 1.254（或直连）
```

否则会出现：VPN/局域网访问 Hass 掉线，或 Hass 连不上 `.254` Telnet。

### 5.3 与 mihomo `DIRECT` 的区别

| 层级 | 作用 |
|------|------|
| 交换机 PBR + 3002 | 报文**根本不进** `.230` |
| mihomo `GEOIP,LAN` / 私网 DIRECT | 已进容器，只是不走机场节点 |

服务端（Hass）必须在交换机层做 3002，不能只靠 mihomo。

---

## 6. 故障速查

| 现象 | 常见原因 | 处理 |
|------|----------|------|
| Hass 开 PBR 后旧电视卡片「设备不可用」 | 连不上 `.254:23`（私网被 PBR） | 确认 node5+3002；Agent 已部署双 ACL |
| VPN 能进 Hass、交互后掉线 | 回程被甩到 `.230` | 检查 3002 是否含该源 + `192.168/16`、`10/8` |
| 开了 PBR 仍不科学 | 3001 无源 permit / node10 未挂接口 | `display acl 3001`、`display ip policy-based-route` |
| 同 ACL deny 私网无效 | H3C if-match 只认 permit | **不要**再用同 ACL deny 方案 |

验证命令（Hass PBR ON 时在 HA 侧）：

```text
# 应通
nc -zv 192.168.1.254 23
ping 192.168.1.241

# 应能出网（经 mihomo）
curl -o /dev/null -w "%{http_code}\n" https://www.google.com/generate_204
```

---

## 7. 相关文件

| 路径 | 内容 |
|------|------|
| 本文 | 交换机 PBR/ACL 逻辑与 CLI |
| [`pbr-vpn-exceptions.md`](./pbr-vpn-exceptions.md) | 双 VPN、Hass 场景、不对称说明 |
| [`switch_pbr.md`](./switch_pbr.md) | 与 Agent 字段对照 |
| [`../agent/`](../agent/) | 自动写 ACL 的实现 |
