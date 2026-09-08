from pathlib import Path

path = Path("ha-investment-tracker-card.js")
text = path.read_text(encoding="utf-8")
marker = "  async searchIsin(index) {"
start = text.index(marker)
end = text.index("\n  selectResult(", start)

replacement = '''  async searchIsin(index) {
    const isin = String(this.config.holdings[index]?.isin || '').trim().toUpperCase();
    if (!/^[A-Z]{2}[A-Z0-9]{9}[0-9]$/.test(isin)) {
      this._search[index] = { error: 'Enter a valid 12-character ISIN before searching.' };
      this.render();
      return;
    }
    this._search[index] = { loading: true };
    this.render();
    let timeout;
    try {
      const controller = new AbortController();
      timeout = setTimeout(() => controller.abort(), 10000);
      const response = await fetch(`https://query1.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(isin)}&quotesCount=10&newsCount=0&listsCount=0`, {
        signal: controller.signal,
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) throw new Error(`Security lookup returned HTTP ${response.status}.`);
      const payload = await response.json();
      const results = Array.isArray(payload?.quotes)
        ? payload.quotes.map(result => ({
            ...result,
            name: result.longname || result.shortname || result.name || result.symbol,
            ticker: result.symbol,
            exchangeCode: result.exchange || result.fullExchangeName || result.exchangeTimezoneName,
            securityType: result.quoteType || 'Security',
          })).filter(result => result.symbol)
        : [];
      if (!results.length) throw new Error('No security was found for that ISIN.');
      this._search[index] = { results: results.slice(0, 10) };
    } catch (err) {
      console.warn('Investment Tracker Card ISIN lookup error', err);
      this._search[index] = { error: err.name === 'AbortError' ? 'Security lookup timed out.' : err.message || 'Security lookup failed.' };
    } finally {
      clearTimeout(timeout);
    }
    this.render();
  }'''

path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
