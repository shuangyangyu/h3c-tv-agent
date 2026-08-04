"""Unit tests for PBR bypass ACL helpers."""

from h3c_tv_agent.route_acl import (
    build_bypass_permit_commands,
    build_route_permit_command,
    bypass_rule_ids,
    cidr_to_h3c,
    expected_bypass_rule_ids,
    find_source_rule_ids,
    has_route_permit,
    parse_bypass_cidrs,
    pbr_deny_node_configured,
)


def test_default_bypass_cidrs():
    assert parse_bypass_cidrs("") == ["192.168.0.0/16", "10.0.0.0/8"]
    assert parse_bypass_cidrs(None) == ["192.168.0.0/16", "10.0.0.0/8"]


def test_parse_and_normalize_cidr():
    assert parse_bypass_cidrs("192.168.5.0/24, 10.0.0.0/24") == [
        "192.168.5.0/24",
        "10.0.0.0/24",
    ]
    assert parse_bypass_cidrs("192.168.1.24/16") == ["192.168.0.0/16"]


def test_cidr_to_h3c_wildcard():
    bn = cidr_to_h3c("192.168.0.0/16")
    assert bn.network == "192.168.0.0"
    assert bn.wildcard == "0.0.255.255"
    bn10 = cidr_to_h3c("10.0.0.0/8")
    assert bn10.network == "10.0.0.0"
    assert bn10.wildcard == "0.255.255.255"


def test_build_dual_acl_commands():
    assert build_route_permit_command("192.168.1.249", 110) == (
        "rule 110 permit ip source 192.168.1.249 0"
    )
    assert build_bypass_permit_commands(
        "192.168.1.249", 110, ["192.168.0.0/16", "10.0.0.0/8"]
    ) == [
        "rule 108 permit ip source 192.168.1.249 0 destination 192.168.0.0 0.0.255.255",
        "rule 109 permit ip source 192.168.1.249 0 destination 10.0.0.0 0.255.255.255",
    ]
    assert bypass_rule_ids(100, 2) == [98, 99]
    assert expected_bypass_rule_ids(100, ["192.168.0.0/16", "10.0.0.0/8"]) == {98, 99}


def test_has_route_permit_ignores_destination():
    acl = """
 rule 98 permit ip source 192.168.1.249 0 destination 192.168.0.0 0.0.255.255
 rule 100 permit ip source 192.168.1.36 0
 rule 110 permit ip source 192.168.1.249 0
"""
    assert has_route_permit(acl, "192.168.1.249")
    assert has_route_permit(acl, "192.168.1.36")
    assert not has_route_permit(acl, "192.168.1.24")
    assert find_source_rule_ids(acl, "192.168.1.249") == {98, 110}


def test_pbr_deny_node_configured():
    text = """
Policy name: mihomo
  node 5 deny:
    if-match acl 3002
  node 10 permit:
    if-match acl 3001
    apply next-hop 192.168.1.230 direct
"""
    assert pbr_deny_node_configured(text, node=5, acl_id=3002)
    assert not pbr_deny_node_configured(text, node=5, acl_id=3001)
    assert not pbr_deny_node_configured("node 10 permit:", node=5, acl_id=3002)
