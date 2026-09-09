"""Build the HACS JavaScript asset from the stable card source plus backend features."""

from __future__ import annotations

import subprocess
from pathlib import Path

BASE_COMMIT = "d89ccdafba119c82a5317b194629175c64407ae3"
SOURCE = "ha-investment-tracker-card.js"
OUTPUT = Path("dist/ha-investment-tracker-card.js")

SEARCH_MARKER = "  async searchIsin(index) {"
SEARCH_END = "\n  selectResult("

SEARCH_REPLACEMENT = '''  async searchIsin(index) {
    const isin = String(this.config.holdings[index]?.isin || '').trim().toUpperCase();
    if (!/^[A-Z]{2}[A-Z0-9]{9}[0-9]$/.test(isin)) {
      this._search[index] = { error: 'Enter a valid 12-character ISIN before searching.' };
      this.render();
      return;
    }
    this._search[index] = { loading: true };
    this.render();
    try {
      const result = await this._hass.connection.sendMessagePromise({
        type: 'investment_tracker/lookup_isin',
        isin,
      });
      this._search[index] = { results: (result.results || []).slice(0, 10) };
      if (!this._search[index].results.length) throw new Error('No security was found for that ISIN.');
    } catch (err) {
      console.warn('Investment Tracker Card ISIN lookup error', err);
      this._search[index] = {
        error: err?.message || 'ISIN lookup failed. Install and configure the Investment Tracker backend integration.',
      };
    }
    this.render();
  }'''

REFRESH_METHODS = '''  refreshMarkup() {
    if (this._refreshLoading) return '<button class="refresh" disabled>↻ Refreshing…</button>';
    if (!this._refreshStatus) return '<button class="refresh" type="button">↻ Refresh</button>';
    const remaining = Number(this._refreshStatus.manual_refresh_remaining) || 0;
    const limit = Number(this._refreshStatus.manual_refresh_limit) || 0;
    if (!limit) return '<button class="refresh" disabled>↻ Refresh disabled</button>';
    return `<button class="refresh" type="button" ${remaining <= 0 ? 'disabled' : ''}>↻ Refresh <span>${remaining}/${limit}</span></button>`;
  }
  async loadRefreshStatus() {
    if (!this._hass?.connection) return;
    try {
      this._refreshStatus = await this._hass.connection.sendMessagePromise({ type: 'investment_tracker/refresh_status' });
      this._refreshError = null;
    } catch (err) {
      this._refreshError = 'Backend integration not installed/configured.';
    }
    this.render();
  }
  async manualRefresh() {
    if (!this._hass?.connection || this._refreshLoading) return;
    const remaining = Number(this._refreshStatus?.manual_refresh_remaining);
    if (Number.isFinite(remaining) && remaining <= 0) return;
    this._refreshLoading = true;
    this._refreshError = null;
    this.render();
    try {
      this._refreshStatus = await this._hass.connection.sendMessagePromise({ type: 'investment_tracker/refresh' });
      this._lastMarketRequestSignature = '';
      await this.loadMarketData(true);
    } catch (err) {
      this._refreshError = err?.message || 'Market data refresh failed.';
    } finally {
      this._refreshLoading = false;
      this.render();
    }
  }
  async loadMarketData(force = false) {
    if (!this._hass?.connection || !this.config?.holdings?.length) return;
    const holdings = this.config.holdings.filter(item => item.symbol && !item.price_entity);
    if (!holdings.length && !force) return;
    const signature = holdings.map(item => `${this.id(item)}:${item.symbol}:${item.currency || this.config.display_currency}`).join(';');
    if (!force && signature === this._lastMarketRequestSignature) return;
    this._lastMarketRequestSignature = signature;
    this._marketLoading = true;
    this.render();
    try {
      await Promise.all(holdings.map(async item => {
        const id = this.id(item);
        try {
          this._marketData[id] = await this._hass.connection.sendMessagePromise({
            type: 'investment_tracker/market_data',
            symbol: item.symbol,
            source_currency: item.currency || this.config.display_currency,
            display_currency: this.config.display_currency,
            force,
          });
          this._marketErrors[id] = null;
        } catch (err) {
          this._marketErrors[id] = err?.message || 'Market data unavailable.';
        }
      }));
    } finally {
      this._marketLoading = false;
      this.render();
      this.loadPortfolioDay();
    }
  }
'''

PORTFOLIO_METHOD = '''  async loadPortfolioDay() {
    if (!this._hass || this._portfolioDayLoading || !this.config?.holdings?.length) return;
    this._portfolioDayLoading = true;
    this.render();
    try {
      const end = new Date(), start = new Date(end);
      start.setDate(start.getDate() - 1);
      const historyForEntity = async entityId => {
        const result = await this._hass.callWS({ type: 'history/history_during_period', start_time: start.toISOString(), end_time: end.toISOString(), entity_ids: [entityId], minimal_response: true, no_attributes: true, significant_changes_only: false });
        const states = Array.isArray(result) ? (result[0] || []) : (result?.[entityId] || []);
        return states.map(s => ({ time: new Date(s.last_changed || s.last_updated).getTime(), value: Number.parseFloat(s.state) })).filter(x => Number.isFinite(x.time) && Number.isFinite(x.value)).sort((a, b) => a.time - b.time);
      };
      const historyForMarket = async symbol => {
        const result = await this._hass.connection.sendMessagePromise({ type: 'investment_tracker/market_history', symbol, period: '1D' });
        return (result.points || []).map(x => ({ time: Number(x.time), value: Number(x.value) })).filter(x => Number.isFinite(x.time) && Number.isFinite(x.value)).sort((a, b) => a.time - b.time);
      };
      let currentValue = 0, previousValue = 0;
      for (const item of this.config.holdings) {
        const p = this.position(item);
        if (p.current === null) throw new Error('Missing current market data');
        const priceHistory = item.price_entity ? await historyForEntity(item.price_entity) : await historyForMarket(item.symbol);
        const priorPrice = priceHistory.length ? priceHistory[0].value : null;
        const sourceCurrency = item.currency || this.config.display_currency;
        let priorFx = 1;
        if (sourceCurrency !== this.config.display_currency) {
          const fxHistory = item.fx_rate_entity
            ? await historyForEntity(item.fx_rate_entity)
            : await historyForMarket(`${sourceCurrency}${this.config.display_currency}=X`);
          priorFx = fxHistory.length ? fxHistory[0].value : null;
        }
        if (priorPrice === null || priorFx === null || !Number.isFinite(priorFx) || priorFx <= 0) throw new Error('Missing prior market data');
        currentValue += p.current;
        previousValue += p.shares * priorPrice * priorFx;
      }
      if (previousValue !== 0) {
        const change = currentValue - previousValue;
        this._portfolioDay = { change, pct: change / previousValue * 100 };
      } else this._portfolioDay = null;
    } catch (err) {
      console.warn('Investment Tracker Card portfolio day history error', err);
      this._portfolioDay = null;
    } finally {
      this._portfolioDayLoading = false;
      this.render();
    }
  }
'''

HISTORY_MARKER = "  async loadHistory(item, period) {"
HISTORY_END = "\n  styles() {"

HISTORY_METHOD = '''  async loadHistory(item, period) {
    if (!this._hass || !item) return;
    const id = this.id(item);
    if (this._history[id]?.[period]?.length) return;
    this._loading[id] = { ...(this._loading[id] || {}), [period]: true };
    this.render();
    try {
      if (!item.price_entity) {
        const result = await this._hass.connection.sendMessagePromise({ type: 'investment_tracker/market_history', symbol: item.symbol, period });
        this._history[id] = { ...(this._history[id] || {}), [period]: result.points || [] };
      } else {
        const end = new Date(), start = new Date(end);
        if (period === 'MAX') start.setFullYear(2000, 0, 1); else start.setDate(start.getDate() - (PERIOD_DAYS[period] || 31));
        const result = await this._hass.callWS({ type: 'history/history_during_period', start_time: start.toISOString(), end_time: end.toISOString(), entity_ids: [item.price_entity], minimal_response: true, no_attributes: true, significant_changes_only: false });
        const states = Array.isArray(result) ? (result[0] || []) : (result?.[item.price_entity] || []);
        const points = states.map(s => ({ time: new Date(s.last_changed || s.last_updated).getTime(), value: Number.parseFloat(s.state) })).filter(x => Number.isFinite(x.time) && Number.isFinite(x.value));
        this._history[id] = { ...(this._history[id] || {}), [period]: points };
      }
    } catch (err) {
      console.warn('Investment Tracker Card history error', err);
      this._history[id] = { ...(this._history[id] || {}), [period]: [] };
    }
    this._loading[id] = { ...(this._loading[id] || {}), [period]: false };
    this.render();
  }
'''


def main() -> None:
    source = subprocess.check_output(["git", "show", f"{BASE_COMMIT}:{SOURCE}"], text=True)

    source = source.replace(
        "this._portfolioDay = null; this._portfolioDayLoading = false; this._lastHassSignature = ''; this.render();",
        "this._portfolioDay = null; this._portfolioDayLoading = false; this._lastHassSignature = ''; this._lastMarketRequestSignature = ''; this._marketData = {}; this._marketErrors = {}; this._marketLoading = false; this._refreshStatus = null; this._refreshLoading = false; this._refreshError = null; this._statusRequested = false; this.render();",
        1,
    )
    source = source.replace(
        "this._hass = hass; if (!this.config) return;",
        "this._hass = hass; if (!this.config) return; if (!this._statusRequested) { this._statusRequested = true; this.loadRefreshStatus(); } this.loadMarketData();",
        1,
    )
    source = source.replace(
        "price(item) { if (!item?.price_entity || !this._hass) return null; const value = Number.parseFloat(this._hass.states[item.price_entity]?.state); return Number.isFinite(value) ? value : null; }",
        "price(item) { const data = this._marketData?.[this.id(item)]; if (data && Number.isFinite(Number(data.price))) return Number(data.price); if (!item?.price_entity || !this._hass) return null; const value = Number.parseFloat(this._hass.states[item.price_entity]?.state); return Number.isFinite(value) ? value : null; }",
        1,
    )
    source = source.replace(
        "fx(item) { const source = item.currency || this.config.display_currency; if (source === this.config.display_currency) return 1; if (!item.fx_rate_entity || !this._hass) return null; const value = Number.parseFloat(this._hass.states[item.fx_rate_entity]?.state); return Number.isFinite(value) && value > 0 ? value : null; }",
        "fx(item) { const source = item.currency || this.config.display_currency; if (source === this.config.display_currency) return 1; const data = this._marketData?.[this.id(item)]; if (data && Number.isFinite(Number(data.fx)) && Number(data.fx) > 0) return Number(data.fx); if (!item.fx_rate_entity || !this._hass) return null; const value = Number.parseFloat(this._hass.states[item.fx_rate_entity]?.state); return Number.isFinite(value) && value > 0 ? value : null; }",
        1,
    )
    source = source.replace(
        "<div class=\"header-value\"><div class=\"total\">${missing ? '—' : this.money(total.current)}</div><div class=\"${this.gainClass(gain)} lifetime-gain\">${missing ? 'Waiting for price / FX data' : `${this.signedMoney(gain)} · ${this.signedPercent(pct)} lifetime`}</div>${this.portfolioDayMarkup()}</div>",
        "<div class=\"header-actions\"><div class=\"header-value\"><div class=\"total\">${missing ? '—' : this.money(total.current)}</div><div class=\"${this.gainClass(gain)} lifetime-gain\">${missing ? 'Waiting for price / FX data' : `${this.signedMoney(gain)} · ${this.signedPercent(pct)} lifetime`}</div>${this.portfolioDayMarkup()}</div>${this.refreshMarkup()}</div>",
        1,
    )
    source = source.replace(
        "</div></ha-card>`; this.bind();",
        "</div><div class=\"refresh-error\">${this._refreshError ? this.escape(this._refreshError) : ''}</div></ha-card>`; this.bind();",
        1,
    )
    source = source.replace("  async loadPortfolioDay() {", REFRESH_METHODS + PORTFOLIO_METHOD, 1)
    source = source.replace(HISTORY_MARKER, HISTORY_METHOD, 1)
    source = source.replace(HISTORY_METHOD + "\n  styles() {", HISTORY_METHOD + "\n  styles() {", 1)
    start = source.index(SEARCH_MARKER)
    end = source.index(SEARCH_END, start)
    source = source[:start] + SEARCH_REPLACEMENT + source[end:]
    source = source.replace(
        "  bind() { this.shadowRoot.querySelectorAll('.summary')",
        "  bind() { this.shadowRoot.querySelector('.refresh')?.addEventListener('click', event => { event.stopPropagation(); this.manualRefresh(); }); this.shadowRoot.querySelectorAll('.summary')",
        1,
    )
    source = source.replace(
        "  styles() { return `:host{display:block}",
        "  styles() { return `:host{display:block}.header-actions{display:flex;align-items:center;gap:12px}.refresh{border:1px solid var(--divider-color);border-radius:9px;padding:8px 10px;background:var(--secondary-background-color);color:var(--primary-text-color);cursor:pointer;font-size:11px;font-weight:650;white-space:nowrap}.refresh:hover:not(:disabled){background:var(--primary-color);color:var(--text-primary-color,#fff)}.refresh:disabled{opacity:.55;cursor:not-allowed}.refresh span{display:block;font-size:9px;font-weight:500;margin-top:2px}.refresh-error{font-size:11px;color:var(--error-color);margin-bottom:5px}",
        1,
    )
    source = source.replace(
        '<div class="label">Price entity</div><input data-key="price_entity" value="${this.escape(h.price_entity || \'\')}" placeholder="sensor.apple_price">',
        '<div class="label">Price entity (optional override)</div><input data-key="price_entity" value="${this.escape(h.price_entity || \'')}" placeholder="Leave blank for automatic market data">',
        1,
    )
    source = source.replace(
        '<div class="label">FX rate entity (source currency → portfolio currency)</div><input data-key="fx_rate_entity" value="${this.escape(h.fx_rate_entity || \'\')}" placeholder="sensor.usd_gbp">',
        '<div class="label">FX rate entity (optional override)</div><input data-key="fx_rate_entity" value="${this.escape(h.fx_rate_entity || \'')}" placeholder="Leave blank for automatic FX data">',
        1,
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(source, encoding="utf-8")


if __name__ == "__main__":
    main()
