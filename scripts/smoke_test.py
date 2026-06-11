#!/usr/bin/env python3
"""Standalone smoke test: fetch a live MET forecast and print derived values.

Usage::

    python3 scripts/smoke_test.py [LAT] [LON]

Defaults to Oslo if no coordinates are given. Needs ``aiohttp``; does not
need Home Assistant.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _load  # noqa: F401, E402 - registers the package without HA installed

from metclouds.api import MetCloudsApiClient  # noqa: E402
from metclouds.model import parse_forecast  # noqa: E402


async def main() -> None:
    lat = float(sys.argv[1]) if len(sys.argv) > 1 else 59.9139
    lon = float(sys.argv[2]) if len(sys.argv) > 2 else 10.7522

    async with aiohttp.ClientSession() as session:
        client = MetCloudsApiClient(session, lat, lon)
        raw = await client.fetch()
        # Exercise the conditional-request path too: should be a cached 304.
        raw2 = await client.fetch()
        assert raw2 is raw or raw2 == raw, "second fetch should reuse cache"

    data = parse_forecast(raw)
    now = datetime.now(timezone.utc).astimezone()

    print(f"Location: {data.latitude}, {data.longitude}")
    print(f"Model run: {data.updated_at}")
    print(f"Points: {len(data.points)} (hourly attr: {len(data.hourly_attribute())})")
    print()
    print(f"Cloud total now:        {data.current(now, lambda p: p.total)} %")
    print(f"Cloud low now:          {data.current(now, lambda p: p.low)} %")
    print(f"Cloud medium now:       {data.current(now, lambda p: p.medium)} %")
    print(f"Cloud high now:         {data.current(now, lambda p: p.high)} %")
    print(f"Fog now:                {data.current(now, lambda p: p.fog)} %")
    print(f"Transmittance now:      {data.transmittance_now(now)} %")
    print(f"Low clouds next 3 h:    {data.cloud_low_next_3h(now)} %")
    print(f"Transmittance next 3 h: {data.transmittance_next_3h(now)} %")
    print(f"Sky quality today rem.: {data.sky_quality_today_remaining(now)} %")
    print(f"Sky quality tomorrow:   {data.sky_quality_tomorrow(now)} %")


if __name__ == "__main__":
    asyncio.run(main())
