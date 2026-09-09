# Home Assistant Investment Tracker Card

![Investment Tracker Card](assets/example-card.svg)

A polished Home Assistant Lovelace card for tracking **stocks and ETFs** with automatic market data, multi-currency support, ISIN identification and historical performance charts.

![HACS validation](https://github.com/louisjferreira/ha-investment-tracker-card/actions/workflows/hacs.yml/badge.svg)

## Features

- 📈 Portfolio invested amount, current value and lifetime gain
- 💱 Multi-currency portfolios with automatic FX conversion
- 💹 Automatic current prices and market data
- 🔎 ISIN-based security identification and listing selection
- 📊 Historical performance charts from 1D through MAX
- 🔄 Rate-limited manual refresh with a persistent daily quota
- ⏰ Automatic daily market-data refresh
- 🏠 Responsive, Home Assistant theme-aware UI
- 🧩 HACS distribution
- 🛠️ Optional legacy Home Assistant price and FX entity overrides

## See it in action

### Portfolio view

![Investment Tracker portfolio example](assets/example-card.svg)

### Key capabilities

![Investment Tracker features](assets/example-features.svg)

The card keeps the important portfolio information visible at a glance while allowing individual holdings to be expanded for more detail.

## Installation

The project has two components:

1. **Lovelace card** — installed through HACS.
2. **Home Assistant backend** — installed manually in `custom_components/investment_tracker/`.

### 1. Install the card through HACS

Install the latest **Investment Tracker Card** release through HACS.

### 2. Install the backend

Copy the complete `custom_components/investment_tracker/` directory from this repository to:

```text
/config/custom_components/investment_tracker/
```

Then add the backend configuration to `configuration.yaml`:

```yaml
investment_tracker:
  daily_refresh_time: "23:15:00"
  manual_refresh_limit: 3
  # Optional:
  # openfigi_api_key: "YOUR_OPENFIGI_API_KEY"
```

Restart Home Assistant after installing or updating the backend.

> **Important:** The Investment Tracker Card does **not** require the `iprak/yahoofinance` Home Assistant integration. Market data is retrieved directly by the Investment Tracker backend. If you already use `iprak/yahoofinance` for other Home Assistant entities, it can remain installed independently.

## Automatic market data

The card can retrieve current prices, FX rates and historical market data without requiring a separate Home Assistant market-data sensor for each holding.

For holdings with an ISIN and provider symbol, the Investment Tracker backend handles the market-data lookup server-side.

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
Price + FX + history returned to the card
```

There is therefore **no need to add `CRWD`, `PLTR`, `AMZN`, etc. to a separate `yahoofinance:` YAML configuration just to use this card**.

The card still supports `price_entity` and `fx_rate_entity` as optional overrides, so existing or legacy configurations remain usable.

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

Notice that there is **no `price_entity` and no `fx_rate_entity`** in this example. The backend supplies the market data automatically.

### Legacy entity-based configuration

If you prefer to use existing Home Assistant entities, or already have a provider-specific setup, the card can still use them:

```yaml
price_entity: sensor.yahoofinance_crwd
fx_rate_entity: sensor.usd_gbp
```

These entity overrides are optional and are not required for the normal automatic market-data flow.

## ISIN lookup

Enter the 12-character ISIN in the visual editor and choose **Search ISIN**.

The browser sends the request to the Home Assistant backend, which queries OpenFIGI server-side. OpenFIGI may return multiple listings for the same security, so select the listing that matches the security and market you actually own.

The holding currency remains an explicit setting. It is not automatically changed simply because a different exchange listing is selected.

## Market data

The Investment Tracker backend currently uses Yahoo Finance's public chart market-data endpoint directly from Home Assistant.

The card itself is **provider-agnostic**. Yahoo Finance is the current backend provider, but the market-data interface is designed so another provider could be added later without changing the card configuration.

The backend briefly caches current market data to avoid unnecessary requests. Manual refresh invalidates the cache and uses the configured daily manual-refresh quota. Automatic daily refreshes do not consume the manual quota.

## Currency conversion

`display_currency` controls the currency used for the portfolio totals and values shown by the card.

Each holding has its own `currency` setting. When automatic market data is used, the backend obtains the required FX rate whenever the holding currency differs from the portfolio currency.

For example, a USD holding in a GBP portfolio uses the USD → GBP exchange rate automatically.

For legacy entity-based configurations, `fx_rate_entity` should represent the value of **1 unit of the holding currency in the portfolio currency**.

## Historical charts

When automatic market data is used, historical chart data is fetched by the Investment Tracker backend.

Supported periods are:

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

The card's **Refresh** button shows the remaining daily manual-refresh quota, for example:

```text
↻ Refresh 2/3
```

The backend persists the counter in Home Assistant storage. Automatic daily refreshes do not consume the manual quota.

## Backend configuration

| Option | Description | Default |
|---|---|---|
| `daily_refresh_time` | Local Home Assistant time for the automatic market-data refresh | `23:15:00` |
| `manual_refresh_limit` | Maximum manual refresh requests per day | `3` |
| `openfigi_api_key` | Optional OpenFIGI API key for higher mapping limits | Not set |

## Branding

The project includes dedicated Investment Tracker branding for Home Assistant and project documentation, including local brand assets under:

```text
custom_components/investment_tracker/brand/
```

A reusable project logo and icon are also included in the repository.

## Validation

GitHub Actions validate:

- JavaScript syntax and the generated release asset
- Home Assistant custom-integration compatibility
- HACS repository requirements

## Current release

**V0.3.3** is the current stable release.

V0.3.3 includes the direct market-data backend fixes for multi-currency portfolios, including correct FX handling and safer Yahoo Finance ticker fallback behaviour.
