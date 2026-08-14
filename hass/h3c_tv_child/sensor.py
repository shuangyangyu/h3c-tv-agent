"""Sensor platform for H3C TV Control."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, TVS, TVConfig
from .coordinator import H3CTVChildCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up child-control sensor entities."""
    coordinator: H3CTVChildCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = []
    for tv_key, tv_info in TVS.items():
        entities.append(H3CTVDailyUsedSensor(coordinator, entry, tv_key, tv_info))
        entities.append(
            H3CTVSessionRemainingSensor(coordinator, entry, tv_key, tv_info)
        )
        entities.append(
            H3CTVCooldownRemainingSensor(coordinator, entry, tv_key, tv_info)
        )
        entities.append(H3CTVOnTodaySensor(coordinator, entry, tv_key, tv_info))
    async_add_entities(entities)


class H3CTVBaseSensor(CoordinatorEntity[H3CTVChildCoordinator], SensorEntity):
    """Base class for H3C TV sensors."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "min"

    def __init__(
        self,
        coordinator: H3CTVChildCoordinator,
        entry: ConfigEntry,
        tv_key: str,
        tv_info: TVConfig,
    ) -> None:
        """Initialize a child-control sensor."""
        super().__init__(coordinator)
        self.tv_key = tv_key
        self.tv_info = tv_info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{tv_key}")},
            name=tv_info["name"],
            manufacturer="Sony",
            model="TV Child (MQTT)",
            via_device=(DOMAIN, entry.entry_id),
        )

    @property
    def available(self) -> bool:
        """Return whether coordinator data is available."""
        status = (
            self.coordinator.data.get("statuses", {}).get(self.tv_key, {})
            if self.coordinator.data
            else {}
        )
        return (
            super().available
            and self.coordinator.data is not None
            and self.coordinator.data.get("available", False)
            and bool(status.get("media_player_entity_id"))
        )


class H3CTVDailyUsedSensor(H3CTVBaseSensor):
    """Sensor for daily internet usage in minutes."""

    def __init__(
        self,
        coordinator: H3CTVChildCoordinator,
        entry: ConfigEntry,
        tv_key: str,
        tv_info: TVConfig,
    ) -> None:
        """Initialize the daily usage sensor."""
        super().__init__(coordinator, entry, tv_key, tv_info)
        self._attr_unique_id = f"{entry.entry_id}_{tv_key}_daily_used"
        self._attr_name = "今日已用"
        self._attr_icon = "mdi:clock-outline"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float:
        """Return today's usage in minutes."""
        return self.coordinator.child_policy.get_daily_used(
            self.tv_key, dt_util.now()
        )


class H3CTVSessionRemainingSensor(H3CTVBaseSensor):
    """Sensor for remaining session time in minutes."""

    def __init__(
        self,
        coordinator: H3CTVChildCoordinator,
        entry: ConfigEntry,
        tv_key: str,
        tv_info: TVConfig,
    ) -> None:
        """Initialize the session remaining sensor."""
        super().__init__(coordinator, entry, tv_key, tv_info)
        self._attr_unique_id = f"{entry.entry_id}_{tv_key}_session_remaining"
        self._attr_name = "本次剩余"
        self._attr_icon = "mdi:timer-sand"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float:
        """Return remaining minutes in the active session."""
        return round(
            self.coordinator.child_policy.get_session_remaining(
                self.tv_key, dt_util.now()
            ),
            1,
        )


class H3CTVCooldownRemainingSensor(H3CTVBaseSensor):
    """Sensor for remaining cooldown time in minutes."""

    def __init__(
        self,
        coordinator: H3CTVChildCoordinator,
        entry: ConfigEntry,
        tv_key: str,
        tv_info: TVConfig,
    ) -> None:
        """Initialize the cooldown remaining sensor."""
        super().__init__(coordinator, entry, tv_key, tv_info)
        self._attr_unique_id = f"{entry.entry_id}_{tv_key}_cooldown_remaining"
        self._attr_name = "冷却剩余"
        self._attr_icon = "mdi:timer-sand"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> float:
        """Return remaining cooldown minutes."""
        return round(
            self.coordinator.child_policy.get_cooldown_remaining(
                self.tv_key, dt_util.now()
            ),
            1,
        )


class H3CTVOnTodaySensor(H3CTVBaseSensor):
    """Sensor for today's total TV power-on time."""

    def __init__(
        self,
        coordinator: H3CTVChildCoordinator,
        entry: ConfigEntry,
        tv_key: str,
        tv_info: TVConfig,
    ) -> None:
        """Initialize the daily TV power-on sensor."""
        super().__init__(coordinator, entry, tv_key, tv_info)
        self._attr_unique_id = f"{entry.entry_id}_{tv_key}_tv_on_today"
        self._attr_translation_key = "tv_on_today"
        self._attr_icon = "mdi:television"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def available(self) -> bool:
        """Return whether this TV has a media player binding."""
        return bool(self.coordinator.tv_entity_id(self.tv_key))

    @property
    def native_value(self) -> float:
        """Return today's TV power-on time in minutes."""
        return self.coordinator.child_policy.get_tv_on_minutes(
            self.tv_key, dt_util.now()
        )
