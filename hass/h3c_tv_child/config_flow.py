"""Config flow for H3C TV Child (MQTT)."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import Platform
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DEFAULT_INTERNET_SWITCHES,
    DOMAIN,
    TV_INTERNET_SWITCH_OPTIONS,
    TV_MEDIA_PLAYER_OPTIONS,
    TVS,
)

_LOGGER = logging.getLogger(__name__)


def _internet_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    schema: dict[vol.Marker, Any] = {}
    for tv_key, option_key in TV_INTERNET_SWITCH_OPTIONS.items():
        suggested = defaults.get(
            option_key, DEFAULT_INTERNET_SWITCHES.get(tv_key)
        )
        schema[
            vol.Required(
                option_key,
                description={"suggested_value": suggested},
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain=Platform.SWITCH)
        )
    return vol.Schema(schema)


class H3CTVChildConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for H3C TV Child."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return options flow for media players and switch rebinding."""
        return H3CTVChildOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Bind each TV to an MQTT internet switch."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selected = [value for value in user_input.values() if value]
            if len(selected) != len(set(selected)):
                errors["base"] = "duplicate_switches"
            elif len(selected) != len(TVS):
                errors["base"] = "missing_switches"
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="H3C TV Child (MQTT)",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_internet_schema(),
            errors=errors,
        )


class H3CTVChildOptionsFlow(OptionsFlow):
    """Configure media players and optionally rebind MQTT switches."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure bindings."""
        errors: dict[str, str] = {}
        if user_input is not None:
            media = [
                user_input[k]
                for k in TV_MEDIA_PLAYER_OPTIONS.values()
                if user_input.get(k)
            ]
            switches = [
                user_input[k]
                for k in TV_INTERNET_SWITCH_OPTIONS.values()
                if user_input.get(k)
            ]
            if len(media) != len(set(media)):
                errors["base"] = "duplicate_tv_entities"
            elif len(switches) != len(set(switches)):
                errors["base"] = "duplicate_switches"
            else:
                return self.async_create_entry(title="", data=user_input)

        merged = {**self.config_entry.data, **self.config_entry.options}
        schema: dict[vol.Marker, Any] = {}
        for option_key in TV_MEDIA_PLAYER_OPTIONS.values():
            current = merged.get(option_key)
            schema[
                vol.Optional(
                    option_key,
                    description={"suggested_value": current},
                )
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain=Platform.MEDIA_PLAYER)
            )
        for tv_key, option_key in TV_INTERNET_SWITCH_OPTIONS.items():
            current = merged.get(
                option_key, DEFAULT_INTERNET_SWITCHES.get(tv_key)
            )
            schema[
                vol.Required(
                    option_key,
                    description={"suggested_value": current},
                )
            ] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain=Platform.SWITCH)
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
            errors=errors,
        )
