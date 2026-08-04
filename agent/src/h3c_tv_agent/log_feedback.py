"""Derive MQTT switch feedback from structured logs (not from polling)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from .models import ACCESS_KEYS, TVState, access_devices

_std = logging.getLogger("h3c_tv_agent.log_feedback")

FeedbackHook = Callable[[dict[str, Any]], None]
_hooks: list[FeedbackHook] = []


def register_log_feedback(hook: FeedbackHook) -> None:
    _hooks.append(hook)


def clear_log_feedback() -> None:
    _hooks.clear()


def log_feedback_processor(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """structlog processor: fan-out business fields to feedback hooks."""
    for hook in list(_hooks):
        try:
            hook(event_dict)
        except Exception as exc:  # never break logging
            _std.warning("feedback hook error: %s", exc)
    return event_dict


def make_mqtt_feedback_publisher(publish_state, publish_status) -> FeedbackHook:
    """
    Recognize slog fields and push HA switch state.

    Accepted shapes:
    - tv + state in {ON,OFF} + result=ok + action allow|deny → single switch
    - states={tv: ON/OFF, ...} + result=ok → bootstrap / rare sync
    - action=poll|login + result=fail → availability offline
    """

    def _hook(event: dict[str, Any]) -> None:
        result = event.get("result")
        action = event.get("action")

        if result == "fail" and action in {"poll", "login"}:
            publish_status("offline")
            return

        if result == "ok" and action == "login":
            publish_status("online")

        states = event.get("states")
        if result == "ok" and isinstance(states, dict):
            for tv, state in states.items():
                if tv not in ACCESS_KEYS or state not in {"ON", "OFF"}:
                    continue
                _publish_one(publish_state, tv, state, event, source="log:states")
            return

        tv = event.get("tv")
        state = event.get("state")
        if (
            result == "ok"
            and tv in ACCESS_KEYS
            and state in {"ON", "OFF"}
            and action in {"allow", "deny"}
        ):
            _publish_one(publish_state, tv, state, event, source="log:acl")

    return _hook


def _publish_one(
    publish_state, tv: str, state: TVState, event: dict[str, Any], *, source: str
) -> None:
    tv_cfg = access_devices()[tv]
    publish_state(
        tv,
        state,  # type: ignore[arg-type]
        attrs={
            "name": tv_cfg.name,
            "ip": tv_cfg.ip,
            "deny_rule": tv_cfg.deny_rule,
            "feedback_source": source,
            "action": event.get("action"),
            "duration_ms": event.get("duration_ms"),
        },
    )
