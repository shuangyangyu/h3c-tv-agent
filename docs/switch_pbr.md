# 交换机 PBR / ACL（Agent 对照）

更新：2026-08-04

**完整交换机配置逻辑、CLI、报文路径、故障速查：**  
→ [`../../../network/h3c-pbr-mihomo.md`](../../../network/h3c-pbr-mihomo.md)

场景与双 VPN：[`../../../network/pbr-vpn-exceptions.md`](../../../network/pbr-vpn-exceptions.md)

---

## 与本仓库 Agent 的映射

| 交换机 | Agent |
|--------|--------|
| ACL **3000** 通断 | `access` + `h3c/tv` |
| ACL **3001** 进 mihomo | `policy_route` ON → 源 `permit` |
| ACL **3002** 私网旁路 | 同上 → 源+目的 `permit` |
| PBR `deny node 5` | 启动/ON 时幂等补齐 |
| PBR `permit node 10` + 接口挂载 | **不改**（需现网已有） |

规则号：`ROUTE_RULE_BASE/STEP`（默认 100/10）；旁路规则占用 `permit_rule - n … permit_rule - 1`。

实现：`agent/src/h3c_tv_agent/route_acl.py`、`telnet_switch.py`。
