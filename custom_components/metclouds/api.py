"""Async client for the MET Norway Locationforecast API.

Implements the parts of the MET terms of service that matter for a polling
client: an identifying User-Agent, coordinates truncated to four decimals,
and conditional requests via If-Modified-Since so unchanged data is never
re-downloaded (the server answers 304 and we reuse the cached body).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .const import API_URL, REQUEST_TIMEOUT, USER_AGENT

_LOGGER = logging.getLogger(__name__)


class MetCloudsError(Exception):
    """Base error for the MET API client."""


class MetCloudsRateLimitError(MetCloudsError):
    """Raised when MET throttles us (HTTP 429)."""


class MetCloudsConnectionError(MetCloudsError):
    """Raised for network problems or unexpected server responses."""


class MetCloudsApiClient:
    """Thin async wrapper around Locationforecast ``complete``.

    The client deliberately holds no Home Assistant references so it can be
    exercised standalone (see the repo's smoke-test script). It caches the
    last response body and Last-Modified header for conditional requests.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        latitude: float,
        longitude: float,
        altitude: int | None = None,
    ) -> None:
        """Initialise the client for one location."""
        # MET requires at most 4 decimals; more can yield 403 Forbidden.
        self._params: dict[str, Any] = {
            "lat": f"{latitude:.4f}",
            "lon": f"{longitude:.4f}",
        }
        if altitude is not None:
            self._params["altitude"] = int(altitude)
        self._session = session
        self._last_modified: str | None = None
        self._last_raw: dict[str, Any] | None = None
        self._deprecation_warned = False

    @property
    def last_raw(self) -> dict[str, Any] | None:
        """The most recently fetched response body, if any."""
        return self._last_raw

    async def fetch(self) -> dict[str, Any]:
        """Fetch the forecast, reusing the cached body on HTTP 304."""
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
        if self._last_modified and self._last_raw is not None:
            headers["If-Modified-Since"] = self._last_modified

        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                response = await self._session.get(
                    API_URL, params=self._params, headers=headers
                )
        except asyncio.TimeoutError as err:
            raise MetCloudsConnectionError(
                f"Timeout connecting to the MET API at {API_URL}"
            ) from err
        except aiohttp.ClientError as err:
            raise MetCloudsConnectionError(
                f"Error connecting to the MET API: {err}"
            ) from err

        if response.status == 304:
            if self._last_raw is not None:
                _LOGGER.debug("MET data unchanged (304); reusing cached body")
                return self._last_raw
            # 304 without a cached body should not happen; refetch cleanly.
            self._last_modified = None
            return await self.fetch()
        if response.status == 429:
            raise MetCloudsRateLimitError(
                "MET API throttled the request (HTTP 429); raise the update "
                "interval in the integration options"
            )
        if response.status == 403:
            raise MetCloudsConnectionError(
                "MET API rejected the request (HTTP 403) - usually a missing/"
                "blocked User-Agent or more than 4 coordinate decimals"
            )
        if response.status == 422:
            raise MetCloudsConnectionError(
                "Location is outside the geographic area supported by the "
                "MET API (HTTP 422)"
            )
        if response.status >= 400:
            text = await _safe_text(response)
            raise MetCloudsConnectionError(
                f"Unexpected MET API response (HTTP {response.status}): {text}"
            )
        if response.status == 203 and not self._deprecation_warned:
            _LOGGER.warning(
                "MET API answered 203: this product version is deprecated; "
                "check https://api.met.no for a replacement"
            )
            self._deprecation_warned = True

        try:
            raw = await response.json()
        except (aiohttp.ContentTypeError, ValueError) as err:
            raise MetCloudsConnectionError(
                "MET API returned a non-JSON response"
            ) from err
        if not isinstance(raw, dict):
            raise MetCloudsConnectionError(
                "MET API returned an unexpected payload shape"
            )

        self._last_modified = response.headers.get("Last-Modified")
        self._last_raw = raw
        return raw


async def _safe_text(response: aiohttp.ClientResponse) -> str:
    """Return a short snippet of a response body for error messages."""
    try:
        text = await response.text()
    except Exception:  # noqa: BLE001 - best effort for logging only
        return "<unreadable body>"
    return text[:200]
