"""PBR 分路：ACL 3001 源 permit + ACL 3002 私网目的 permit（配合 deny node）。

H3C ``if-match acl`` 只认 permit；同 ACL 里写 deny 无法作例外。
正确结构：

- ``policy-based-route mihomo deny node 5`` + ``if-match acl 3002``
- ``policy-based-route mihomo permit node 10`` + ``if-match acl 3001`` + next-hop
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass

_RE_SRC_RULE = re.compile(
    r"(?i)rule\s+(\d+)\s+(permit|deny)\s+ip\s+source\s+(\d+\.\d+\.\d+\.\d+)\s+0\b"
)
# 3001 用的「裸」permit（无 destination）
_RE_BARE_PERMIT = re.compile(
    r"(?i)rule\s+(\d+)\s+permit\s+ip\s+source\s+(\d+\.\d+\.\d+\.\d+)\s+0(?!\s+destination)"
)

DEFAULT_ROUTE_BYPASS_CIDRS = ("192.168.0.0/16", "10.0.0.0/8")


@dataclass(frozen=True)
class BypassNet:
    cidr: str
    network: str
    wildcard: str


def parse_bypass_cidrs(raw: str | None) -> list[str]:
    """逗号分隔 CIDR；空则用默认（家网/办公室 192.168/16 + WG 10/8）。"""
    if raw is None or not str(raw).strip():
        return list(DEFAULT_ROUTE_BYPASS_CIDRS)
    out: list[str] = []
    for part in str(raw).split(","):
        item = part.strip()
        if not item:
            continue
        net = ipaddress.ip_network(item, strict=False)
        if not isinstance(net, ipaddress.IPv4Network):
            raise ValueError(f"only IPv4 bypass CIDR supported: {item}")
        out.append(str(net))
    if not out:
        return list(DEFAULT_ROUTE_BYPASS_CIDRS)
    return out


def cidr_to_h3c(cidr: str) -> BypassNet:
    net = ipaddress.ip_network(cidr, strict=False)
    if not isinstance(net, ipaddress.IPv4Network):
        raise ValueError(f"only IPv4: {cidr}")
    return BypassNet(
        cidr=str(net),
        network=str(net.network_address),
        wildcard=str(ipaddress.IPv4Address(int(net.hostmask))),
    )


def bypass_rule_ids(permit_rule: int, n_bypass: int) -> list[int]:
    """与 permit 号对齐的 bypass 规则号（如 100 + 2 → 98,99）。"""
    if n_bypass < 0:
        raise ValueError("n_bypass must be >= 0")
    if n_bypass == 0:
        return []
    first = permit_rule - n_bypass
    if first < 1:
        raise ValueError(
            f"permit_rule {permit_rule} too small for {n_bypass} bypass rules"
        )
    return list(range(first, permit_rule))


def expected_bypass_rule_ids(permit_rule: int, bypass_cidrs: list[str]) -> set[int]:
    return set(bypass_rule_ids(permit_rule, len(bypass_cidrs)))


def build_route_permit_command(ip: str, permit_rule: int) -> str:
    """ACL 3001：整源 permit → PBR permit node → mihomo。"""
    return f"rule {permit_rule} permit ip source {ip} 0"


def build_bypass_permit_commands(
    ip: str, permit_rule: int, bypass_cidrs: list[str]
) -> list[str]:
    """ACL 3002：源+私网目的 permit → PBR deny node → 普通路由。"""
    cmds: list[str] = []
    for rid, cidr in zip(
        bypass_rule_ids(permit_rule, len(bypass_cidrs)), bypass_cidrs, strict=True
    ):
        bn = cidr_to_h3c(cidr)
        cmds.append(
            f"rule {rid} permit ip source {ip} 0 destination {bn.network} {bn.wildcard}"
        )
    return cmds


def find_source_rule_ids(acl_text: str, ip: str) -> set[int]:
    """ACL 文本中该源 IP 的全部 rule 号（permit/deny）。"""
    return {
        int(m.group(1))
        for m in _RE_SRC_RULE.finditer(acl_text)
        if m.group(3) == ip
    }


def has_route_permit(acl_text: str, ip: str) -> bool:
    """3001 上是否有无 destination 的源 permit。"""
    return any(m.group(2) == ip for m in _RE_BARE_PERMIT.finditer(acl_text))


def pbr_deny_node_configured(pbr_text: str, *, node: int, acl_id: int) -> bool:
    """粗检 display ip policy-based-route 是否已有 deny node + if-match acl。"""
    # 只看该 deny node 段，避免跨到下一个 node
    pattern = re.compile(
        rf"(?is)node\s+{node}\s+deny:(.*?)(?=\n\s*node\s+\d+|\Z)"
    )
    m = pattern.search(pbr_text)
    if not m:
        return False
    return bool(re.search(rf"(?i)if-match\s+acl\s+{acl_id}\b", m.group(1)))
