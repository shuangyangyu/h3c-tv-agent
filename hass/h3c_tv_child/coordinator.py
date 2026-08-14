"""Coordinator: child policy + MQTT internet switch proxy."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.media_player.const import MediaPlayerState
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .child_policy import ChildPolicyManager, SESSION_LIMIT_REASON
from .const import (
    DEFAULT_INTERNET_SWITCHES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    TV_INTERNET_SWITCH_OPTIONS,
    TV_MEDIA_PLAYER_OPTIONS,
    TVS,
    WINDOW_PRESETS,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 2
ACTIVE_TV_STATES = {
    MediaPlayerState.ON,
    MediaPlayerState.IDLE,
    MediaPlayerState.PLAYING,
    MediaPlayerState.PAUSED,
    MediaPlayerState.BUFFERING,
}
INACTIVE_TV_STATES = {MediaPlayerState.OFF}
TV_UNAVAILABLE_GRACE = timedelta(minutes=2)


def storage_key(entry_id: str) -> str:
    """Return the per-config-entry storage key."""
    return f"{DOMAIN}.{entry_id}.child_policy"


class H3CTVChildCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Drive child policy against MQTT-discovered internet switches."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        self.entry = entry
        self.child_policy = ChildPolicyManager()
        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORAGE_VERSION,
            storage_key(entry.entry_id),
        )
        self._policy_loaded = False
        self._operation_lock = asyncio.Lock()
        # 手动关网后禁止协调器自动开网；策略自动断网不进入此集合
        self._suppress_auto_enable: set[str] = set()
        self._internet_action_depth = 0
        # 点按后的目标态：MQTT 尚未跟上时，refresh 不得盖回旧值
        self._pending_internet: dict[str, bool] = {}
        merged = {**entry.data, **entry.options}
        self._tv_entity_ids = {
            tv_key: merged.get(option_key)
            for tv_key, option_key in TV_MEDIA_PLAYER_OPTIONS.items()
        }
        self._internet_switch_ids = {
            tv_key: merged.get(
                option_key, DEFAULT_INTERNET_SWITCHES.get(tv_key)
            )
            for tv_key, option_key in TV_INTERNET_SWITCH_OPTIONS.items()
        }

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(
                seconds=merged.get("scan_interval", DEFAULT_SCAN_INTERVAL)
            ),
        )

    def internet_switch_id(self, tv_key: str) -> str | None:
        """Return the MQTT (or other) switch entity for ACL control."""
        return self._internet_switch_ids.get(tv_key)

    def tv_entity_id(self, tv_key: str) -> str | None:
        """Return the media player entity bound to a TV."""
        return self._tv_entity_ids.get(tv_key)

    def _mqtt_internet_on(self, tv_key: str) -> bool | None:
        """Read internet state from the bound switch entity."""
        entity_id = self._internet_switch_ids.get(tv_key)
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        return state.state == STATE_ON

    def _tv_activity(self, tv_key: str, now: datetime) -> bool | None:
        """Return whether the bound TV is active, inactive, or indeterminate."""
        entity_id = self._tv_entity_ids.get(tv_key)
        if not entity_id or (state := self.hass.states.get(entity_id)) is None:
            return None
        if state.state in ACTIVE_TV_STATES:
            return True
        if state.state in INACTIVE_TV_STATES:
            return False
        if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            if now - state.last_changed >= TV_UNAVAILABLE_GRACE:
                return False
        return None

    async def _async_set_internet(self, tv_key: str, enabled: bool) -> None:
        """Turn the bound MQTT switch on or off (non-blocking for snappy UI)."""
        entity_id = self._internet_switch_ids.get(tv_key)
        if not entity_id:
            raise HomeAssistantError(f"未配置上网开关: {tv_key}")
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            raise HomeAssistantError(f"上网开关不可用: {entity_id}")
        service = "turn_on" if enabled else "turn_off"
        self._internet_action_depth += 1
        try:
            # 不阻塞等 Telnet：UI 先变，ACL 后台执行
            await self.hass.services.async_call(
                "switch",
                service,
                {"entity_id": entity_id},
                blocking=False,
            )
        finally:
            self._internet_action_depth -= 1

    def _apply_internet_optimistic(self, tv_key: str, enabled: bool) -> None:
        """Patch coordinator data so proxy switch UI updates immediately."""
        self._pending_internet[tv_key] = enabled
        data = self.data
        if not isinstance(data, dict):
            data = {"statuses": {}, "available": True}
        statuses = data.setdefault("statuses", {})
        status = statuses.setdefault(tv_key, {})
        status["internet_enabled"] = enabled
        status["switch_available"] = True
        status["auto_enabled"] = False
        status["auto_disabled"] = False
        if enabled:
            status.pop("disable_reason", None)
            status.pop("manual_hold_off", None)
        else:
            status["manual_hold_off"] = True
        self.async_set_updated_data(data)

    def _resolve_internet_enabled(
        self, tv_key: str, mqtt_on: bool | None
    ) -> bool:
        """Prefer pending target until MQTT state catches up."""
        pending = self._pending_internet.get(tv_key)
        if pending is None:
            return bool(mqtt_on) if mqtt_on is not None else False
        if mqtt_on is not None and bool(mqtt_on) == pending:
            self._pending_internet.pop(tv_key, None)
            return pending
        return pending

    async def _async_record_tv_activity(self, tv_key: str) -> None:
        """Persist a media player activity transition immediately."""
        async with self._operation_lock:
            now = dt_util.now()
            self.child_policy.update_tv_activity(
                tv_key, self._tv_activity(tv_key, now), now
            )
            await self._async_save_policy_locked()
        self.async_update_listeners()

    def async_setup_listeners(self) -> Callable[[], None]:
        """Listen for media_player and MQTT switch changes."""
        watch: dict[str, str] = {}
        for tv_key, entity_id in self._tv_entity_ids.items():
            if entity_id:
                watch[entity_id] = tv_key
        for tv_key, entity_id in self._internet_switch_ids.items():
            if entity_id:
                watch[entity_id] = tv_key

        if not watch:
            return lambda: None

        async def _async_state_changed(
            event: Event[EventStateChangedData],
        ) -> None:
            entity_id = event.data["entity_id"]
            tv_key = watch.get(entity_id)
            if not tv_key:
                return
            if entity_id == self._internet_switch_ids.get(tv_key):
                new_state = event.data.get("new_state")
                # 非本协调器发起的关网（HA 开关/卡片手动）→ 抑制自动开网
                if (
                    new_state is not None
                    and new_state.state != STATE_ON
                    and new_state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
                    and self._internet_action_depth == 0
                ):
                    self._suppress_auto_enable.add(tv_key)
                    _LOGGER.info("手动关网，暂停自动开网: %s", tv_key)
                elif new_state is not None and new_state.state == STATE_ON:
                    self._suppress_auto_enable.discard(tv_key)
            if entity_id == self._tv_entity_ids.get(tv_key):
                await self._async_record_tv_activity(tv_key)
            await self.async_request_refresh()

        return async_track_state_change_event(
            self.hass,
            list(watch),
            _async_state_changed,
        )

    async def async_load_policy(self) -> None:
        """Load child policy state from storage."""
        data = await self._store.async_load()
        if data:
            self.child_policy.load_from_dict(data)
        for tv_key in TVS:
            state = self.child_policy.get_state(tv_key)
            preset = self.child_policy.get_window_preset(tv_key)
            if (
                state.settings.window_start,
                state.settings.window_end,
            ) != WINDOW_PRESETS[preset]:
                self.child_policy.set_window_preset(tv_key, preset)
        await self._async_save_policy_locked()
        self._policy_loaded = True

    async def _async_save_policy_locked(self, force: bool = False) -> None:
        """Persist policy while caller owns the operation lock."""
        if not force and not self.child_policy.dirty:
            return
        await self._store.async_save(self.child_policy.to_dict())
        self.child_policy.mark_clean()

    async def async_save_policy(self, force: bool = False) -> None:
        """Persist child policy safely."""
        async with self._operation_lock:
            await self._async_save_policy_locked(force)

    async def _async_update_data(self) -> dict[str, Any]:
        if not self._policy_loaded:
            await self.async_load_policy()

        async with self._operation_lock:
            now = dt_util.now()
            for tv_key in TVS:
                self.child_policy.update_tv_activity(
                    tv_key, self._tv_activity(tv_key, now), now
                )
            await self._async_save_policy_locked()

            statuses: dict[str, Any] = {}
            any_available = False

            for tv_key in TVS:
                mqtt_on = self._mqtt_internet_on(tv_key)
                switch_id = self._internet_switch_ids.get(tv_key)
                entity_id = self._tv_entity_ids.get(tv_key)
                tv_active = self._tv_activity(tv_key, now)
                available = mqtt_on is not None
                if available:
                    any_available = True

                enabled = self._resolve_internet_enabled(tv_key, mqtt_on)
                statuses[tv_key] = {
                    "internet_enabled": enabled,
                    "mqtt_switch_entity_id": switch_id,
                    "media_player_entity_id": entity_id,
                    "tv_active": tv_active,
                    "switch_available": available,
                }

                if not available:
                    continue

                state = self.child_policy.get_state(tv_key)
                if not entity_id:
                    self.child_policy.discard_session(tv_key)
                elif tv_active is False and state.runtime.session_start:
                    _, stop_reason = self.child_policy.should_disable(
                        tv_key, enabled, now
                    )
                    self.child_policy.end_session(
                        tv_key,
                        now,
                        start_cooldown=stop_reason == SESSION_LIMIT_REASON,
                    )

                if not state.settings.child_enabled:
                    self.child_policy.end_session(tv_key, now)
                    continue

                if not enabled and state.runtime.session_start:
                    _, stop_reason = self.child_policy.should_disable(
                        tv_key, True, now
                    )
                    self.child_policy.end_session(
                        tv_key,
                        now,
                        start_cooldown=stop_reason == SESSION_LIMIT_REASON,
                    )

                state = self.child_policy.get_state(tv_key)
                if state.runtime.session_start:
                    should_off, reason = self.child_policy.should_disable(
                        tv_key, enabled, now
                    )
                    if not should_off:
                        continue

                    _LOGGER.info(
                        "儿童控制自动断网: %s, 原因: %s",
                        TVS[tv_key]["name"],
                        reason,
                    )
                    try:
                        await self._async_set_internet(tv_key, False)
                    except HomeAssistantError as err:
                        statuses[tv_key]["disable_error"] = str(err)
                        statuses[tv_key]["disable_reason"] = reason
                        _LOGGER.error("自动断网失败 %s: %s", tv_key, err)
                        continue

                    self.child_policy.end_session(
                        tv_key,
                        now,
                        start_cooldown=reason == SESSION_LIMIT_REASON,
                    )
                    statuses[tv_key]["internet_enabled"] = False
                    statuses[tv_key]["auto_disabled"] = True
                    statuses[tv_key]["disable_reason"] = reason
                    continue

                can_enable, deny_reason = self.child_policy.can_enable(
                    tv_key, now
                )
                if not can_enable:
                    statuses[tv_key]["disable_reason"] = deny_reason
                    if enabled:
                        try:
                            await self._async_set_internet(tv_key, False)
                        except HomeAssistantError as err:
                            statuses[tv_key]["disable_error"] = str(err)
                            _LOGGER.error("策略断网失败 %s: %s", tv_key, err)
                        else:
                            statuses[tv_key]["internet_enabled"] = False
                            statuses[tv_key]["auto_disabled"] = True
                    continue

                if not enabled:
                    if tv_key in self._suppress_auto_enable:
                        statuses[tv_key]["manual_hold_off"] = True
                        continue
                    try:
                        await self._async_set_internet(tv_key, True)
                    except HomeAssistantError as err:
                        statuses[tv_key]["enable_error"] = str(err)
                        _LOGGER.error("自动开网失败 %s: %s", tv_key, err)
                        continue
                    enabled = True
                    statuses[tv_key]["internet_enabled"] = True
                    statuses[tv_key]["auto_enabled"] = True

                if entity_id and tv_active is True:
                    self.child_policy.start_session(tv_key, now)

            await self._async_save_policy_locked()
            if not any_available:
                _LOGGER.warning("没有可用的 MQTT 上网开关实体，实体将标记为不可用")
            return {"statuses": statuses, "available": any_available}

    async def async_enable_tv(self, tv_key: str) -> None:
        """Enable internet after checking child policy (UI returns immediately)."""
        # 不抢 operation_lock：否则 refresh/落盘会卡住开关数秒
        now = dt_util.now()
        can_enable, reason = self.child_policy.can_enable(tv_key, now)
        if not can_enable:
            raise ChildPolicyDenied(reason)

        self._suppress_auto_enable.discard(tv_key)
        self._apply_internet_optimistic(tv_key, True)
        self.hass.async_create_task(self._async_enable_tv_bg(tv_key))

    async def _async_enable_tv_bg(self, tv_key: str) -> None:
        try:
            async with self._operation_lock:
                now = dt_util.now()
                if self.child_policy.get_state(
                    tv_key
                ).settings.child_enabled and self._tv_activity(tv_key, now) is True:
                    self.child_policy.start_session(tv_key, now)
            if not self._mqtt_internet_on(tv_key):
                await self._async_set_internet(tv_key, True)
            async with self._operation_lock:
                await self._async_save_policy_locked()
        except HomeAssistantError as err:
            _LOGGER.error("开网后台失败 %s: %s", tv_key, err)
            self._apply_internet_optimistic(tv_key, False)
        self.hass.async_create_task(self.async_request_refresh())

    async def async_disable_tv(self, tv_key: str) -> None:
        """Disable internet (UI returns immediately)."""
        self._suppress_auto_enable.add(tv_key)
        self._apply_internet_optimistic(tv_key, False)
        self.hass.async_create_task(self._async_disable_tv_bg(tv_key))

    async def _async_disable_tv_bg(self, tv_key: str) -> None:
        try:
            async with self._operation_lock:
                now = dt_util.now()
                _, stop_reason = self.child_policy.should_disable(
                    tv_key, True, now
                )
                self.child_policy.end_session(
                    tv_key,
                    now,
                    start_cooldown=stop_reason == SESSION_LIMIT_REASON,
                )
            await self._async_set_internet(tv_key, False)
            async with self._operation_lock:
                await self._async_save_policy_locked()
        except HomeAssistantError as err:
            _LOGGER.error("关网后台失败 %s: %s", tv_key, err)
            self._suppress_auto_enable.discard(tv_key)
            self._apply_internet_optimistic(tv_key, True)
        self.hass.async_create_task(self.async_request_refresh())

    async def async_update_policy(
        self, update: Callable[[ChildPolicyManager], None]
    ) -> None:
        """Apply and persist a policy setting atomically."""
        async with self._operation_lock:
            update(self.child_policy)
            await self._async_save_policy_locked()
        self.async_update_listeners()

    async def async_reset_daily(self, tv_key: str) -> None:
        """Reset today's child-policy counters for one TV."""
        async with self._operation_lock:
            now = dt_util.now()
            self.child_policy.reset_daily(tv_key, now)
            self.child_policy.reset_tv_on(tv_key, now)
            await self._async_save_policy_locked()
        self.async_update_listeners()

    async def async_set_child_enabled(
        self, tv_key: str, enabled: bool
    ) -> None:
        """Enable or disable child control and reconcile current state."""
        async with self._operation_lock:
            now = dt_util.now()
            self.child_policy.set_child_enabled(tv_key, enabled)
            currently_enabled = bool(self._mqtt_internet_on(tv_key))
            if (
                enabled
                and currently_enabled
                and self._tv_activity(tv_key, now) is True
            ):
                self.child_policy.start_session(tv_key, now)
            elif not enabled:
                self.child_policy.end_session(tv_key, now)
            await self._async_save_policy_locked()
        await self.async_request_refresh()


class ChildPolicyDenied(Exception):
    """Raised when child policy rejects an enable request."""
