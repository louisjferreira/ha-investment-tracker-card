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
      const result = await this._hass.connection.sendMessagePromise({ type: 'investment_tracker/lookup_isin', isin });
      this._search[index] = { results: (result.results || []).slice(0, 10) };
      if (!this._search[index].results.length) throw new Error('No security was found for that ISIN.');
    } catch (err) {
      console.warn('Investment Tracker Card ISIN lookup error', err);
      this._search[index] = { error: err?.message || 'ISIN lookup failed. Install and configure the Investment Tracker backend integration.' };
    }
    this.render();
  }'''

MARKET_PATCH = '''
const _itOriginalSetConfig = InvestmentTrackerCard.prototype.setConfig;
const _itOriginalHassSetter = Object.getOwnPropertyDescriptor(InvestmentTrackerCard.prototype, 'hass').set;
InvestmentTrackerCard.prototype.setConfig = function(config) {
  this._marketData = {};
  this._marketErrors = {};
  this._marketLoading = false;
  this._lastMarketRequestSignature = '';
  this._refreshStatus = null;
  this._refreshLoading = false;
  this._refreshError = null;
  this._statusRequested = false;
  _itOriginalSetConfig.call(this, config);
};
InvestmentTrackerCard.prototype.price = function(item) {
  const data = this._marketData?.[this.id(item)];
  if (data && Number.isFinite(Number(data.price))) return Number(data.price);
  if (!item?.price_entity || !this._hass) return null;
  const value = Number.parseFloat(this._hass.states[item.price_entity]?.state);
  return Number.isFinite(value) ? value : null;
};
InvestmentTrackerCard.prototype.fx = function(item) {
  const source = item.currency || this.config.display_currency;
  if (source === this.config.display_currency) return 1;
  const data = this._marketData?.[this.id(item)];
  if (data && Number.isFinite(Number(data.fx)) && Number(data.fx) > 0) return Number(data.fx);
  if (!item.fx_rate_entity || !this._hass) return null;
  const value = Number.parseFloat(this._hass.states[item.fx_rate_entity]?.state);
  return Number.isFinite(value) && value > 0 ? value : null;
};
InvestmentTrackerCard.prototype.refreshMarkup = function() {
  if (this._refreshLoading) return '<button class="refresh" disabled>↻ Refreshing…</button>';
  if (!this._refreshStatus) return '<button class="refresh" type="button">↻ Refresh</button>';
  const remaining = Number(this._refreshStatus.manual_refresh_remaining) || 0;
  const limit = Number(this._refreshStatus.manual_refresh_limit) || 0;
  if (!limit) return '<button class="refresh" disabled>↻ Refresh disabled</button>';
  return `<button class="refresh" type="button" ${remaining <= 0 ? 'disabled' : ''}>↻ Refresh <span>${remaining}/${limit}</span></button>`;
};
InvestmentTrackerCard.prototype.loadRefreshStatus = async function() {
  if (!this._hass?.connection) return;
  try { this._refreshStatus = await this._hass.connection.sendMessagePromise({ type: 'investment_tracker/refresh_status' }); this._refreshError = null; }
  catch (err) { this._refreshError = 'Backend integration not installed/configured.'; }
  this.render();
};
InvestmentTrackerCard.prototype.manualRefresh = async function() {
  if (!this._hass?.connection || this._refreshLoading) return;
  const remaining = Number(this._refreshStatus?.manual_refresh_remaining);
  if (Number.isFinite(remaining) && remaining <= 0) return;
  this._refreshLoading = true; this._refreshError = null; this.render();
  try {
    this._refreshStatus = await this._hass.connection.sendMessagePromise({ type: 'investment_tracker/refresh' });
    this._lastMarketRequestSignature = '';
    await this.loadMarketData(true);
  } catch (err) { this._refreshError = err?.message || 'Market data refresh failed.'; }
  finally { this._refreshLoading = false; this.render(); }
};
InvestmentTrackerCard.prototype.loadMarketData = async function(force = false) {
  if (!this._hass?.connection || !this.config?.holdings?.length) return;
  const holdings = this.config.holdings.filter(item => item.symbol && !item.price_entity);
  if (!holdings.length) return;
  const signature = holdings.map(item => `${this.id(item)}:${item.symbol}:${item.currency || this.config.display_currency}`).join(';');
  if (!force && signature === this._lastMarketRequestSignature) return;
  this._lastMarketRequestSignature = signature;
  this._marketLoading = true;
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
      } catch (err) { this._marketErrors[id] = err?.message || 'Market data unavailable.'; }
    }));
  } finally { this._marketLoading = false; this.render(); }
};
InvestmentTrackerCard.prototype.loadHistory = async function(item, period) {
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
      const end = new Date(); const start = new Date(end);
      if (period === 'MAX') start.setFullYear(2000, 0, 1); else start.setDate(start.getDate() - (PERIOD_DAYS[period] || 31));
      const result = await this._hass.callWS({ type: 'history/history_during_period', start_time: start.toISOString(), end_time: end.toISOString(), entity_ids: [item.price_entity], minimal_response: true, no_attributes: true, significant_changes_only: false });
      const states = Array.isArray(result) ? (result[0] || []) : (result?.[item.price_entity] || []);
      this._history[id] = { ...(this._history[id] || {}), [period]: states.map(s => ({ time: new Date(s.last_changed || s.last_updated).getTime(), value: Number.parseFloat(s.state) })).filter(x => Number.isFinite(x.time) && Number.isFinite(x.value)) };
    }
  } catch (err) {
    console.warn('Investment Tracker Card history error', err);
    this._history[id] = { ...(this._history[id] || {}), [period]: [] };
  }
  this._loading[id] = { ...(this._loading[id] || {}), [period]: false };
  this.render();
};
Object.defineProperty(InvestmentTrackerCard.prototype, 'hass', {
  configurable: true,
  get() { return this._hass; },
  set(hass) {
    _itOriginalHassSetter.call(this, hass);
    if (!this._statusRequested) { this._statusRequested = true; this.loadRefreshStatus(); }
    this.loadMarketData();
  },
});
'''


def main() -> None:
    source = subprocess.check_output(["git", "show", f"{BASE_COMMIT}:{SOURCE}"], text=True)
    source = source.replace(
        "this._portfolioDay = null; this._portfolioDayLoading = false; this._lastHassSignature = ''; this.render();",
        "this._portfolioDay = null; this._portfolioDayLoading = false; this._lastHassSignature = ''; this._refreshStatus = null; this._refreshLoading = false; this._refreshError = null; this._statusRequested = false; this.render();",
        1,
    )
    source = source.replace(
        "<div class=\"header-value\"><div class=\"total\">${missing ? '—' : this.money(total.current)}</div><div class=\"${this.gainClass(gain)} lifetime-gain\">${missing ? 'Waiting for price / FX data' : `${this.signedMoney(gain)} · ${this.signedPercent(pct)} lifetime`}</div>${this.portfolioDayMarkup()}</div>",
        "<div class=\"header-actions\"><div class=\"header-value\"><div class=\"total\">${missing ? '—' : this.money(total.current)}</div><div class=\"${this.gainClass(gain)} lifetime-gain\">${missing ? 'Waiting for price / FX data' : `${this.signedMoney(gain)} · ${this.signedPercent(pct)} lifetime`}</div>${this.portfolioDayMarkup()}</div>${this.refreshMarkup()}</div>",
        1,
    )
    source = source.replace("</div></ha-card>`; this.bind();", "</div><div class=\"refresh-error\">${this._refreshError ? this.escape(this._refreshError) : ''}</div></ha-card>`; this.bind();", 1)
    source = source.replace("  bind() { this.shadowRoot.querySelectorAll('.summary')", "  bind() { this.shadowRoot.querySelector('.refresh')?.addEventListener('click', event => { event.stopPropagation(); this.manualRefresh(); }); this.shadowRoot.querySelectorAll('.summary')", 1)
    source = source.replace("  styles() { return `:host{display:block}", "  styles() { return `:host{display:block}.header-actions{display:flex;align-items:center;gap:12px}.refresh{border:1px solid var(--divider-color);border-radius:9px;padding:8px 10px;background:var(--secondary-background-color);color:var(--primary-text-color);cursor:pointer;font-size:11px;font-weight:650;white-space:nowrap}.refresh:hover:not(:disabled){background:var(--primary-color);color:var(--text-primary-color,#fff)}.refresh:disabled{opacity:.55;cursor:not-allowed}.refresh span{display:block;font-size:9px;font-weight:500;margin-top:2px}.refresh-error{font-size:11px;color:var(--error-color);margin-bottom:5px}", 1)
    start = source.index(SEARCH_MARKER)
    end = source.index(SEARCH_END, start)
    source = source[:start] + SEARCH_REPLACEMENT + source[end:]
    source = source.replace("customElements.define('investment-tracker-card', InvestmentTrackerCard);", MARKET_PATCH + "\ncustomElements.define('investment-tracker-card', InvestmentTrackerCard);", 1)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(source, encoding="utf-8")


if __name__ == "__main__":
    main()
