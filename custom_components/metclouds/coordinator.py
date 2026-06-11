"""DataUpdateCoordinator for the MET Cloud Layers integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MetCloudsApiClient, MetCloudsError, MetCloudsRateLimitError
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
)
from .model import MetCloudsData, Weights, parse_forecast

_LOGGER = logging.getLogger(__name__)

type MetCloudsConfigEntry = ConfigEntry[MetCloudsDataUpdateCoordinator]


class MetCloudsDataUpdateCoordinator(DataUpdateCoordinator[MetCloudsData]):
    """Coordinator that fetches and parses MET cloud-layer forecasts."""

    config_entry: MetCloudsConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: MetCloudsConfigEntry
    ) -> None:
        """Initialise the coordinator from a config entry."""
        self.client = MetCloudsApiClient(
            session=async_get_clientsession(hass),
            latitude=config_entry.data[CONF_LATITUDE],
            longitude=config_entry.data[CONF_LONGITUDE],
            altitude=config_entry.data.get(CONF_ALTITUDE),
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=self._interval_from_options(config_entry),
        )
        self._rate_limit_warned = False

    @staticmethod
    def _interval_from_options(config_entry: MetCloudsConfigEntry) -> timedelta:
        minutes = config_entry.options.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_MINUTES
        )
        return timedelta(minutes=minutes)

    def _weights_from_options(self) -> Weights:
        options = self.config_entry.options
        return Weights(
            low=options.get(CONF_WEIGHT_LOW, DEFAULT_WEIGHT_LOW),
            medium=options.get(CONF_WEIGHT_MEDIUM, DEFAULT_WEIGHT_MEDIUM),
            high=options.get(CONF_WEIGHT_HIGH, DEFAULT_WEIGHT_HIGH),
            fog=options.get(CONF_WEIGHT_FOG, DEFAULT_WEIGHT_FOG),
        )

    async def _async_update_data(self) -> MetCloudsData:
        try:
            raw = await self.client.fetch()
        except MetCloudsRateLimitError as err:
            if not self._rate_limit_warned:
                _LOGGER.warning(
                    "MET API rate limit hit; consider raising the update "
                    "interval in the integration options. (%s)",
                    err,
                )
                self._rate_limit_warned = True
            raise UpdateFailed(str(err)) from err
        except MetCloudsError as err:
            raise UpdateFailed(str(err)) from err

        self._rate_limit_warned = False
        return parse_forecast(raw, self._weights_from_options())
