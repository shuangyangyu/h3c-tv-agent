"""Constants for H3C TV Child (MQTT) integration."""

from typing import TypedDict


class TVConfig(TypedDict):
    """Configuration for one controlled television."""

    name: str
    ip: str
    deny_rule: int


DOMAIN = "h3c_tv_child"
DEFAULT_SCAN_INTERVAL = 30

# Options / config keys: media_player + MQTT internet switch per TV
TV_MEDIA_PLAYER_OPTIONS: dict[str, str] = {
    "master_bedroom": "master_bedroom_media_player",
    "living_room": "living_room_media_player",
    "elder_room": "elder_room_media_player",
    "study_room": "study_room_media_player",
}

TV_INTERNET_SWITCH_OPTIONS: dict[str, str] = {
    "master_bedroom": "master_bedroom_internet_switch",
    "living_room": "living_room_internet_switch",
    "elder_room": "elder_room_internet_switch",
    "study_room": "study_room_internet_switch",
}

# Defaults match h3c-tv-agent MQTT discovery entity_ids
# (slug = IP digits when mac empty: 192.168.1.24 → 192168124)
DEFAULT_INTERNET_SWITCHES: dict[str, str] = {
    "master_bedroom": "switch.h3c_tv_192168124",
    "living_room": "switch.h3c_tv_192168125",
    "elder_room": "switch.h3c_tv_192168126",
    "study_room": "switch.h3c_tv_192168127",
}

ATTR_INTERNET_ENABLED = "internet_enabled"
ATTR_SESSION_REMAINING = "session_remaining_minutes"
ATTR_DAILY_USED = "daily_used_minutes"
ATTR_CHILD_ENABLED = "child_control_enabled"
ATTR_DENY_REASON = "deny_reason"

DEFAULT_SESSION_MINUTES = 30
DEFAULT_DAILY_MINUTES = 90
DEFAULT_COOLDOWN_MINUTES = 60
DEFAULT_WINDOW_PRESET = "daytime"
WINDOW_PRESETS: dict[str, tuple[str, str]] = {
    "all_day": ("00:00:00", "00:00:00"),
    "daytime": ("08:00:00", "20:00:00"),
    "nighttime": ("20:00:00", "08:00:00"),
}
DEFAULT_WINDOW_START, DEFAULT_WINDOW_END = WINDOW_PRESETS[DEFAULT_WINDOW_PRESET]

MIN_SESSION_MINUTES = 5
MAX_SESSION_MINUTES = 180
MIN_DAILY_MINUTES = 10
MAX_DAILY_MINUTES = 480
MIN_COOLDOWN_MINUTES = 5
MAX_COOLDOWN_MINUTES = 180

TVS: dict[str, TVConfig] = {
    "master_bedroom": {
        "name": "主卧电视上网",
        "ip": "192.168.1.24",
        "deny_rule": 15,
    },
    "living_room": {
        "name": "客厅电视上网",
        "ip": "192.168.1.25",
        "deny_rule": 25,
    },
    "elder_room": {
        "name": "老人房电视上网",
        "ip": "192.168.1.26",
        "deny_rule": 35,
    },
    "study_room": {
        "name": "书房电视上网",
        "ip": "192.168.1.27",
        "deny_rule": 45,
    },
}
