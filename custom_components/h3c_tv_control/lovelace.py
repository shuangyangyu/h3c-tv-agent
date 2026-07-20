"""Serve the H3C TV child-control Lovelace card."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import DOMAIN

CARD_FILENAME = "h3c-tv-child-card.js"
CARD_URL = f"/{DOMAIN}/lovelace/{CARD_FILENAME}"
_FRONTEND_REGISTERED = f"{DOMAIN}_lovelace_registered"


async def async_register_lovelace_frontend(hass: HomeAssistant) -> None:
    """Register the bundled Lovelace card static path once."""
    if hass.data.get(_FRONTEND_REGISTERED):
        return

    card_path = Path(__file__).parent / "www" / CARD_FILENAME
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                url_path=CARD_URL,
                path=str(card_path),
                cache_headers=True,
            )
        ]
    )
    hass.data[_FRONTEND_REGISTERED] = True
