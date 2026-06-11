"""The MET Cloud Layers integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import MetCloudsConfigEntry, MetCloudsDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: MetCloudsConfigEntry
) -> bool:
    """Set up MET Cloud Layers from a config entry."""
    coordinator = MetCloudsDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: MetCloudsConfigEntry
) -> bool:
    """Unload a MET Cloud Layers config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant, entry: MetCloudsConfigEntry
) -> None:
    """Reload the entry when its options change (interval or weights)."""
    await hass.config_entries.async_reload(entry.entry_id)
