"""Config and options flow for the MET Cloud Layers integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .api import MetCloudsApiClient, MetCloudsError
from .const import (
    CONF_ALTITUDE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_UPDATE_INTERVAL,
    CONF_WEIGHT_FOG,
    CONF_WEIGHT_HIGH,
    CONF_WEIGHT_LOW,
    CONF_WEIGHT_MEDIUM,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    DEFAULT_WEIGHT_FOG,
    DEFAULT_WEIGHT_HIGH,
    DEFAULT_WEIGHT_LOW,
    DEFAULT_WEIGHT_MEDIUM,
    DOMAIN,
    MAX_UPDATE_INTERVAL_MINUTES,
    MIN_UPDATE_INTERVAL_MINUTES,
)


def _weight_selector() -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(min=0.0, max=1.0, step=0.05, mode=NumberSelectorMode.SLIDER)
    )


class MetCloudsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the MET Cloud Layers configuration flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Single step: location. No API key needed."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = MetCloudsApiClient(
                session=async_get_clientsession(self.hass),
                latitude=user_input[CONF_LATITUDE],
                longitude=user_input[CONF_LONGITUDE],
                altitude=user_input.get(CONF_ALTITUDE),
            )
            try:
                await client.fetch()
            except MetCloudsError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(
                    f"{user_input[CONF_LATITUDE]:.4f}_{user_input[CONF_LONGITUDE]:.4f}"
                )
                self._abort_if_unique_id_configured()
                lat = user_input[CONF_LATITUDE]
                lon = user_input[CONF_LONGITUDE]
                return self.async_create_entry(
                    title=f"MET Clouds ({lat:.2f}, {lon:.2f})",
                    data=dict(user_input),
                )

        suggested = user_input or {}
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_LATITUDE,
                    default=suggested.get(CONF_LATITUDE, self.hass.config.latitude),
                ): cv.latitude,
                vol.Required(
                    CONF_LONGITUDE,
                    default=suggested.get(CONF_LONGITUDE, self.hass.config.longitude),
                ): cv.longitude,
                vol.Optional(
                    CONF_ALTITUDE,
                    default=suggested.get(
                        CONF_ALTITUDE, int(self.hass.config.elevation or 0)
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=-500,
                        max=9000,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="m",
                    )
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> MetCloudsOptionsFlow:
        """Return the options flow handler."""
        return MetCloudsOptionsFlow()


class MetCloudsOptionsFlow(OptionsFlow):
    """Handle MET Cloud Layers options (polling and attenuation weights)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the update interval and the transmittance weights."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_UPDATE_INTERVAL,
                    default=options.get(
                        CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_MINUTES
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_UPDATE_INTERVAL_MINUTES,
                        max=MAX_UPDATE_INTERVAL_MINUTES,
                        step=5,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement="min",
                    )
                ),
                vol.Required(
                    CONF_WEIGHT_LOW,
                    default=options.get(CONF_WEIGHT_LOW, DEFAULT_WEIGHT_LOW),
                ): _weight_selector(),
                vol.Required(
                    CONF_WEIGHT_MEDIUM,
                    default=options.get(CONF_WEIGHT_MEDIUM, DEFAULT_WEIGHT_MEDIUM),
                ): _weight_selector(),
                vol.Required(
                    CONF_WEIGHT_HIGH,
                    default=options.get(CONF_WEIGHT_HIGH, DEFAULT_WEIGHT_HIGH),
                ): _weight_selector(),
                vol.Required(
                    CONF_WEIGHT_FOG,
                    default=options.get(CONF_WEIGHT_FOG, DEFAULT_WEIGHT_FOG),
                ): _weight_selector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
