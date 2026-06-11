"""Diagnostics support for the MET Cloud Layers integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_LATITUDE, CONF_LONGITUDE
from .coordinator import MetCloudsConfigEntry

TO_REDACT = {CONF_LATITUDE, CONF_LONGITUDE}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MetCloudsConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry (location redacted)."""
    coordinator = entry.runtime_data
    data = coordinator.data

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "last_update_success": coordinator.last_update_success,
        "forecast": None
        if data is None
        else {
            "updated_at": data.updated_at.isoformat() if data.updated_at else None,
            "weights": {
                "low": data.weights.low,
                "medium": data.weights.medium,
                "high": data.weights.high,
                "fog": data.weights.fog,
            },
            "point_count": len(data.points),
            "hourly": data.hourly_attribute(),
        },
    }
