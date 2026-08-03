"""Shared models and TV inventory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TVState = Literal["ON", "OFF"]
WantState = Literal["ON", "OFF"]


@dataclass(frozen=True)
class TVConfig:
    key: str
    name: str
    ip: str
    mac: str
    permit_rule: int
    deny_rule: int


TVS: dict[str, TVConfig] = {
    "master_bedroom": TVConfig(
        key="master_bedroom",
        name="主卧电视上网",
        ip="192.168.1.24",
        mac="cc98-8b23-abaa",
        permit_rule=10,
        deny_rule=15,
    ),
    "living_room": TVConfig(
        key="living_room",
        name="客厅电视上网",
        ip="192.168.1.25",
        mac="88c9-e8d1-bcb0",
        permit_rule=20,
        deny_rule=25,
    ),
    "elder_room": TVConfig(
        key="elder_room",
        name="老人房电视上网",
        ip="192.168.1.26",
        mac="cc98-8b36-afc7",
        permit_rule=30,
        deny_rule=35,
    ),
    "study_room": TVConfig(
        key="study_room",
        name="书房电视上网",
        ip="192.168.1.27",
        mac="7026-05e6-0afd",
        permit_rule=40,
        deny_rule=45,
    ),
}


@dataclass(frozen=True)
class Command:
    """MQTT-driven ACL change request."""

    tv: str
    want: WantState
    source: str = "mqtt"


def parse_want(payload: str | bytes) -> WantState | None:
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8", errors="ignore")
    text = payload.strip()
    upper = text.upper()
    if upper in {"ON", "OFF"}:
        return upper  # type: ignore[return-value]
    if text.startswith("{"):
        import json

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        state = str(data.get("state", "")).upper()
        if state in {"ON", "OFF"}:
            return state  # type: ignore[return-value]
    return None
