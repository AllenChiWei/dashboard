# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment

- **Conda env**: `dashboard` at `C:/Users/Master/Anaconda3/envs/dashboard/`
- **Python**: `C:/Users/Master/Anaconda3/envs/dashboard/python.exe`
- **Working dir**: `D:/ai/Dashboard`
- `.pth` file at `C:/Users/Master/Anaconda3/envs/dashboard/Lib/site-packages/dashboard.pth` enables `import src.*` from anywhere

## Commands

```bash
# Start the dashboard
C:/Users/Master/Anaconda3/envs/dashboard/Scripts/streamlit.exe run src/dashboard/Home.py
# → http://localhost:8501

# Check if running
netstat -ano | findstr :8501

# Run ETL pipeline manually
C:/Users/Master/Anaconda3/envs/dashboard/python.exe src/etl/pipeline.py

# Run tests
C:/Users/Master/Anaconda3/envs/dashboard/python.exe -m pytest test_crawlers.py -v

# Quick Python test
C:/Users/Master/Anaconda3/envs/dashboard/python.exe -c "<code>"

# Install a new package
C:/Users/Master/Anaconda3/envs/dashboard/Scripts/pip.exe install <package>
# Then add to requirements.txt
```

After fixing a bug, remind the user to hard-refresh the browser (Ctrl+Shift+R) to clear Streamlit cache.

## Architecture

### Data Flow

```
External APIs → src/crawlers/ → src/etl/pipeline.py → PostgreSQL
                                                           ↓
                                          src/dashboard/pages/*.py (Streamlit)
                                                           ↓
                                          src/dashboard/agents/ (Claude Opus 4.6 AI)
```

### Dashboard Pages

Pages in `src/dashboard/pages/` are auto-routed by Streamlit (filename = route):

| File | Purpose | Key data sources |
|------|---------|-----------------|
| `1_Market_Overview.py` | US stock market view | yfinance + PostgreSQL |
| `2_Financial_Indicators.py` | Real-time fear metrics | CBOE (VIX), TAIFEX MIS (TVIX), CNN, TWSE OpenAPI, FinMind |
| `3_Taiwan_Stocks.py` | Taiwan K-line charts | FinLab |
| `5_AI_Analyst.py` | AI chat with market context | `src/dashboard/agents/` + all indicators |

### Caching Strategy

All live data fetches use `@st.cache_data(ttl=N)`:
- TVIX: 60s (real-time)
- VIX history: 600s
- Fear & Greed: 1800s
- Margin maintenance ratio: 3600s
- TAIFEX OI data: 3600s

### Database (SQLAlchemy 2.x)

Models in `src/database/models.py`: `MarketData`, `SentimentData`, `VIXData`, `MarginData`.

**Critical**: Always use SQLAlchemy 2.x style — `conn.execute(query, params)` + `pd.DataFrame(result.fetchall(), columns=result.keys())`. Do **not** use `pd.read_sql()` with a connection object.

### AI Analyst (`src/dashboard/agents/`)

- Model: `claude-opus-4-6` with `thinking={"type": "adaptive"}`
- `MarketAnalyst` is a **synchronous** wrapper around the `anthropic` SDK (not the Agent SDK) — required for Streamlit compatibility
- `analyst.analyze(context)` → blocking one-shot analysis
- `analyst.stream(messages)` → generator for `st.write_stream()`
- `build_context(vix, tw_vix, fg, margin_result, score, label)` → builds the structured context dict

### Fear Score Formula

Composite fear score (0–100) with weights summing to 1.0:
- US VIX: 0.35
- TW VIX: 0.25
- Fear & Greed: 0.25
- 融資維持率 (margin maintenance ratio): 0.15

Defined in `2_Financial_Indicators.py:compute_fear_score()` and replicated in `5_AI_Analyst.py`.

## Key External APIs

| Indicator | Endpoint | Notes |
|-----------|----------|-------|
| US VIX | `https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv` | CSV, GET |
| TW VIX (TVIX) | `POST https://mis.taifex.com.tw/futures/api/getQuoteListVIX` | JSON `{}` body, Referer required; returns empty when market closed |
| CNN Fear & Greed | `fear_and_greed` Python library | |
| P/C Ratio | `POST https://www.taifex.com.tw/cht/3/pcRatioDown` | CSV, cp950, descending date order |
| 外資期貨OI | `POST https://www.taifex.com.tw/cht/3/futContractsDateDown` | CSV, cp950, needs `queryStartDate`/`queryEndDate` |
| 外資選擇權OI | `POST https://www.taifex.com.tw/cht/3/optContractsDateDown` | CSV, cp950, same params |
| 融資維持率 | TWSE OpenAPI `MI_MARGN` + FinMind `TaiwanStockTotalMarginPurchaseShortSale` | See notes below |
| Taiwan stocks | FinLab `data.get('price:收盤價')` | VIP account, key in `.env` |

**TAIFEX CSV quirks:**
- All three endpoints use `decode('cp950', errors='replace')`
- Use `queryEndDate = yesterday` (not today) — server returns HTML error if today's data isn't published
- Row ordering within each date×product block: 自營商(index 0), 投信(index 1), 外資及陸資(index 2)
- pcRatioDown data is in **descending** date order — use `rows[0]` for the latest row
- col[6] of pcRatioDown = 買賣權未平倉量比率%
- col[13] of futContractsDateDown / optContractsDateDown = 多空未平倉淨口數

**融資維持率 notes:**
- TWSE `STOCK_DAY_ALL` → closing prices (always latest trading day D')
- TWSE `MI_MARGN` → per-stock margin share balances; keys[6] = 融資今日餘額, keys[5] = 融資前日餘額
- FinMind `MarginPurchaseMoney` → aggregate cash balance (denominator); may lag TWSE by 1 day
- When FinMind date ≠ TWSE date, use 前日餘額 to align numerator and denominator to the same day
- TWSE dates are in ROC format: `"1150310"` → parse as `int(raw[:3]) + 1911` for Gregorian year

## Conventions

**Charts**: Always use `template="plotly_dark"`. For Taiwan stocks, use `xaxis_type='category'` with string dates to eliminate weekend gaps. Colors: red=up (`#ef5350`), green=down (`#26a69a`) per Taiwan convention.

**Page CSS**: All pages inject the same dark trading-terminal CSS with monospace fonts via `st.markdown("""<style>...""", unsafe_allow_html=True)`.

**FinLab login**: `finlab.login(os.getenv('FINLAB_API_KEY', ''))` — call inside the cached fetch function.

**Secrets**: `.env` is gitignored. Required keys: `POSTGRES_*`, `ANTHROPIC_API_KEY`, `FINLAB_API_KEY`.

## Skills (Slash Commands)

Invoke these via `/skill-name` in Claude Code:

- `/add-indicator` — Add a new market indicator to `2_Financial_Indicators.py`
- `/add-page` — Create a new Streamlit dashboard page
- `/debug-data` — Debug a failing data fetch function
- `/taiwan-stock` — Look up / add a Taiwan stock with FinLab
- `/deploy` — Start or restart the Streamlit server
