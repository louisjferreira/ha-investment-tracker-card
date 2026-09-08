# Home Assistant Investment Tracker Card

A reusable Home Assistant Lovelace card for tracking stocks and ETFs with live market-price integrations.

## Planned features

- Portfolio total, invested amount, current value and gain percentage
- Configurable holdings with shares/units and invested amount
- GBP and foreign-currency holdings with FX conversion
- Expandable holding rows
- Per-holding price charts
- Chart periods: 1D, 1W, 1M, 3M, 6M, 1Y, 5Y and MAX
- Easy add/remove/update of holdings
- Home Assistant theme-aware UI
- HACS distribution
- Market-data-provider agnostic architecture

## Example configuration

```yaml
type: custom:investment-tracker-card
holdings:
  - symbol: CRWD
    name: CrowdStrike
    shares: 8
    invested: 747.30
    currency: USD
  - symbol: PLTR
    name: Palantir
    shares: 7
    invested: 720.43
    currency: USD
  - symbol: AMZN
    name: Amazon
    shares: 4
    invested: 659.67
    currency: USD
  - symbol: CSP1
    name: S&P 500 ETF
    shares: 7
    invested: 975.31
    currency: GBP
```

> The market-data connection will be configured separately from the card so users are not locked to a single provider.

## Status

Early development.
