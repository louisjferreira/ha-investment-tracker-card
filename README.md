# Home Assistant Investment Tracker Card

A reusable Home Assistant Lovelace card for tracking stocks and ETFs with Home Assistant market-data entities.

![HACS validation](https://github.com/louisjferreira/ha-investment-tracker-card/actions/workflows/hacs.yml/badge.svg)

## Backend-enabled build

The card separates security identification from market data:

- **OpenFIGI** is used server-side by the companion Home Assistant backend to resolve an ISIN to security metadata.
- **Yahoo Finance** remains the market-data source through the existing `iprak/yahoofinance` Home Assistant integration.
- The browser never calls OpenFIGI or Yahoo Finance directly, avoiding the CORS failure seen with browser-side API calls.
- Yahoo Finance data is refreshed automatically once per day at a configurable time.
- The card provides a manual **Refresh** button with a persistent daily quota; the default is 3 manual refreshes per day.

OpenFIGI's v3 mapping API supports `ID_ISIN` mappings and has a free unauthenticated rate limit, with higher limits available using an API key. urlOpenFIGI API documentationhttps://www.openfigi.com/api/documentation

## Current features

- Portfolio invested amount, current value and lifetime gain percentage
- Portfolio-level daily movement with multi-currency conversion
- Portfolio allocation percentage per holding
- Configurable holdings with shares/units and invested amount
- Selectable portfolio display currency
- Selectable holding currency
- Foreign-currency holdings with an optional FX-rate entity
- ISIN as the primary security identifier
- Server-side ISIN security lookup in the visual card editor
- Selection of a returned security to populate its name, ticker and exchange
- Expandable holding rows
- Current price, average purchase price, invested amount and current value detail metrics
- Historical charts using Home Assistant Recorder history
- Interactive chart hover values
- Chart periods: 1D, 1W, 1M, 3M, 6M, 1Y, 5Y and MAX
- Responsive desktop/mobile layout
- Home Assistant theme-aware styling
- Graceful handling when price or FX data is unavailable
- Manual market-data refresh with a daily limit

## Backend installation for testing

The backend is currently included in this repository under `custom_components/investment_tracker/` so it can be tested before we split it into a dedicated HACS integration repository.

For a test installation, copy that directory to:

```text
/config/custom_components/investment_tracker/
```

Then add the following to `configuration.yaml`:

```yaml
investment_tracker:
  daily_refresh_time: "23:15:00"
  manual_refresh_limit: 3
  # Optional:
  # openfigi_api_key: "YOUR_OPENFIGI_API_KEY"
```

The default example time is deliberately after the US market close for a Home Assistant instance in Zimbabwe. Change it if your portfolio is dominated by another market.

Restart Home Assistant after adding the integration.

The backend calls the existing Yahoo Finance integration's `yahoofinance.refresh_symbols` service for both the scheduled and manual refresh. The manual counter is stored in Home Assistant storage, so reloading the dashboard does not reset the quota.

See `examples/investment-tracker-backend.yaml` for the same configuration.

## Configuration

Each holding should use its ISIN as the primary identifier. The ticker/symbol is retained because the market-data provider generally needs a provider-specific symbol or instrument identifier to supply prices.

**Important:** `invested` is entered in the holding's own `currency`. The card converts it into `display_currency` using `fx_rate_entity` when required.

```yaml
type: custom:investment-tracker-card
title: My Investments
display_currency: GBP
holdings:
  - isin: US22788C1053
    symbol: CRWD
    name: CrowdStrike
    exchange: NASDAQ
    shares: 8
    invested: 1007.96
    currency: USD
    price_entity: sensor.yahoofinance_crwd
    fx_rate_entity: sensor.usd_gbp

  - isin: US69608A1088
    symbol: PLTR
    name: Palantir
    exchange: NYSE
    shares: 7
    invested: 971.70
    currency: USD
    price_entity: sensor.yahoofinance_pltr
    fx_rate_entity: sensor.usd_gbp

  - isin: US0231351067
    symbol: AMZN
    name: Amazon
    exchange: NASDAQ
    shares: 4
    invested: 889.76
    currency: USD
    price_entity: sensor.yahoofinance_amzn
    fx_rate_entity: sensor.usd_gbp

  - isin: IE00B3Y8X563
    symbol: CSP1
    name: iShares S&P 500 GBP Hedged UCITS ETF
    shares: 7
    invested: 975.31
    currency: GBP
    price_entity: sensor.sp500_etf_price
```

### Visual ISIN lookup

In the Home Assistant card editor, enter the 12-character ISIN and select **Search ISIN**. The editor sends the request through the Home Assistant backend, which queries OpenFIGI. The browser therefore does not contact the external security-master API.

The lookup may return more than one listing for an ISIN. Select the listing that matches the security and market you actually own. Currency remains an explicit user selection because the market-data layer is provider-agnostic.

### Manual refresh

The card's **Refresh** button requests a backend refresh of the configured Yahoo Finance symbols. The button shows the remaining daily quota, for example `↻ Refresh 2/3`.

The backend enforces the quota and persists the counter. Automatic daily refreshes do **not** consume the manual quota. The limit is configured in the backend's `manual_refresh_limit` setting, not in the card YAML.

### Currency conversion

`display_currency` controls the portfolio total and other portfolio-level monetary figures. Each holding has its own `currency` setting. For a foreign-currency holding, `fx_rate_entity` should represent the value of **1 unit of the holding currency in the portfolio currency**. For example, a USD holding in a GBP portfolio needs a sensor representing USD → GBP.

### Market data

The card deliberately separates the UI from the market-data provider. The intended first-party test setup uses the `iprak/yahoofinance` Home Assistant integration, but any provider that creates numeric Home Assistant price and FX sensors can be used.

### Daily portfolio movement

The portfolio **Today** figure uses Home Assistant Recorder history for each holding's price entity and, where required, its FX entity. The card compares the current position value with the earliest available value in the trailing 24-hour Recorder window. If complete historical data is not available for every holding, the card shows `Today · —` rather than presenting a misleading partial result.

### Charts

When a holding is expanded, the card requests historical values for its `price_entity` from Home Assistant Recorder. The chart is therefore independent of the market-data provider. MAX requests history from 2000 onward.

## Market-data examples

See `examples/market-data-sensors.yaml` for provider-agnostic examples of price and FX entity wiring.

## Validation

The repository includes GitHub Actions for JavaScript syntax validation, custom-integration validation and HACS plugin validation. Release builds bundle the backend-enabled card into the single JavaScript asset expected by HACS.

## Status

Backend-enabled test build — OpenFIGI ISIN resolution, daily Yahoo Finance refresh and rate-limited manual refresh are implemented on the feature branch and ready for Home Assistant testing.
