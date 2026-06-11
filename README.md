# MET Cloud Layers for Home Assistant

Layered cloud-cover forecasts — **low / mid / high clouds and fog** — from
[MET Norway's free Locationforecast API](https://api.met.no/weatherapi/locationforecast/2.0/documentation),
plus derived **sky transmittance** and **PV-weighted sky quality** sensors
aimed at solar/battery automation.

Home Assistant's built-in Met.no integration only exposes *total* cloud
cover. For solar work that's not enough: 80% cover can mean thin cirrus
(production barely dented) or solid stratus (production gone). This
integration exposes the layers and turns them into actionable numbers.

> Not affiliated with or endorsed by MET Norway, Yr or NRK.

## Sensors

| Sensor | Meaning |
|---|---|
| Cloud cover | Total cloud fraction now (%) — carries the hourly forecast series as a `hourly` attribute |
| Low / Mid / High clouds | Per-layer cloud fraction now (%) |
| Fog | Fog fraction now (%) |
| Sky transmittance | Estimated fraction of clear-sky irradiance reaching the ground now (%) |
| Low clouds next 3 h | Time-weighted average — a "will this dip persist?" signal |
| Sky transmittance next 3 h | Same window, transmittance |
| Sky quality today remaining | Solar-elevation-weighted transmittance from now to midnight (%) |
| Sky quality tomorrow | Same for tomorrow's daylight hours (%) |
| Forecast updated | Timestamp of the MET model run (diagnostic) |

The `hourly` attribute on **Cloud cover** holds ~48–54 h of
`{datetime, total, low, medium, high, fog, transmittance}` rows for use in
Node-RED, templates or ApexCharts.

### The transmittance model

A deliberately simple, tunable heuristic:

```
attenuation   = w_low·low + w_medium·medium + w_high·high + w_fog·fog   (fractions)
transmittance = 1 − min(1, attenuation)
```

Default weights: low **0.75**, medium **0.40**, high **0.15**, fog **0.85**
— all adjustable in the integration options. The *sky quality* aggregates
additionally weight each forecast hour by `sin(solar elevation)`, so a
cloudy noon costs the score far more than a cloudy 05:00.

These are estimates, not irradiance physics. Calibrate the weights against
your own PV data if you need better absolute numbers; the *relative* signal
(good day / bad day / clearing up / closing in) is the point.

## Installation

**HACS (custom repository):** HACS → Integrations → ⋮ → Custom
repositories → add this repo URL, category *Integration* → install →
restart Home Assistant.

**Manual:** copy `custom_components/metclouds/` into your HA `config/custom_components/`
and restart.

Then *Settings → Devices & services → Add integration → MET Cloud Layers*.
Only a location is needed — **no API key**.

## MET terms-of-service compliance

This integration follows the [MET API TOS](https://api.met.no/doc/TermsOfService):

- Sends an identifying `User-Agent` (`ha-metclouds/<version> <repo URL>`).
- Truncates coordinates to 4 decimals.
- Uses `If-Modified-Since` conditional requests; unchanged data is answered
  with a cheap 304 and reused locally.
- Default poll interval 30 min (MET's data file refreshes about that often).
- Data license: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) —
  the sensors carry the required attribution.

## Standalone smoke test

```bash
python3 scripts/smoke_test.py 59.5450 10.8571
```

Fetches a live forecast and prints the current layers plus the derived
metrics — no Home Assistant required (needs `aiohttp`).

## License

MIT for the code. The weather data itself is © MET Norway, CC BY 4.0.
