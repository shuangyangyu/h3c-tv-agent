"""H3C TV Child — child policy over MQTT internet switches."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.storage import Store

from .const import DOMAIN, TVS
from .coordinator import STORAGE_VERSION, H3CTVChildCoordinator, storage_key
from .lovelace import async_register_lovelace_frontend

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.SWITCH,
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up H3C TV Child from a config entry."""
    await async_register_lovelace_frontend(hass)

    coordinator = H3CTVChildCoordinator(hass, entry)
    await coordinator.async_load_policy()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="H3C TV Child (MQTT)",
        manufacturer="H3C",
        model="Child policy over h3c-tv-agent",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    entry.async_on_unload(coordinator.async_setup_listeners())
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload after options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    ):
        coordinator: H3CTVChildCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_save_policy(force=True)
        await coordinator.async_shutdown()

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove persisted child policy when an entry is deleted."""
    store: Store[dict[str, Any]] = Store(
        hass,
        STORAGE_VERSION,
        storage_key(entry.entry_id),
    )
    await store.async_remove()
