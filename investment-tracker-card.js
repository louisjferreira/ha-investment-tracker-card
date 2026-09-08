class InvestmentTrackerCard extends HTMLElement {
  setConfig(config) {
    if (!config || !Array.isArray(config.holdings)) {
      throw new Error('Please provide a holdings array.');
    }
    this.config = config;
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this.config) this.render();
  }

  getCardSize() {
    return 4;
  }

  render() {
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });

    const holdings = this.config.holdings || [];
    const rows = holdings.map((holding) => `
      <div class="holding" data-symbol="${this.escape(holding.symbol)}">
        <div class="summary">
          <div>
            <div class="name">${this.escape(holding.name || holding.symbol)}</div>
            <div class="meta">${this.escape(String(holding.shares ?? 0))} shares · Invested ${this.money(holding.invested, holding.currency || 'GBP')}</div>
          </div>
          <div class="value">—</div>
          <div class="gain">—</div>
          <button type="button" aria-label="Show chart for ${this.escape(holding.name || holding.symbol)}">⌄</button>
        </div>
        <div class="chart-panel" hidden>
          <div class="periods">
            ${['1D','1W','1M','3M','6M','1Y','5Y','MAX'].map((p) => `<button type="button" data-period="${p}">${p}</button>`).join('')}
          </div>
          <div class="chart-placeholder">Market data will appear here.</div>
        </div>
      </div>
    `).join('');

    this.shadowRoot.innerHTML = `
      <style>
        :host { display:block; }
        .card { padding: 16px; border-radius: 16px; background: var(--ha-card-background, var(--card-background-color, #fff)); color: var(--primary-text-color); box-shadow: var(--ha-card-box-shadow, none); }
        .header { display:flex; justify-content:space-between; align-items:end; margin-bottom:14px; }
        .title { font-size:18px; font-weight:600; }
        .total { font-size:24px; font-weight:700; text-align:right; }
        .sub { color:var(--secondary-text-color); font-size:12px; text-align:right; }
        .holding { border-top:1px solid var(--divider-color); padding:10px 0; }
        .summary { display:grid; grid-template-columns:minmax(0,1fr) auto auto 32px; gap:12px; align-items:center; }
        .name { font-weight:600; }
        .meta { color:var(--secondary-text-color); font-size:12px; margin-top:3px; }
        .value { font-weight:600; }
        .gain { font-weight:600; }
        button { border:0; background:transparent; color:var(--primary-text-color); cursor:pointer; min-width:32px; min-height:32px; border-radius:8px; }
        button:hover { background:var(--secondary-background-color); }
        .chart-panel { padding:10px 0 4px; }
        .periods { display:flex; gap:4px; flex-wrap:wrap; margin-bottom:10px; }
        .periods button { color:var(--secondary-text-color); font-size:12px; }
        .chart-placeholder { height:140px; display:grid; place-items:center; color:var(--secondary-text-color); background:var(--secondary-background-color); border-radius:10px; }
        @media (max-width:600px) { .summary { grid-template-columns:minmax(0,1fr) auto 32px; } .gain { display:none; } }
      </style>
      <ha-card class="card">
        <div class="header">
          <div class="title">Investment Tracker</div>
          <div><div class="total">—</div><div class="sub">Portfolio value</div></div>
        </div>
        <div class="holdings">${rows}</div>
      </ha-card>
    `;

    this.shadowRoot.querySelectorAll('.holding > .summary > button').forEach((button) => {
      button.addEventListener('click', () => {
        const panel = button.closest('.holding').querySelector('.chart-panel');
        panel.hidden = !panel.hidden;
        button.textContent = panel.hidden ? '⌄' : '⌃';
      });
    });
  }

  money(value, currency) {
    const number = Number(value);
    if (!Number.isFinite(number)) return '—';
    return new Intl.NumberFormat(undefined, { style:'currency', currency }).format(number);
  }

  escape(value) {
    return String(value).replace(/[&<>"']/g, (c) => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
  }
}

customElements.define('investment-tracker-card', InvestmentTrackerCard);
