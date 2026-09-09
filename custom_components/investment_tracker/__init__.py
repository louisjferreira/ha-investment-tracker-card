"""Investment Tracker Home Assistant backend."""

from __future__ import annotations

import asyncio
from datetime import datetime, time
import logging
import re
from typing import Any
from urllib.parse import quote

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

DOMAIN = "investment_tracker"
CONF_DAILY_REFRESH_TIME = "daily_refresh_time"
CONF_MANUAL_REFRESH_LIMIT = "manual_refresh_limit"
CONF_OPENFIGI_API_KEY = "openfigi_api_key"
DEFAULT_DAILY_REFRESH_TIME = "23:15:00"
DEFAULT_MANUAL_REFRESH_LIMIT = 3
STORAGE_VERSION = 2
STORAGE_KEY = f"{DOMAIN}.refresh_state"
ISIN_RE = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
SYMBOL_RE = re.compile(r"^[A-Z0-9^._=-]{1,32}$")
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{}"
CACHE_SECONDS = 60

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


class MarketDataManager:
    """Fetch and cache market data without requiring provider-specific HA entities."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.session = async_get_clientsession(hass)
        self.cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self.symbols: set[str] = set()
        self._lock = asyncio.Lock()

    def _cache_key(self, symbol: str, source_currency: str, display_currency: str) -> str:
        return f"{symbol.upper()}|{source_currency.upper()}|{display_currency.upper()}"

    @staticmethod
    def _fx_symbol(source_currency: str, display_currency: str) -> str:
        return f"{source_currency.upper()}{display_currency.upper()}=X"

    async def _chart(self, symbol: str, range_: str = "5d", interval: str = "1d") -> dict[str, Any]:
        symbol = symbol.strip().upper()
        if not SYMBOL_RE.fullmatch(symbol):
            raise ValueError("Invalid market-data symbol.")
        url = YAHOO_CHART_URL.format(quote(symbol, safe=""))
        async with self.session.get(
            url,
            params={"range": range_, "interval": interval, "events": "div,splits", "includePrePost": "true"},
            headers={"Accept": "application/json", "User-Agent": "Home Assistant Investment Tracker"},
            timeout=15,
        ) as response:
            if response.status != 200:
                body = await response.text()
                raise RuntimeError(f"Market data returned HTTP {response.status}: {body[:200]}")
            payload = await response.json()
        result = ((payload.get("chart") or {}).get("result") or [None])[0]
        if not result:
            error = (payload.get("chart") or {}).get("error") or {}
            raise RuntimeError(error.get("description") or f"No market data returned for {symbol}.")
        return result

    @staticmethod
    def _latest(result: dict[str, Any]) -> float | None:
        meta = result.get("meta") or {}
        for key in ("regularMarketPrice", "previousClose"):
            value = meta.get(key)
            if isinstance(value, (int, float)):
                return float(value)
        quote_data = (((result.get("indicators") or {}).get("quote") or [None])[0] or {})
        closes = [value for value in (quote_data.get("close") or []) if isinstance(value, (int, float))]
        return float(closes[-1]) if closes else None

    @staticmethod
    def _history(result: dict[str, Any]) -> list[dict[str, Any]]:
        timestamps = result.get("timestamp") or []
        quote_data = (((result.get("indicators") or {}).get("quote") or [None])[0] or {})
        closes = quote_data.get("close") or []
        points: list[dict[str, Any]] = []
        for timestamp, close in zip(timestamps, closes):
            if isinstance(timestamp, (int, float)) and isinstance(close, (int, float)):
                points.append({"time": int(timestamp) * 1000, "value": float(close)})
        return points

    async def async_get(self, symbol: str, source_currency: str, display_currency: str, force: bool = False) -> dict[str, Any]:
        symbol = symbol.strip().upper()
        source_currency = source_currency.upper()
        display_currency = display_currency.upper()
        key = self._cache_key(symbol, source_currency, display_currency)
        now = dt_util.utcnow().timestamp()
        cached = self.cache.get(key)
        if cached and not force and now - cached[0] < CACHE_SECONDS:
            return cached[1]

        async with self._lock:
            cached = self.cache.get(key)
            now = dt_util.utcnow().timestamp()
            if cached and not force and now - cached[0] < CACHE_SECONDS:
                return cached[1]
            result = await self._chart(symbol, "5d", "1d")
            price = self._latest(result)
            if price is None:
                raise RuntimeError(f"No current price is available for {symbol}.")
            meta = result.get("meta") or {}
            fx = 1.0
            if source_currency != display_currency:
                fx_result = await self._chart(self._fx_symbol(source_currency, display_currency), "5d", "1d")
                fx = self._latest(fx_result) or 0.0
                if fx <= 0:
                    raise RuntimeError(f"No FX rate is available for {source_currency} → {display_currency}.")
            data = {
                "symbol": symbol,
                "price": price,
                "currency": meta.get("currency") or source_currency,
                "exchange": meta.get("exchangeName") or meta.get("fullExchangeName"),
                "fx": fx,
                "source_currency": source_currency,
                "display_currency": display_currency,
                "updated": dt_util.now().isoformat(),
            }
            self.symbols.add(symbol)
            self.cache[key] = (dt_util.utcnow().timestamp(), data)
            return data

    async def async_history(self, symbol: str, period: str) -> list[dict[str, Any]]:
        ranges = {
            "1D": ("1d", "5m"), "1W": ("5d", "30m"), "1M": ("1mo", "1d"),
            "3M": ("3mo", "1d"), "6M": ("6mo", "1d"), "1Y": ("1y", "1d"),
            "5Y": ("5y", "1wk"), "MAX": ("max", "1mo"),
        }
        range_, interval = ranges.get(period, ("1mo", "1d"))
        result = await self._chart(symbol, range_, interval)
        return self._history(result)

    async def async_refresh_all(self) -> None:
        for symbol in list(self.symbols):
            try:
                for key in [key for key in self.cache if key.startswith(f"{symbol}|")]:
                    self.cache.pop(key, None)
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Could not clear market cache for %s: %s", symbol, err)


class RefreshManager:
    """Persist and enforce manual refresh limits."""

    def __init__(self, hass: HomeAssistant, limit: int, market: MarketDataManager) -> None:
        self.hass = hass
        self.limit = limit
        self.market = market
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
        return dt_util.now().date().isoformat()

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
            await self.market.async_refresh_all()
            self.count += 1
            self.last_refresh = dt_util.now().isoformat()
            await self._save()
            return True, max(0, self.limit - self.count), None

    async def async_automatic_refresh(self) -> None:
        await self.market.async_refresh_all()
        self.last_refresh = dt_util.now().isoformat()
        await self._save()

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
    market = MarketDataManager(hass)
    manager = RefreshManager(hass, cfg[CONF_MANUAL_REFRESH_LIMIT], market)
    await manager.async_load()
    hass.data[DOMAIN] = {"manager": manager, "market": market, "config": cfg}

    refresh_time: time = cfg[CONF_DAILY_REFRESH_TIME]

    async def daily_refresh(_now: datetime) -> None:
        await manager.async_automatic_refresh()

    hass.data[DOMAIN]["unsubscribe_time"] = async_track_time_change(
        hass, daily_refresh, hour=refresh_time.hour, minute=refresh_time.minute, second=refresh_time.second
    )

    websocket_api.async_register_command(hass, websocket_lookup_isin)
    websocket_api.async_register_command(hass, websocket_refresh)
    websocket_api.async_register_command(hass, websocket_refresh_status)
    websocket_api.async_register_command(hass, websocket_market_data)
    websocket_api.async_register_command(hass, websocket_market_history)
    return True


@websocket_api.websocket_command(
    {vol.Required("type"): "investment_tracker/lookup_isin", vol.Required("isin"): str}
)
@websocket_api.async_response
async def websocket_lookup_isin(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
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
            "https://api.openfigi.com/v3/mapping", json=[{"idType": "ID_ISIN", "idValue": isin}], headers=headers, timeout=15
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
            "figi": item.get("figi"), "ticker": item.get("ticker"), "name": item.get("name"),
            "exchangeCode": item.get("exchCode"), "securityType": item.get("securityType"),
            "securityType2": item.get("securityType2"), "marketSector": item.get("marketSector"),
            "securityDescription": item.get("securityDescription"),
        }
        for item in (job.get("data", []) or [])
    ]
    if not results:
        connection.send_error(msg["id"], "not_found", job.get("warning", "No security was found for that ISIN."))
        return
    connection.send_result(msg["id"], {"isin": isin, "results": results})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "investment_tracker/market_data",
        vol.Required("symbol"): str,
        vol.Required("source_currency"): str,
        vol.Required("display_currency"): str,
        vol.Optional("force", default=False): bool,
    }
)
@websocket_api.async_response
async def websocket_market_data(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Return current price and FX data for a holding."""
    try:
        data = await hass.data[DOMAIN]["market"].async_get(
            msg["symbol"], msg["source_currency"], msg["display_currency"], msg["force"]
        )
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "market_data_failed", str(err))
        return
    connection.send_result(msg["id"], data)


@websocket_api.websocket_command(
    {vol.Required("type"): "investment_tracker/market_history", vol.Required("symbol"): str, vol.Required("period"): str}
)
@websocket_api.async_response
async def websocket_market_history(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Return historical market prices for a holding."""
    try:
        points = await hass.data[DOMAIN]["market"].async_history(msg["symbol"], msg["period"])
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "market_history_failed", str(err))
        return
    connection.send_result(msg["id"], {"symbol": msg["symbol"].upper(), "period": msg["period"], "points": points})


@websocket_api.websocket_command({vol.Required("type"): "investment_tracker/refresh"})
@websocket_api.async_response
async def websocket_refresh(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Perform a rate-limited manual market-data refresh."""
    manager: RefreshManager = hass.data[DOMAIN]["manager"]
    try:
        success, remaining, error = await manager.async_manual_refresh()
    except Exception as err:  # noqa: BLE001
        connection.send_error(msg["id"], "refresh_failed", str(err))
        return
    if not success:
        connection.send_error(msg["id"], "refresh_failed", error or "Refresh failed.")
        return
    connection.send_result(msg["id"], {"remaining": remaining, **manager.status()})


@websocket_api.websocket_command({vol.Required("type"): "investment_tracker/refresh_status"})
@callback
def websocket_refresh_status(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Return the current manual refresh quota."""
    connection.send_result(msg["id"], hass.data[DOMAIN]["manager"].status())
