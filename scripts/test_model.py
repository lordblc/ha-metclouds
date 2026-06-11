#!/usr/bin/env python3
"""Offline sanity tests for the pure model — no network, no Home Assistant.

Usage::

    python3 scripts/test_model.py [path/to/saved_response.json]

Runs synthetic-data assertions always; additionally parses a saved
Locationforecast body when a path is given.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _load  # noqa: F401, E402 - registers the package without HA installed

from metclouds.model import (  # noqa: E402
    CloudPoint,
    MetCloudsData,
    Weights,
    parse_forecast,
    solar_elevation_deg,
)

LAT, LON = 59.5450, 10.8571


def make_data(points: list[CloudPoint], weights: Weights | None = None) -> MetCloudsData:
    return MetCloudsData(
        updated_at=None,
        latitude=LAT,
        longitude=LON,
        weights=weights or Weights(),
        points=points,
    )


def test_solar_elevation() -> None:
    # June solstice-ish noon at 59.5°N: max elevation ≈ 90 − 59.5 + 23.3 ≈ 53.8°
    noon = datetime(2026, 6, 11, 11, 15, tzinfo=timezone.utc)  # ~solar noon for 10.86°E
    midnight = datetime(2026, 6, 11, 23, 15, tzinfo=timezone.utc)
    morning = datetime(2026, 6, 11, 5, 0, tzinfo=timezone.utc)

    elev_noon = solar_elevation_deg(noon, LAT, LON)
    elev_night = solar_elevation_deg(midnight, LAT, LON)
    elev_morning = solar_elevation_deg(morning, LAT, LON)

    assert 51.0 < elev_noon < 56.0, f"noon elevation off: {elev_noon}"
    assert elev_night < 0.0, f"midnight sun should be below horizon: {elev_night}"
    assert 0.0 < elev_morning < elev_noon, f"morning elevation off: {elev_morning}"
    # December noon should be low but above horizon at this latitude.
    dec_noon = solar_elevation_deg(
        datetime(2026, 12, 21, 11, 15, tzinfo=timezone.utc), LAT, LON
    )
    assert 5.0 < dec_noon < 9.0, f"winter noon elevation off: {dec_noon}"
    print(f"solar elevation ok (jun noon {elev_noon:.1f}°, dec noon {dec_noon:.1f}°)")


def test_transmittance() -> None:
    data = make_data([])
    clear = CloudPoint(datetime.now(timezone.utc), 0, 0, 0, 0, 0)
    stratus = CloudPoint(datetime.now(timezone.utc), 100, 100, 0, 0, 0)
    cirrus = CloudPoint(datetime.now(timezone.utc), 100, 0, 0, 100, 0)
    everything = CloudPoint(datetime.now(timezone.utc), 100, 100, 100, 100, 100)
    unknown = CloudPoint(datetime.now(timezone.utc), None, None, None, None, None)

    assert data.transmittance(clear) == 1.0
    assert abs(data.transmittance(stratus) - 0.25) < 1e-9  # 1 − 0.75
    assert abs(data.transmittance(cirrus) - 0.85) < 1e-9  # 1 − 0.15
    assert data.transmittance(everything) == 0.0  # clamped
    assert data.transmittance(unknown) is None
    print("transmittance ok (clear=1.0, stratus=0.25, cirrus=0.85, clamp, None)")


def test_window_and_quality() -> None:
    # Local noon window on a June day: solid low cloud for 3 h, then clear.
    base = datetime(2026, 6, 11, 10, 0, tzinfo=timezone.utc)
    points = [
        CloudPoint(base + timedelta(hours=i), *([100.0, 100.0, 0.0, 0.0, 0.0] if i < 3 else [0.0, 0.0, 0.0, 0.0, 0.0]))
        for i in range(12)
    ]
    data = make_data(points)

    now = base
    low3 = data.cloud_low_next_3h(now)
    assert low3 == 100.0, f"expected solid low cloud, got {low3}"
    t3 = data.transmittance_next_3h(now)
    assert abs(t3 - 25.0) < 0.2, f"expected ~25% transmittance, got {t3}"

    # Mixed window: 1.5 h cloud + 1.5 h clear → halfway between 25 and 100.
    t_mixed = data.transmittance_next_3h(base + timedelta(hours=1, minutes=30))
    assert abs(t_mixed - 62.5) < 0.5, f"expected ~62.5%, got {t_mixed}"

    # Sky quality over the cloudy noon + clear afternoon must land between
    # the extremes, and weighting must favour the (cloudy) high-sun hours
    # so it lands below the plain time average.
    q = data.sky_quality(base, base + timedelta(hours=12))
    assert 25.0 < q < 100.0, f"quality out of range: {q}"
    plain_avg = 25.0 * 3 / 12 + 100.0 * 9 / 12
    assert q < plain_avg, f"elevation weighting should pull below {plain_avg}, got {q}"

    # Night-only window → None.
    night = datetime(2026, 6, 11, 22, 30, tzinfo=timezone.utc)
    night_pts = [CloudPoint(night + timedelta(hours=i), 0, 0, 0, 0, 0) for i in range(2)]
    assert make_data(night_pts).sky_quality(night, night + timedelta(hours=2)) is None
    print(f"window averages + sky quality ok (q={q}, plain avg={plain_avg:.1f})")


def test_point_lookup() -> None:
    base = datetime(2026, 6, 11, 10, 0, tzinfo=timezone.utc)
    points = [
        CloudPoint(base, 10.0, 1.0, 2.0, 3.0, 0.0),
        CloudPoint(base + timedelta(hours=1), 20.0, 4.0, 5.0, 6.0, 0.0),
        # 6-hourly tail
        CloudPoint(base + timedelta(hours=7), 30.0, 7.0, 8.0, 9.0, None),
    ]
    data = make_data(points)
    assert data.point_at(base + timedelta(minutes=30)).total == 10.0
    assert data.point_at(base + timedelta(hours=1, minutes=59)).total == 20.0
    # Inside the 6-hour validity of the second-to-last point's gap.
    assert data.point_at(base + timedelta(hours=4)).total == 20.0
    assert data.point_at(base + timedelta(hours=7, minutes=30)).total == 30.0
    # Slightly before the series starts (fresh fetch) → first point.
    assert data.point_at(base - timedelta(minutes=20)).total == 10.0
    assert data.point_at(base - timedelta(hours=2)) is None
    print("point lookup ok (hourly, 6-hourly gap, pre-series tolerance)")


def test_parse_saved(path: str) -> None:
    raw = json.loads(Path(path).read_text())
    data = parse_forecast(raw)
    assert data.latitude != 0.0 and data.longitude != 0.0
    assert data.updated_at is not None
    assert len(data.points) > 50, f"too few points: {len(data.points)}"
    hourly = data.hourly_attribute()
    assert 40 <= len(hourly) <= 60, f"unexpected hourly span: {len(hourly)}"
    now = data.points[0].timestamp + timedelta(minutes=30)
    assert data.transmittance_now(now) is not None
    assert data.sky_quality_tomorrow(now) is not None
    print(
        f"saved-body parse ok ({len(data.points)} points, {len(hourly)} hourly, "
        f"T_now={data.transmittance_now(now)}%, "
        f"q_tomorrow={data.sky_quality_tomorrow(now)}%)"
    )


if __name__ == "__main__":
    test_solar_elevation()
    test_transmittance()
    test_window_and_quality()
    test_point_lookup()
    if len(sys.argv) > 1:
        test_parse_saved(sys.argv[1])
    print("all model tests passed")
