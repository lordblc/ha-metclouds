"""Constants for the MET Cloud Layers integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "metclouds"

# MET Norway Locationforecast 2.0 (complete variant has the layered clouds).
API_URL: Final = "https://api.met.no/weatherapi/locationforecast/2.0/complete"

# Config entry data keys.
CONF_LATITUDE: Final = "latitude"
CONF_LONGITUDE: Final = "longitude"
CONF_ALTITUDE: Final = "altitude"

# Options keys.
CONF_UPDATE_INTERVAL: Final = "update_interval_minutes"
CONF_WEIGHT_LOW: Final = "weight_low"
CONF_WEIGHT_MEDIUM: Final = "weight_medium"
CONF_WEIGHT_HIGH: Final = "weight_high"
CONF_WEIGHT_FOG: Final = "weight_fog"

# Defaults. The MET data file is refreshed roughly every 30 minutes (see the
# Expires response header); polling faster than that mostly yields 304s.
DEFAULT_UPDATE_INTERVAL_MINUTES: Final = 30
MIN_UPDATE_INTERVAL_MINUTES: Final = 15
MAX_UPDATE_INTERVAL_MINUTES: Final = 180

# Default attenuation weights for the sky-transmittance heuristic: the
# fraction of irradiance a 100% cover of that layer is assumed to block.
# Low stratus kills PV output; high cirrus barely dents it.
DEFAULT_WEIGHT_LOW: Final = 0.75
DEFAULT_WEIGHT_MEDIUM: Final = 0.40
DEFAULT_WEIGHT_HIGH: Final = 0.15
DEFAULT_WEIGHT_FOG: Final = 0.85

# Request timeout in seconds.
REQUEST_TIMEOUT: Final = 30

# Integration version (keep in sync with manifest.json). The MET TOS requires
# an identifying User-Agent with contact info; the repo URL serves as both.
VERSION: Final = "0.1.0"
USER_AGENT: Final = f"ha-metclouds/{VERSION} https://github.com/lordblc/ha-metclouds"

MANUFACTURER: Final = "MET Norway"

# CC BY 4.0 attribution required by the MET license.
ATTRIBUTION: Final = (
    "Weather data from the Norwegian Meteorological Institute (CC BY 4.0)"
)
