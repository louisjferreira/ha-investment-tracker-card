# Home Assistant Investment Tracker Card

A reusable Home Assistant Lovelace card for tracking stocks and ETFs with live Home Assistant price entities.

## Current development build

The card currently supports:

- Portfolio invested amount, current value and gain percentage
- Portfolio allocation percentage per holding
- Configurable holdings with shares/units and invested amount
- Selectable portfolio display currency
- Selectable holding currency
- Foreign-currency holdings with an optional FX-rate entity
- ISIN as the primary security identifier
- ISIN security lookup in the visual card editor using the OpenFIGI security master
- Selection of a returned security to populate its name, ticker and exchange
- Expandable holding rows
- Current price, average purchase price, invested amount and current value detail metrics
- Historical charts using Home Assistant Recorder history
- Interactive chart hover values
- Chart periods: 1D, 1W, 1M, 3M, 6M, 1Y, 5Y and MAX
- Responsive desktop/mobile layout
- Home Assistant theme-aware styling
- Graceful handling when price or FX data is unavailable

## Configuration

Each holding should use its ISIN as the primary identifier. The ticker/symbol is retained because a market-data provider generally needs a provider-specific symbol or instrument identifier to supply prices.

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
    invested: 747.30
    currency: USD
    price_entity: sensor.crowdstrike_price
    fx_rate_entity: sensor.usd_gbp

  - isin: US69608A1088
    symbol: PLTR
    name: Palantir
    shares: 7
    invested: 720.43
    currency: USD
    price_entity: sensor.palantir_price
    fx_rate_entity: sensor.usd_gbp

  - isin: US0231351067
    symbol: AMZN
    name: Amazon
    exchange: NASDAQ
    shares: 4
    invested: 659.67
    currency: USD
    price_entity: sensor.amazon_price
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

When using the Home Assistant card editor, enter the 12-character ISIN and select **Search ISIN**. The editor queries OpenFIGI's public security-mapping endpoint and presents matching instruments. Selecting a result fills in the security name, ticker and exchange while retaining the ISIN as the primary identifier.

The lookup may return more than one instrument for an ISIN. Select the listing that matches the security and market you actually own. Currency remains an explicit user selection because the market-data layer is provider-agnostic and a security can have multiple listing/currency considerations.

### Currency conversion

`display_currency` controls the portfolio total and other portfolio-level monetary figures. Each holding has its own `currency` setting. For a foreign-currency holding, `fx_rate_entity` should represent the value of **1 unit of the holding currency in the portfolio currency**. For example, a USD holding in a GBP portfolio needs a sensor representing USD → GBP.

### Market data

The card deliberately separates the UI from the market-data provider. Users can use Yahoo Finance, another Home Assistant integration, REST sensors, or any other source that creates numeric Home Assistant price and FX sensors.

### Charts

When a holding is expanded, the card requests historical values for its `price_entity` from Home Assistant Recorder. The chart is therefore independent of the market-data provider. The provider only needs to keep the price sensor updated. The card handles missing or insufficient history without breaking the holding view.

## Planned next steps

- Improve chart scaling and add clearer time-axis context
- Add daily portfolio movement and daily change indicators
- Add ready-made market-data sensor examples
- Add provider-specific instrument mapping where appropriate
- Support transaction history and partial buys/sells
- Add optional watchlist/trading sections
- Add AI portfolio/event summaries and alerts
- Prepare a tagged HACS release

## Status

Early development — **do not install as a production card yet**.
