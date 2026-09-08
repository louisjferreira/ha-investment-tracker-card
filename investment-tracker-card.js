const CURRENCIES = [
  ['GBP', '£', 'British Pound'],
  ['USD', '$', 'US Dollar'],
  ['EUR', '€', 'Euro'],
  ['ZAR', 'R', 'South African Rand'],
  ['AUD', 'A$', 'Australian Dollar'],
  ['CAD', 'C$', 'Canadian Dollar'],
  ['CHF', 'CHF', 'Swiss Franc'],
  ['JPY', '¥', 'Japanese Yen'],
  ['NZD', 'NZ$', 'New Zealand Dollar'],
  ['SGD', 'S$', 'Singapore Dollar'],
  ['HKD', 'HK$', 'Hong Kong Dollar'],
  ['SEK', 'kr', 'Swedish Krona'],
  ['NOK', 'kr', 'Norwegian Krone'],
  ['DKK', 'kr', 'Danish Krone'],
];

const PERIODS = ['1D', '1W', '1M', '3M', '6M', '1Y', '5Y', 'MAX'];

class InvestmentTrackerCard extends HTMLElement {
  setConfig(config) {
    if (!config || !Array.isArray(config.holdings)) {
      throw new Error('Investment Tracker Card requires a holdings array.');
    }
    this.config = { title: 'Investment Tracker', display_currency: 'GBP', ...config };
    this._expanded = null;
    this._periods = {};
    this._history = {};
    this._loading = {};
    this.render();
  }

  static getConfigElement() { return document.createElement('investment-tracker-card-editor'); }
  static getStubConfig() { return { title: 'Investment Tracker', display_currency: 'GBP', holdings: [] }; }

  set hass(hass) {
    this._hass = hass;
    if (this.config) this.render();
  }

  getCardSize() { return Math.max(4, 3 + (this.config?.holdings?.length || 0) * 2); }

  id(item) { return String(item.isin || item.id || item.symbol || item.name); }

  price(item) {
    if (!item?.price_entity || !this._hass) return null;
    const value = Number.parseFloat(this._hass.states[item.price_entity]?.state);
    return Number.isFinite(value) ? value : null;
  }

  fx(item) {
    const source = item.currency || this.config.display_currency;
    if (source === this.config.display_currency) return 1;
    if (!item.fx_rate_entity || !this._hass) return null;
    const value = Number.parseFloat(this._hass.states[item.fx_rate_entity]?.state);
    return Number.isFinite(value) && value > 0 ? value : null;
  }

  position(item) {
    const shares = Number(item.shares) || 0;
    const invested = Number(item.invested) || 0;
    const price = this.price(item);
    const fx = this.fx(item);
    const investedDisplay = fx === null ? null : invested * fx;
    const current = price === null || fx === null ? null : shares * price * fx;
    const gain = current === null || investedDisplay === null ? null : current - investedDisplay;
    const gainPct = gain === null || !investedDisplay ? null : gain / investedDisplay * 100;
    return { shares, invested, investedDisplay, price, fx, current, gain, gainPct };
  }

  totals() {
    return this.config.holdings.reduce((out, item) => {
      const p = this.position(item);
      if (p.investedDisplay === null) out.missing += 1; else out.invested += p.investedDisplay;
      if (p.current === null) out.missing += 1; else out.current += p.current;
      return out;
    }, { invested: 0, current: 0, missing: 0 });
  }

  render() {
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
    const total = this.totals();
    const gain = total.current - total.invested;
    const pct = total.invested ? gain / total.invested * 100 : null;
    this.shadowRoot.innerHTML = `<style>${this.styles()}</style><ha-card class="card">
      <div class="header"><div><div class="title">${this.escape(this.config.title)}</div><div class="caption">${this.config.holdings.length} holdings · ${this.escape(this.config.display_currency)}</div></div>
      <div class="header-value"><div class="total">${total.missing ? '—' : this.money(total.current)}</div><div class="${this.gainClass(gain)}">${total.missing ? 'Waiting for price / FX data' : `${this.signedMoney(gain)} · ${this.signedPercent(pct)}`}</div></div></div>
      <div class="holdings">${this.config.holdings.map((item) => this.renderHolding(item)).join('')}</div>
    </ha-card>`;
    this.bind();
  }

  renderHolding(item) {
    const id = this.id(item);
    const p = this.position(item);
    const open = this._expanded === id;
    return `<div class="holding" data-id="${this.escape(id)}">
      <button class="summary" type="button" aria-expanded="${open}">
        <span class="identity"><span class="name">${this.escape(item.name || item.symbol || item.isin)}</span><span class="meta">${this.number(p.shares)} shares · Invested ${p.investedDisplay === null ? '—' : this.money(p.investedDisplay)}${item.isin ? ` · ${this.escape(item.isin)}` : ''}</span></span>
        <span class="current"><span class="current-value">${p.current === null ? '—' : this.money(p.current)}</span><span class="source">Value in ${this.escape(this.config.display_currency)}</span></span>
        <span class="position-gain ${this.gainClass(p.gain)}">${this.signedPercent(p.gainPct)}</span><span class="chevron">${open ? '⌃' : '⌄'}</span>
      </button>${open ? this.renderDetail(item, p) : ''}
    </div>`;
  }

  renderDetail(item, p) {
    const id = this.id(item);
    const period = this._periods[id] || '1M';
    const history = this._history[id]?.[period] || [];
    const loading = this._loading[id]?.[period];
    return `<div class="detail"><div class="detail-top">
      <div><div class="detail-value">${p.price === null ? '—' : this.money(p.price, item.currency || this.config.display_currency)}</div><div class="detail-label">Current price · ${this.escape(item.currency || this.config.display_currency)}</div></div>
      <div class="detail-stat"><span>Invested</span><strong>${p.investedDisplay === null ? '—' : this.money(p.investedDisplay)}</strong></div><div class="detail-stat"><span>Value</span><strong>${p.current === null ? '—' : this.money(p.current)}</strong></div>
    </div><div class="periods">${PERIODS.map((x) => `<button class="period ${x === period ? 'selected' : ''}" data-period="${x}" type="button">${x}</button>`).join('')}</div>
    <div class="chart">${loading ? '<div class="chart-message">Loading history…</div>' : this.chart(history, item)}</div></div>`;
  }

  chart(history, item) {
    const values = history.map((x) => x.value).filter(Number.isFinite);
    if (values.length < 2) return '<div class="chart-message">Historical data is not available yet.</div>';
    const w = 760, h = 220, pad = 12, min = Math.min(...values), max = Math.max(...values), range = max - min || 1;
    const points = history.map((x, i) => `${(pad + i / (history.length - 1) * (w - pad * 2)).toFixed(1)},${(h - pad - (x.value - min) / range * (h - pad * 2)).toFixed(1)}`).join(' ');
    const change = values[0] ? (values.at(-1) - values[0]) / values[0] * 100 : null;
    return `<div class="chart-head"><span>${this.money(values.at(-1), item.currency || this.config.display_currency)}</span><span class="${this.gainClass(change)}">${this.signedPercent(change)} over period</span></div><svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><polyline points="${points}" fill="none" stroke="var(--primary-color)" stroke-width="3" vector-effect="non-scaling-stroke" stroke-linecap="round" stroke-linejoin="round" /></svg>`;
  }

  bind() {
    this.shadowRoot.querySelectorAll('.summary').forEach((button) => button.addEventListener('click', () => {
      const id = button.closest('.holding').dataset.id;
      this._expanded = this._expanded === id ? null : id;
      this.render();
      if (this._expanded) {
        const item = this.config.holdings.find((x) => this.id(x) === id);
        this.loadHistory(item, this._periods[id] || '1M');
      }
    }));
    this.shadowRoot.querySelectorAll('.period').forEach((button) => button.addEventListener('click', () => {
      const id = button.closest('.holding').dataset.id;
      const period = button.dataset.period;
      this._periods[id] = period;
      const item = this.config.holdings.find((x) => this.id(x) === id);
      this.loadHistory(item, period);
    }));
  }

  async loadHistory(item, period) {
    if (!this._hass || !item?.price_entity) return;
    const id = this.id(item);
    this._loading[id] = { ...(this._loading[id] || {}), [period]: true };
    this.render();
    const end = new Date();
    const start = new Date(end);
    const days = { '1D':1, '1W':7, '1M':31, '3M':93, '6M':186, '1Y':366, '5Y':1826, 'MAX':3650 }[period] || 31;
    start.setDate(start.getDate() - days);
    try {
      const result = await this._hass.callWS({ type:'history/history_during_period', start_time:start.toISOString(), end_time:end.toISOString(), entity_ids:[item.price_entity], minimal_response:true, no_attributes:true, significant_changes_only:false });
      const states = Array.isArray(result) ? (result[0] || []) : [];
      const points = states.map((s) => ({ time:new Date(s.last_changed || s.last_updated).getTime(), value:Number.parseFloat(s.state) })).filter((x) => Number.isFinite(x.time) && Number.isFinite(x.value));
      this._history[id] = { ...(this._history[id] || {}), [period]:points };
    } catch (err) {
      console.warn('Investment Tracker Card history error', err);
      this._history[id] = { ...(this._history[id] || {}), [period]:[] };
    }
    this._loading[id] = { ...(this._loading[id] || {}), [period]: false };
    this.render();
  }

  styles() { return `
    :host{display:block}.card{overflow:hidden;padding:0 16px;border-radius:16px;background:var(--ha-card-background,var(--card-background-color,#fff));color:var(--primary-text-color);box-shadow:var(--ha-card-box-shadow,none)}
    .header{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:18px 0 14px}.title{font-size:18px;font-weight:700}.caption,.meta,.source,.detail-label,.detail-stat span{color:var(--secondary-text-color)}.caption{font-size:12px;margin-top:3px}.header-value{text-align:right}.total{font-size:24px;font-weight:750;line-height:1.1}.positive{color:var(--success-color,#2e7d32)}.negative{color:var(--error-color,#c62828)}.neutral{color:var(--secondary-text-color)}
    .holding{border-top:1px solid var(--divider-color)}.summary{width:100%;display:grid;grid-template-columns:minmax(0,1fr) auto auto 28px;gap:14px;align-items:center;padding:12px 0;border:0;background:transparent;color:inherit;text-align:left;cursor:pointer}.summary:hover{background:var(--secondary-background-color)}.identity{min-width:0;display:flex;flex-direction:column;gap:3px}.name{font-weight:650;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.meta{font-size:12px}.current{display:flex;flex-direction:column;align-items:flex-end;gap:2px}.current-value{font-weight:650;white-space:nowrap}.source{font-size:10px}.position-gain{min-width:66px;text-align:right;font-size:13px;font-weight:650}.chevron{text-align:center;font-size:18px;color:var(--secondary-text-color)}
    .detail{padding:4px 0 16px}.detail-top{display:flex;gap:28px;align-items:end;padding:4px 0 12px}.detail-value{font-size:20px;font-weight:700}.detail-label,.detail-stat span{display:block;font-size:11px;margin-top:3px}.detail-stat strong{display:block;font-size:13px;margin-top:3px}.periods{display:flex;gap:4px;flex-wrap:wrap;margin-bottom:10px}.period{border:0;border-radius:7px;padding:5px 8px;background:transparent;color:var(--secondary-text-color);cursor:pointer;font-size:11px;font-weight:650}.period:hover,.period.selected{background:var(--secondary-background-color);color:var(--primary-text-color)}.chart{min-height:160px;border-radius:10px;background:var(--secondary-background-color);overflow:hidden}.chart svg{display:block;width:100%;height:180px}.chart-head{display:flex;justify-content:space-between;padding:9px 10px 0;font-size:12px;font-weight:600}.chart-message{height:180px;display:grid;place-items:center;color:var(--secondary-text-color);font-size:12px}
    @media(max-width:600px){.summary{grid-template-columns:minmax(0,1fr) auto 28px}.position-gain{display:none}.detail-top{gap:16px}}
  `; }

  number(value) { return new Intl.NumberFormat(undefined,{maximumFractionDigits:4}).format(Number(value)||0); }
  money(value,currency=this.config.display_currency){ const n=Number(value); return Number.isFinite(n)?new Intl.NumberFormat(undefined,{style:'currency',currency,maximumFractionDigits:2}).format(n):'—'; }
  signedMoney(value,currency=this.config.display_currency){ const n=Number(value); return Number.isFinite(n)?`${n>=0?'+':''}${this.money(n,currency)}`:'—'; }
  signedPercent(value){ const n=Number(value); return Number.isFinite(n)?`${n>=0?'+':''}${n.toFixed(2)}%`:'—'; }
  gainClass(value){ const n=Number(value); return Number.isFinite(n)?n>0?'positive':n<0?'negative':'neutral':'neutral'; }
  escape(value){ return String(value).replace(/[&<>"']/g,(c)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
}

class InvestmentTrackerCardEditor extends HTMLElement {
  setConfig(config) {
    this.config = { title:'Investment Tracker', display_currency:'GBP', holdings:[], ...config };
    this._search = {};
    this.render();
  }

  set hass(hass) { this._hass = hass; }

  render() {
    if (!this.shadowRoot) this.attachShadow({mode:'open'});
    this.shadowRoot.innerHTML = `<style>${this.styles()}</style><div class="wrap">
      <div class="field"><div class="label">Card title</div><input id="title" value="${this.escape(this.config.title)}"></div>
      <div class="field"><div class="label">Portfolio display currency</div><select id="display_currency">${this.currencyOptions(this.config.display_currency)}</select></div>
      <div id="holdings">${this.config.holdings.map((h,i)=>this.holding(h,i)).join('')}</div>
      <div class="actions"><button id="add" type="button">Add holding</button></div>
      <div class="hint">Search an ISIN to identify the security. Select the returned instrument, then choose its trading currency. Market-price and FX entities remain configurable so the card stays provider-agnostic.</div>
    </div>`;
    this.bind();
  }

  styles() { return `
    .wrap{display:flex;flex-direction:column;gap:14px;padding:8px 0}.field{display:flex;flex-direction:column;gap:5px}.label{font-size:12px;color:var(--secondary-text-color)}input,select{box-sizing:border-box;width:100%;padding:9px;border:1px solid var(--divider-color);border-radius:8px;background:var(--card-background-color);color:var(--primary-text-color);font:inherit}.holding{border:1px solid var(--divider-color);border-radius:10px;padding:12px;display:flex;flex-direction:column;gap:10px}.holding-head{display:flex;justify-content:space-between;align-items:center;font-weight:650}.remove{border:0;background:transparent;color:var(--error-color);cursor:pointer}.actions{display:flex;gap:8px}.actions button,.search-button{border:0;border-radius:8px;padding:8px 12px;background:var(--primary-color);color:var(--text-primary-color,#fff);cursor:pointer}.search-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px}.search-button{white-space:nowrap}.search-status{font-size:11px;color:var(--secondary-text-color)}.results{display:flex;flex-direction:column;gap:5px}.result{width:100%;text-align:left;border:1px solid var(--divider-color);border-radius:8px;padding:8px;background:transparent;color:inherit;cursor:pointer}.result:hover{background:var(--secondary-background-color)}.result strong{display:block;font-size:12px}.result span{display:block;font-size:11px;color:var(--secondary-text-color);margin-top:2px}.hint{font-size:11px;color:var(--secondary-text-color);line-height:1.4}
    @media(max-width:600px){.search-row{grid-template-columns:1fr}.search-button{width:100%}}
  `; }

  currencyOptions(selected) { return CURRENCIES.map(([code,symbol,name]) => `<option value="${code}" ${code===selected?'selected':''}>${symbol} ${code} — ${name}</option>`).join(''); }

  holding(h,i) {
    const currency = h.currency || this.config.display_currency;
    const search = this._search[i] || {};
    const results = (search.results || []).map((r,index)=>`<button class="result" type="button" data-result-index="${index}"><strong>${this.escape(r.name || 'Unknown security')}</strong><span>${this.escape(r.ticker || 'No ticker')} · ${this.escape(r.exchangeCode || r.exchCode || 'Exchange unknown')} · ${this.escape(r.securityType || r.marketSector || 'Security')}</span></button>`).join('');
    return `<div class="holding" data-index="${i}"><div class="holding-head"><span>Holding ${i+1}</span><button class="remove" data-action="remove" type="button">Remove</button></div>
      <div class="field"><div class="label">ISIN (primary security ID)</div><div class="search-row"><input data-key="isin" value="${this.escape(h.isin||'')}" placeholder="e.g. US0378331005"><button class="search-button" data-action="search" type="button">Search ISIN</button></div>${search.loading?'<div class="search-status">Searching security master…</div>':''}${search.error?`<div class="search-status">${this.escape(search.error)}</div>`:''}${results?`<div class="results">${results}</div>`:''}</div>
      <div class="field"><div class="label">Name</div><input data-key="name" value="${this.escape(h.name||'')}" placeholder="Apple Inc."></div>
      <div class="field"><div class="label">Ticker / symbol</div><input data-key="symbol" value="${this.escape(h.symbol||'')}" placeholder="AAPL"></div>
      <div class="field"><div class="label">Exchange</div><input data-key="exchange" value="${this.escape(h.exchange||'')}" placeholder="NASDAQ"></div>
      <div class="field"><div class="label">Currency</div><select data-key="currency">${this.currencyOptions(currency)}</select></div>
      <div class="field"><div class="label">Shares / units</div><input data-key="shares" type="number" step="any" value="${this.escape(h.shares??0)}"></div>
      <div class="field"><div class="label">Invested amount (${this.escape(currency)})</div><input data-key="invested" type="number" step="0.01" value="${this.escape(h.invested??0)}"></div>
      <div class="field"><div class="label">Price entity</div><input data-key="price_entity" value="${this.escape(h.price_entity||'')}" placeholder="sensor.apple_price"></div>
      <div class="field"><div class="label">FX rate entity (source currency → portfolio currency)</div><input data-key="fx_rate_entity" value="${this.escape(h.fx_rate_entity||'')}" placeholder="sensor.usd_gbp"></div>
    </div>`;
  }

  bind() {
    this.shadowRoot.querySelector('#title').addEventListener('input', (e)=>this.commit({title:e.target.value}));
    this.shadowRoot.querySelector('#display_currency').addEventListener('change', (e)=>this.commit({display_currency:e.target.value}));
    this.shadowRoot.querySelector('#add').addEventListener('click', ()=>this.commit({holdings:[...this.config.holdings,{isin:'',name:'',symbol:'',exchange:'',currency:this.config.display_currency,shares:0,invested:0,price_entity:'',fx_rate_entity:''}]}));
    this.shadowRoot.querySelectorAll('.holding').forEach((row)=>{
      const i=Number(row.dataset.index);
      row.querySelectorAll('[data-key]').forEach((el)=>el.addEventListener(el.tagName==='SELECT'?'change':'input',()=>{
        const holdings=this.config.holdings.map((h,idx)=>idx===i?{...h,[el.dataset.key]:this.parseValue(el.dataset.key,el.value)}:h);
        this.commit({holdings});
      }));
      row.querySelector('[data-action="remove"]').addEventListener('click',()=>this.commit({holdings:this.config.holdings.filter((_,idx)=>idx!==i)}));
      row.querySelector('[data-action="search"]').addEventListener('click',()=>this.searchIsin(i));
      row.querySelectorAll('[data-result-index]').forEach((button)=>button.addEventListener('click',()=>this.selectResult(i,Number(button.dataset.resultIndex))));
    });
  }

  parseValue(key,value){ if(key==='shares'||key==='invested') return Number(value)||0; return value; }

  async searchIsin(index) {
    const isin=String(this.config.holdings[index]?.isin||'').trim().toUpperCase();
    if(!/^[A-Z]{2}[A-Z0-9]{9}[0-9]$/.test(isin)) {
      this._search[index]={error:'Enter a valid 12-character ISIN before searching.'}; this.render(); return;
    }
    this._search[index]={loading:true}; this.render();
    const controller = new AbortController();
    const timeout = setTimeout(()=>controller.abort(),10000);
    try {
      const response=await fetch('https://api.openfigi.com/v3/mapping',{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify([{idType:'ID_ISIN',idValue:isin}]),signal:controller.signal});
      if(!response.ok) throw new Error(`Security lookup returned HTTP ${response.status}.`);
      const payload=await response.json();
      const resultBlock=payload?.[0];
      if(resultBlock?.error) throw new Error(String(resultBlock.error));
      const results=Array.isArray(resultBlock?.data)?resultBlock.data:[];
      if(!results.length) throw new Error('No security was found for that ISIN.');
      this._search[index]={results:results.slice(0,10)};
    } catch(err) {
      console.warn('Investment Tracker Card ISIN lookup error',err);
      this._search[index]={error:err.name==='AbortError'?'Security lookup timed out.':(err.message||'Security lookup failed.')};
    } finally {
      clearTimeout(timeout);
    }
    this.render();
  }

  selectResult(index,resultIndex) {
    const result=this._search[index]?.results?.[resultIndex];
    if(!result) return;
    const holdings=this.config.holdings.map((h,i)=>i===index?{...h,name:result.name||h.name,symbol:result.ticker||h.symbol,exchange:result.exchangeCode||result.exchCode||h.exchange}:h);
    this._search[index]={};
    this.commit({holdings});
  }

  commit(changes){ this.config={...this.config,...changes}; this.dispatchEvent(new CustomEvent('config-changed',{detail:{config:this.config},bubbles:true,composed:true})); }
  escape(value){ return String(value).replace(/[&<>"']/g,(c)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
}

customElements.define('investment-tracker-card', InvestmentTrackerCard);
customElements.define('investment-tracker-card-editor', InvestmentTrackerCardEditor);
