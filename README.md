# Home Assistant Investment Tracker Card

A reusable Home Assistant Lovelace card for tracking stocks and ETFs with Home Assistant market-data entities.

![HACS validation](https://github.com/louisjferreira/ha-investment-tracker-card/actions/workflows/hacs.yml/badge.svg)

## Installation — read this first

The Investment Tracker Card has **two parts** in the current V0.2.x test architecture:

1. **The Lovelace card** — installed through HACS.
2. **The Home Assistant backend** — currently copied manually into `custom_components`. This backend is required for ISIN lookup and the card's Refresh button.

> **Important:** HACS currently installs the frontend card only. It does **not** install the Python backend automatically. Follow **Step 2** below even if HACS reports that the card installed successfully.

### Step 1 — Install the card with HACS

In Home Assistant:

1. Open **HACS**.
2. Go to **Frontend**.
3. Search for **Investment Tracker Card**.
4. Install the latest release.
5. Restart Home Assistant or reload the browser resources when HACS requests it.

The card type is:

```yaml
type: custom:investment-tracker-card
```

### Step 2 — Install the Home Assistant backend

The backend is included in this repository under:

```text
custom_components/investment_tracker/
```

Copy the **entire `investment_tracker` directory** into your Home Assistant configuration directory so that the final path is:

```text
/config/custom_components/investment_tracker/
```

Your folder structure should look like this:

```text
/config/
├── configuration.yaml
└── custom_components/
    └── investment_tracker/
        ├── __init__.py
        └── manifest.json
        ...
```

Do **not** copy the Python files directly into `/config/custom_components/`. The `investment_tracker` folder must remain intact.

You can copy the folder using Studio Code Server, File editor, Samba, Terminal & SSH, or another method you normally use to manage your Home Assistant files.

### Step 3 — Configure the backend

Add this to your Home Assistant `configuration.yaml`:

```yaml
investment_tracker:
  daily_refresh_time: "23:15:00"
  manual_refresh_limit: 3
  # Optional:
  # openfigi_api_key: "YOUR_OPENFIGI_API_KEY"
```

Then **restart Home Assistant**.

#### Configuration options

- `daily_refresh_time` — local Home Assistant time for the automatic daily market-data refresh. The example `23:15:00` is suitable for a Zimbabwe-based installation because it is after the US market close in both US daylight and standard time. Change it if your portfolio is dominated by another market.
- `manual_refresh_limit` — maximum number of manual refreshes allowed per day. The default is `3`.
- `openfigi_api_key` — optional OpenFIGI API key. OpenFIGI works without a key, but a key provides a higher mapping rate limit.

The manual refresh counter is stored in Home Assistant storage, so refreshing the dashboard or restarting the browser does not reset the daily quota.

### Step 4 — Make sure market data is available

The backend uses the existing **Yahoo Finance Home Assistant integration** for market-data refreshes. Install/configure the `iprak/yahoofinance` Home Assistant integration if you do not already have it.

The Investment Tracker Card does not directly contact Yahoo Finance from the browser. Instead, the backend calls Home Assistant's:

```text
yahoofinance.refresh_symbols
```

service.

Your configured Yahoo Finance entities provide the numeric price data used by the card. FX entities can be supplied in the same way for holdings whose currency differs from the portfolio display currency.

### Step 5 — Add the card

Once the frontend card and backend are installed, add the card to a dashboard using the visual editor or YAML.

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
    price_entity: sensor.yahoofinance_crwd
    fx_rate_entity: sensor.usd_gbp
```

For a foreign-currency holding, `fx_rate_entity` should represent the value of **1 unit of the holding currency in the portfolio currency**. For example, a USD holding in a GBP portfolio needs a sensor representing USD → GBP.

### Step 6 — Test ISIN lookup

Open the card's visual editor and enter the 12-character ISIN.

Click **Search ISIN**.

The request follows this path:

```text
Card editor
    ↓
Home Assistant backend
    ↓
OpenFIGI
    ↓
Security metadata / ticker / exchange
    ↓
Card editor
```

The browser does **not** contact OpenFIGI directly. This avoids the browser CORS problem that affected earlier versions of the card.

The lookup can return multiple listings for the same security. Select the listing matching the security and market you actually own.

> **Currency is still selected by the user.** OpenFIGI identifies the security but does not provide the currency used by this card's market-data configuration, so do not assume the lookup has selected the correct portfolio/holding currency for you.

### Step 7 — Test Refresh

The card's **Refresh** button requests a refresh of the configured Yahoo Finance symbols through Home Assistant.

The button displays the remaining manual quota, for example:

```text
↻ Refresh 2/3
```

Automatic daily refreshes do **not** consume the manual quota.

To test the limit, press Refresh successfully three times. The fourth manual request should be refused until the daily quota resets.

## Backend-enabled architecture

The card separates security identification from market data:

- **OpenFIGI** is used server-side by the companion Home Assistant backend to resolve an ISIN to security metadata.
- **Yahoo Finance** remains the market-data source through the existing `iprak/yahoofinance` Home Assistant integration.
- The browser never calls OpenFIGI or Yahoo Finance directly.
- Yahoo Finance data is refreshed automatically once per day at a configurable time.
- The card provides a manual **Refresh** button with a persistent daily quota.

OpenFIGI's v3 mapping API supports `ID_ISIN` mappings and has a free unauthenticated rate limit, with higher limits available using an API key. See the [OpenFIGI API documentation](https://www.openfigi.com/api/documentation).

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

## Visual ISIN lookup

In the Home Assistant card editor, enter the 12-character ISIN and select **Search ISIN**. The editor sends the request through the Home Assistant backend, which queries OpenFIGI. The browser therefore does not contact the external security-master API.

The lookup may return more than one listing for an ISIN. Select the listing that matches the security and market you actually own. Currency remains an explicit user selection because the market-data layer is provider-agnostic.

## Manual refresh

The card's **Refresh** button requests a backend refresh of the configured Yahoo Finance symbols. The button shows the remaining daily quota, for example `↻ Refresh 2/3`.

The backend enforces the quota and persists the counter. Automatic daily refreshes do **not** consume the manual quota. The limit is configured in the backend's `manual_refresh_limit` setting, not in the card YAML.

## Currency conversion

`display_currency` controls the portfolio total and other portfolio-level monetary figures. Each holding has its own `currency` setting. For a foreign-currency holding, `fx_rate_entity` should represent the value of **1 unit of the holding currency in the portfolio currency**.

## Market data

The card deliberately separates the UI from the market-data provider. The intended first-party test setup uses the `iprak/yahoofinance` Home Assistant integration, but any provider that creates numeric Home Assistant price and FX sensors can be used for the card's calculations and charts.

## Daily portfolio movement

The portfolio **Today** figure uses Home Assistant Recorder history for each holding's price entity and, where required, its FX entity. The card compares the current position value with the earliest available value in the trailing 24-hour Recorder window. If complete historical data is not available for every holding, the card shows `Today · —` rather than presenting a misleading partial result.

## Charts

When a holding is expanded, the card requests historical values for its `price_entity` from Home Assistant Recorder. The chart is therefore independent of the market-data provider. MAX requests history from 2000 onward.

## Market-data examples

See `examples/market-data-sensors.yaml` for provider-agnostic examples of price and FX entity wiring.

See `examples/investment-tracker-backend.yaml` for the backend configuration example.

## Validation and releases

The repository includes GitHub Actions for JavaScript syntax validation, custom-integration validation and HACS plugin validation. Release builds bundle the backend-enabled card into the single JavaScript asset expected by HACS.

## Status

**V0.2.x backend-enabled test release.** The public HACS card, Home Assistant backend, OpenFIGI ISIN resolution, daily Yahoo Finance refresh and rate-limited manual refresh are implemented. The backend is currently manually installed because the repository is still distributed by HACS as a frontend/plugin repository. A future release may move the backend into a dedicated HACS integration repository so that the entire installation can become one-click.
