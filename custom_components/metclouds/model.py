"""Pure data model and derived-value math for MET cloud-layer forecasts.

This module intentionally has **no Home Assistant imports** so the parsing and
the derived-value helpers can be exercised standalone (see ``scripts`` in the
repository). The Home Assistant coordinator feeds it the raw Locationforecast
JSON and a timezone-aware ``now``.

The headline derived value is a *sky transmittance* heuristic: an estimate of
the fraction of clear-sky irradiance that reaches the ground, computed from
the layered cloud fractions. Low clouds attenuate far more than high cirrus,
so each layer gets its own weight::

    attenuation = w_low*low + w_medium*medium + w_high*high + w_fog*fog
    transmittance = 1 - min(1, attenuation)        (fractions 0..1)

The *sky quality* aggregates weight each forecast hour by solar elevation
(``sin(elevation)``), so a cloudy 05:00 barely matters while a cloudy noon
dominates — a proxy for how much PV production the clouds will actually cost.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from typing import Any, Callable

ONE_HOUR = timedelta(hours=1)
# Gap between the last hourly samples and the 6-hourly tail of the series.
MAX_STEP = timedelta(hours=6)


def _parse_ts(value: str) -> datetime:
    """Parse an ISO-8601 timestamp (``...Z`` or offset) to aware UTC."""
    text = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def solar_elevation_deg(ts: datetime, latitude: float, longitude: float) -> float:
    """Solar elevation angle (degrees) at ``ts`` for a location.

    NOAA's approximation (Spencer series for declination and the equation of
    time); accurate to a fraction of a degree, which is plenty for weighting
    forecast hours by PV relevance.
    """
    t = ts.astimezone(timezone.utc)
    doy = t.timetuple().tm_yday
    frac_hour = t.hour + t.minute / 60.0 + t.second / 3600.0

    gamma = 2.0 * math.pi / 365.0 * (doy - 1 + (frac_hour - 12.0) / 24.0)
    eqtime = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )
    decl = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma)
        + 0.00148 * math.sin(3 * gamma)
    )

    time_offset = eqtime + 4.0 * longitude  # minutes; longitude east-positive
    true_solar_minutes = frac_hour * 60.0 + time_offset
    hour_angle = math.radians(true_solar_minutes / 4.0 - 180.0)

    lat_r = math.radians(latitude)
    cos_zenith = math.sin(lat_r) * math.sin(decl) + math.cos(lat_r) * math.cos(
        decl
    ) * math.cos(hour_angle)
    cos_zenith = max(-1.0, min(1.0, cos_zenith))
    return 90.0 - math.degrees(math.acos(cos_zenith))


@dataclass(slots=True)
class Weights:
    """Per-layer attenuation weights for the transmittance heuristic."""

    low: float = 0.75
    medium: float = 0.40
    high: float = 0.15
    fog: float = 0.85


@dataclass(slots=True)
class CloudPoint:
    """One forecast sample; valid from ``timestamp`` until the next point."""

    timestamp: datetime  # aware, UTC
    total: float | None  # cloud_area_fraction, %
    low: float | None
    medium: float | None
    high: float | None
    fog: float | None  # absent in the 6-hourly tail of the series


@dataclass(slots=True)
class MetCloudsData:
    """Parsed forecast plus derived-value helpers."""

    updated_at: datetime | None
    latitude: float
    longitude: float
    weights: Weights = field(default_factory=Weights)
    points: list[CloudPoint] = field(default_factory=list)

    # -- transmittance ------------------------------------------------------

    def transmittance(self, point: CloudPoint) -> float | None:
        """Estimated fraction (0..1) of clear-sky irradiance getting through."""
        if point.low is None and point.medium is None and point.high is None:
            return None
        w = self.weights
        attenuation = (
            w.low * (point.low or 0.0)
            + w.medium * (point.medium or 0.0)
            + w.high * (point.high or 0.0)
            + w.fog * (point.fog or 0.0)
        ) / 100.0
        return 1.0 - min(1.0, max(0.0, attenuation))

    # -- point lookup -------------------------------------------------------

    def _duration(self, index: int) -> timedelta:
        """Validity span of a point: gap to the next one (1 h or 6 h)."""
        pts = self.points
        if index + 1 < len(pts):
            return min(MAX_STEP, pts[index + 1].timestamp - pts[index].timestamp)
        return ONE_HOUR

    def point_at(self, now: datetime) -> CloudPoint | None:
        """The point whose validity interval contains ``now``."""
        pts = self.points
        if not pts:
            return None
        now = now.astimezone(timezone.utc)
        # Tolerate a freshly-fetched series starting just after ``now``.
        if now < pts[0].timestamp:
            return pts[0] if pts[0].timestamp - now <= ONE_HOUR else None
        for i in range(len(pts)):
            if pts[i].timestamp <= now < pts[i].timestamp + self._duration(i):
                return pts[i]
        return None

    def current(
        self, now: datetime, getter: Callable[[CloudPoint], float | None]
    ) -> float | None:
        point = self.point_at(now)
        return None if point is None else getter(point)

    def transmittance_now(self, now: datetime) -> float | None:
        """Current sky transmittance as a percentage (0–100)."""
        point = self.point_at(now)
        if point is None:
            return None
        value = self.transmittance(point)
        return None if value is None else round(value * 100.0, 1)

    # -- windowed averages ---------------------------------------------------

    def window_avg(
        self,
        now: datetime,
        hours: float,
        getter: Callable[[CloudPoint], float | None],
    ) -> float | None:
        """Time-weighted average of ``getter`` over [now, now+hours]."""
        pts = self.points
        if not pts:
            return None
        start = now.astimezone(timezone.utc)
        end = start + timedelta(hours=hours)
        total_weight = 0.0
        total = 0.0
        for i, point in enumerate(pts):
            seg_start = max(start, point.timestamp)
            seg_end = min(end, point.timestamp + self._duration(i))
            if seg_end <= seg_start:
                continue
            value = getter(point)
            if value is None:
                continue
            weight = (seg_end - seg_start).total_seconds()
            total += value * weight
            total_weight += weight
        if total_weight <= 0.0:
            return None
        return round(total / total_weight, 1)

    def cloud_low_next_3h(self, now: datetime) -> float | None:
        """Average low-cloud fraction (%) over the next three hours."""
        return self.window_avg(now, 3.0, lambda p: p.low)

    def transmittance_next_3h(self, now: datetime) -> float | None:
        """Average sky transmittance (%) over the next three hours."""

        def getter(point: CloudPoint) -> float | None:
            value = self.transmittance(point)
            return None if value is None else value * 100.0

        return self.window_avg(now, 3.0, getter)

    # -- PV-weighted sky quality ----------------------------------------------

    def sky_quality(self, start: datetime, end: datetime) -> float | None:
        """Solar-elevation-weighted mean transmittance (%) over [start, end].

        Each forecast segment is weighted by ``sin(solar elevation)`` at its
        midpoint times its duration, so midday clouds dominate the score and
        night hours contribute nothing. ``None`` when the sun never rises in
        the window (or no forecast covers it).
        """
        pts = self.points
        if not pts:
            return None
        start = start.astimezone(timezone.utc)
        end = end.astimezone(timezone.utc)
        total_weight = 0.0
        total = 0.0
        for i, point in enumerate(pts):
            seg_start = max(start, point.timestamp)
            seg_end = min(end, point.timestamp + self._duration(i))
            if seg_end <= seg_start:
                continue
            value = self.transmittance(point)
            if value is None:
                continue
            midpoint = seg_start + (seg_end - seg_start) / 2
            elevation = solar_elevation_deg(midpoint, self.latitude, self.longitude)
            sun_weight = max(0.0, math.sin(math.radians(elevation)))
            if sun_weight <= 0.0:
                continue
            weight = sun_weight * (seg_end - seg_start).total_seconds()
            total += value * weight
            total_weight += weight
        if total_weight <= 0.0:
            return None
        return round(total / total_weight * 100.0, 1)

    def sky_quality_today_remaining(self, now: datetime) -> float | None:
        """Sky quality (%) from ``now`` until local midnight."""
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        next_midnight = datetime.combine(
            now.date() + timedelta(days=1), time(0), tzinfo=now.tzinfo
        )
        return self.sky_quality(now, next_midnight)

    def sky_quality_tomorrow(self, now: datetime) -> float | None:
        """Sky quality (%) over the whole of the local day after ``now``."""
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        start = datetime.combine(
            now.date() + timedelta(days=1), time(0), tzinfo=now.tzinfo
        )
        return self.sky_quality(start, start + timedelta(days=1))

    # -- export helpers --------------------------------------------------------

    def hourly_attribute(self) -> list[dict[str, Any]]:
        """Compact per-hour series for a sensor attribute (hourly part only)."""
        result: list[dict[str, Any]] = []
        for i, point in enumerate(self.points):
            if self._duration(i) > ONE_HOUR:
                break
            transmittance = self.transmittance(point)
            result.append(
                {
                    "datetime": point.timestamp.isoformat(),
                    "total": point.total,
                    "low": point.low,
                    "medium": point.medium,
                    "high": point.high,
                    "fog": point.fog,
                    "transmittance": None
                    if transmittance is None
                    else round(transmittance * 100.0, 1),
                }
            )
        return result


def parse_forecast(raw: dict[str, Any], weights: Weights | None = None) -> MetCloudsData:
    """Parse a raw Locationforecast ``complete`` JSON body."""
    coordinates = (raw.get("geometry") or {}).get("coordinates") or [0.0, 0.0]
    properties = raw.get("properties") or {}
    meta = properties.get("meta") or {}
    updated_raw = meta.get("updated_at")

    points: list[CloudPoint] = []
    for item in properties.get("timeseries") or []:
        ts_raw = item.get("time")
        if not ts_raw:
            continue
        details = ((item.get("data") or {}).get("instant") or {}).get("details") or {}
        points.append(
            CloudPoint(
                timestamp=_parse_ts(ts_raw),
                total=_as_float(details.get("cloud_area_fraction")),
                low=_as_float(details.get("cloud_area_fraction_low")),
                medium=_as_float(details.get("cloud_area_fraction_medium")),
                high=_as_float(details.get("cloud_area_fraction_high")),
                fog=_as_float(details.get("fog_area_fraction")),
            )
        )
    points.sort(key=lambda p: p.timestamp)

    return MetCloudsData(
        updated_at=_parse_ts(updated_raw) if updated_raw else None,
        latitude=float(coordinates[1]) if len(coordinates) > 1 else 0.0,
        longitude=float(coordinates[0]) if coordinates else 0.0,
        weights=weights or Weights(),
        points=points,
    )
