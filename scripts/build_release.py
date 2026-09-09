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
      this._lastHassSignature = '';
    } catch (err) {
      this._refreshError = err?.message || 'Market data refresh failed.';
    } finally {
      this._refreshLoading = false;
      this.render();
    }
  }
'''


def main() -> None:
    source = subprocess.check_output(
        ["git", "show", f"{BASE_COMMIT}:{SOURCE}"], text=True
    )

    source = source.replace(
        "this._portfolioDay = null; this._portfolioDayLoading = false; this._lastHassSignature = ''; this.render();",
        "this._portfolioDay = null; this._portfolioDayLoading = false; this._lastHassSignature = ''; this._refreshStatus = null; this._refreshLoading = false; this._refreshError = null; this._statusRequested = false; this.render();",
        1,
    )
    source = source.replace(
        "this._hass = hass; if (!this.config) return;",
        "this._hass = hass; if (!this.config) return; if (!this._statusRequested) { this._statusRequested = true; this.loadRefreshStatus(); }",
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
    source = source.replace(
        "  async loadPortfolioDay() {",
        REFRESH_METHODS + "  async loadPortfolioDay() {",
        1,
    )
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

    start = source.index(SEARCH_MARKER)
    end = source.index(SEARCH_END, start)
    source = source[:start] + SEARCH_REPLACEMENT + source[end:]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(source, encoding="utf-8")


if __name__ == "__main__":
    main()
