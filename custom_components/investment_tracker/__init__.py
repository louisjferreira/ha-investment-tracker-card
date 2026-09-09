"""Investment Tracker Home Assistant backend."""

from __future__ import annotations

import asyncio
from datetime import datetime, time
import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store

_LOGGER = logging.getLogger(__name__)

DOMAIN = "investment_tracker"
CONF_DAILY_REFRESH_TIME = "daily_refresh_time"
CONF_MANUAL_REFRESH_LIMIT = "manual_refresh_limit"
CONF_OPENFIGI_API_KEY = "openfigi_api_key"
DEFAULT_DAILY_REFRESH_TIME = "23:15:00"
DEFAULT_MANUAL_REFRESH_LIMIT = 3
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.refresh_state"
ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_DAILY_REFRESH_TIME, default=DEFAULT_DAILY_REFRESH_TIME): cv.time,
                vol.Optional(CONF_MANUAL_REFRESH_LIMIT, default=DEFAULT_MANUAL_REFRESH_LIMIT): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=100)
                ),
                vol.Optional(CONF_OPENFIGI_API_KEY, default=""): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


class RefreshManager:
    """Persist and enforce manual refresh limits."""

    def __init__(self, hass: HomeAssistant, limit: int) -> None:
        self.hass = hass
        self.limit = limit
        self.store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self.count = 0
        self.date = ""
        self.last_refresh: str | None = None
        self._lock = asyncio.Lock()

    async def async_load(self) -> None:
        data = await self.store.async_load() or {}
        self.date = str(data.get("date", ""))
        self.count = int(data.get("manual_count", 0) or 0)
        self.last_refresh = data.get("last_refresh")
        self._reset_if_new_day()

    def _today(self) -> str:
        return datetime.now(self.hass.config.time_zone).date().isoformat()

    def _reset_if_new_day(self) -> None:
        today = self._today()
        if self.date != today:
            self.date = today
            self.count = 0

    async def _save(self) -> None:
        await self.store.async_save(
            {"date": self.date, "manual_count": self.count, "last_refresh": self.last_refresh}
        )

    async def async_manual_refresh(self) -> tuple[bool, int, str | None]:
        async with self._lock:
            self._reset_if_new_day()
            if self.count >= self.limit:
                return False, 0, "Daily manual refresh limit reached."
            if not self.hass.services.has_service("yahoofinance", "refresh_symbols"):
                return False, self.limit - self.count, "The Yahoo Finance refresh service is not available."
            await self.hass.services.async_call("yahoofinance", "refresh_symbols", {}, blocking=True)
            self.count += 1
            self.last_refresh = datetime.now(self.hass.config.time_zone).isoformat()
            await self._save()
            return True, max(0, self.limit - self.count), None

    async def async_automatic_refresh(self) -> None:
        if not self.hass.services.has_service("yahoofinance", "refresh_symbols"):
            _LOGGER.warning("Yahoo Finance refresh service is not available; skipping automatic refresh")
            return
        try:
            await self.hass.services.async_call("yahoofinance", "refresh_symbols", {}, blocking=True)
            self.last_refresh = datetime.now(self.hass.config.time_zone).isoformat()
            await self._save()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Investment Tracker automatic refresh failed: %s", err)

    def status(self) -> dict[str, Any]:
        self._reset_if_new_day()
        return {
            "manual_refresh_limit": self.limit,
            "manual_refresh_count": self.count,
            "manual_refresh_remaining": max(0, self.limit - self.count),
            "last_refresh": self.last_refresh,
            "date": self.date,
        }


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Investment Tracker backend."""
    cfg = config.get(DOMAIN, {})
    manager = RefreshManager(hass, cfg[CONF_MANUAL_REFRESH_LIMIT])
    await manager.async_load()
    hass.data[DOMAIN] = {"manager": manager, "config": cfg}

    refresh_time: time = cfg[CONF_DAILY_REFRESH_TIME]

    async def daily_refresh(_now: datetime) -> None:
        await manager.async_automatic_refresh()

    hass.data[DOMAIN]["unsubscribe_time"] = async_track_time_change(
        hass, daily_refresh, hour=refresh_time.hour, minute=refresh_time.minute, second=refresh_time.second
    )

    websocket_api.async_register_command(hass, websocket_lookup_isin)
    websocket_api.async_register_command(hass, websocket_refresh)
    websocket_api.async_register_command(hass, websocket_refresh_status)
    return True


@websocket_api.websocket_command(
    {vol.Required("type"): "investment_tracker/lookup_isin", vol.Required("isin"): str}
)
@websocket_api.async_response
async def websocket_lookup_isin(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Resolve an ISIN using OpenFIGI from Home Assistant's backend."""
    isin = msg["isin"].strip().upper()
    if not ISIN_RE.fullmatch(isin):
        connection.send_error(msg["id"], "invalid_isin", "Enter a valid 12-character ISIN.")
        return

    api_key = hass.data[DOMAIN]["config"].get(CONF_OPENFIGI_API_KEY, "")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key:
        headers["X-OPENFIGI-APIKEY"] = api_key

    session = async_get_clientsession(hass)
    try:
        async with session.post(
            "https://api.openfigi.com/v3/mapping",
            json=[{"idType": "ID_ISIN", "idValue": isin}],
            headers=headers,
            timeout=15,
        ) as response:
            if response.status != 200:
                body = await response.text()
                raise RuntimeError(f"OpenFIGI returned HTTP {response.status}: {body[:200]}")
            payload = await response.json()
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "lookup_failed", str(err))
        return

    job = payload[0] if payload else {}
    results = [
        {
            "figi": item.get("figi"),
            "ticker": item.get("ticker"),
            "name": item.get("name"),
            "exchangeCode": item.get("exchCode"),
            "securityType": item.get("securityType"),
            "securityType2": item.get("securityType2"),
            "marketSector": item.get("marketSector"),
            "securityDescription": item.get("securityDescription"),
        }
        for item in (job.get("data", []) or [])
    ]

    if not results:
        connection.send_error(
            msg["id"], "not_found", job.get("warning", "No security was found for that ISIN.")
        )
        return

    connection.send_result(msg["id"], {"isin": isin, "results": results})


@websocket_api.websocket_command({vol.Required("type"): "investment_tracker/refresh"})
@websocket_api.async_response
async def websocket_refresh(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Perform a rate-limited manual Yahoo Finance refresh."""
    manager: RefreshManager = hass.data[DOMAIN]["manager"]
    success, remaining, error = await manager.async_manual_refresh()
    if not success:
        connection.send_error(msg["id"], "refresh_failed", error or "Refresh failed.")
        return
    connection.send_result(msg["id"], {"remaining": remaining, **manager.status()})


@websocket_api.websocket_command({vol.Required("type"): "investment_tracker/refresh_status"})
@callback
def websocket_refresh_status(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the current manual refresh quota."""
    connection.send_result(msg["id"], hass.data[DOMAIN]["manager"].status())
