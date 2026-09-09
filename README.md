# Home Assistant Investment Tracker Card

![Investment Tracker Card](assets/example-card.svg)

A polished Home Assistant Lovelace card for tracking stocks and ETFs with automatic market data, multi-currency support, ISIN identification and historical performance charts.

![HACS validation](https://github.com/louisjferreira/ha-investment-tracker-card/actions/workflows/hacs.yml/badge.svg)

## Features

- 📈 Portfolio invested amount, current value and lifetime gain
- 💱 Multi-currency portfolio calculations with automatic FX conversion
- 💹 Automatic current price and market data
- 🔎 ISIN-based security identification and listing selection
- 📊 Historical charts from 1D through MAX
- 🔄 Rate-limited manual refresh with persistent daily quota
- ⏰ Automatic daily market-data refresh
- 🏠 Responsive Home Assistant theme-aware UI
- 🧩 HACS distribution
- 🛠️ Optional legacy Home Assistant price/FX entity overrides

## See it in action

### Portfolio view

![Investment Tracker portfolio example](assets/example-card.svg)

### Key capabilities

![Investment Tracker features](assets/example-features.svg)

The card is designed to keep the important information visible at a glance while allowing each holding to be expanded for more detail.

## Installation

The project currently has two parts:

1. **Lovelace card** — installed through HACS.
2. **Home Assistant backend** — copied into `custom_components/investment_tracker/` because this repository is distributed by HACS as a frontend repository.

Install the latest card release through HACS, then copy the complete `custom_components/investment_tracker/` directory from this repository to:

```text
/config/custom_components/investment_tracker/
```

Add the backend configuration to `configuration.yaml`:

```yaml
investment_tracker:
  daily_refresh_time: "23:15:00"
  manual_refresh_limit: 3
  # Optional:
  # openfigi_api_key: "YOUR_OPENFIGI_API_KEY"
```

Restart Home Assistant after installing or updating the backend.

## Automatic market data

The card no longer requires a separate Yahoo Finance Home Assistant sensor for every holding.

When a holding has an ISIN and a provider symbol, the Investment Tracker backend can fetch current market data directly and return it to the card. The existing Yahoo Finance integration used for Devere holdings can remain completely unchanged.

The normal flow is:

```text
ISIN
  ↓
OpenFIGI security lookup
  ↓
Ticker / listing selected
  ↓
Investment Tracker backend
  ↓
Yahoo Finance market data
  ↓
Price + FX returned directly to the card
```

There is therefore **no need to add `CRWD`, `PLTR`, `AMZN`, etc. to the separate `yahoofinance:` YAML configuration just to use this card**.

The card still accepts `price_entity` and `fx_rate_entity` as optional overrides, so existing configurations remain usable.

## Backend configuration

- `daily_refresh_time` — local Home Assistant time used for the automatic cache refresh. Default: `23:15:00`.
- `manual_refresh_limit` — maximum manual refresh requests per day. Default: `3`.
- `openfigi_api_key` — optional OpenFIGI API key for higher mapping limits.

The manual quota is persisted in Home Assistant storage and automatic refreshes do not consume it.

## Add the card

Example:

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
```

Notice that there is **no `price_entity` and no `fx_rate_entity`** in the example. Those are optional overrides; the backend supplies the market data automatically.

For a legacy/provider-specific setup they can still be supplied:

```yaml
price_entity: sensor.yahoofinance_crwd
fx_rate_entity: sensor.usd_gbp
```

## ISIN lookup

Enter the 12-character ISIN in the visual editor and choose **Search ISIN**. The browser sends the request to the Home Assistant backend, which queries OpenFIGI server-side.

OpenFIGI may return multiple listings for the same security. Select the listing matching the security and market you actually own. Currency remains an explicit holding setting.

## Market-data provider

The backend currently uses Yahoo Finance's public chart market-data endpoint server-side. It does **not** depend on the `iprak/yahoofinance` Home Assistant integration for new Investment Tracker holdings.

This is intentional: the card's market-data interface is provider-agnostic, while the current backend provider is Yahoo Finance. A future provider can be added behind the same interface without changing the card configuration.

The backend caches current data briefly to avoid unnecessary requests. Manual refresh invalidates the cache and is subject to the daily quota. Automatic refresh does not consume the manual quota.

## Currency conversion

`display_currency` controls the portfolio currency. Each holding has its own `currency`.

For automatic market data, the backend requests the corresponding Yahoo Finance FX pair when the holding currency differs from the portfolio currency. For example, a USD holding in a GBP portfolio uses the USD → GBP FX rate automatically.

For legacy entity-based configurations, `fx_rate_entity` should represent the value of **1 unit of the holding currency in the portfolio currency**.

## Historical charts

When automatic market data is used, historical chart data is also fetched by the Investment Tracker backend. The supported periods are:

- 1D
- 1W
- 1M
- 3M
- 6M
- 1Y
- 5Y
- MAX

Legacy entity-based holdings continue to use Home Assistant Recorder history.

## Manual refresh

The card's **Refresh** button shows the remaining daily manual quota, for example:

```text
↻ Refresh 2/3
```

The backend persists the counter. Automatic daily refreshes do not consume the manual quota.

## Branding

The project includes Home Assistant local brand assets under `custom_components/investment_tracker/brand/` so the backend integration can use the same Investment Tracker identity inside Home Assistant.

The repository also includes a reusable logo and icon for project documentation and distribution.

## Validation

GitHub Actions validate:

- JavaScript syntax and the generated release asset
- Home Assistant custom-integration compatibility
- HACS repository requirements

## Current release

**V0.3.3** is the current stable release.

V0.3.3 includes the direct market-data backend fixes for multi-currency portfolios, including correct FX handling and safer Yahoo ticker fallback behaviour.
