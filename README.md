# Home Assistant Investment Tracker Card

A reusable Home Assistant Lovelace card for tracking stocks and ETFs with live Home Assistant price entities.

## Current development build

The card currently supports:

- Portfolio invested amount, current value and gain percentage
- Configurable holdings with shares/units and invested amount
- GBP as the default portfolio currency
- Foreign-currency holdings with an optional FX-rate entity
- Expandable holding rows
- Historical charts using Home Assistant Recorder history
- Chart periods: 1D, 1W, 1M, 3M, 6M, 1Y, 5Y and MAX
- Responsive desktop/mobile layout
- Home Assistant theme-aware styling

## Configuration

Each holding needs a Home Assistant entity containing the current market price. The card deliberately separates the UI from the market-data provider, so users can use Yahoo Finance, another integration, REST sensors, or any other source that creates a numeric Home Assistant sensor.

```yaml
type: custom:investment-tracker-card
title: My Investments
display_currency: GBP
holdings:
  - symbol: CRWD
    name: CrowdStrike
    shares: 8
    invested: 747.30
    currency: USD
    price_entity: sensor.crowdstrike_price
    fx_rate_entity: sensor.usd_gbp

  - symbol: PLTR
    name: Palantir
    shares: 7
    invested: 720.43
    currency: USD
    price_entity: sensor.palantir_price
    fx_rate_entity: sensor.usd_gbp

  - symbol: AMZN
    name: Amazon
    shares: 4
    invested: 659.67
    currency: USD
    price_entity: sensor.amazon_price
    fx_rate_entity: sensor.usd_gbp

  - symbol: CSP1
    name: S&P 500 ETF
    shares: 7
    invested: 975.31
    currency: GBP
    price_entity: sensor.sp500_etf_price
```

### Currency conversion

For a foreign-currency holding, `fx_rate_entity` should represent the value of **1 unit of the holding currency in the portfolio currency**. For example, a USD holding in a GBP portfolio needs a sensor representing USD → GBP.

### Charts

When a holding is expanded, the card requests historical values for its `price_entity` from Home Assistant Recorder. This means the chart works independently of the market-data provider. The provider only needs to keep the price sensor updated.

## Planned next steps

- Add a polished production UI
- Improve chart rendering and tooltips
- Add market-data provider guidance and ready-made sensor examples
- Support transaction history and partial buys/sells
- Add allocation percentages and daily change
- Add optional watchlist/trading sections
- Prepare a tagged HACS release

## Status

Early development — **do not install as a production card yet**.
