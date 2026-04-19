import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import requests
from io import StringIO

st.set_page_config(page_title="Market Indicators", page_icon="📊", layout="wide")

# ── CSS: Professional Trader Style ───────────────────────────────────────────
st.markdown("""<style>
[data-testid="metric-container"] {
    background:linear-gradient(135deg,#0d1827,#0f2236);
    border:1px solid #1c3a58;
    border-left:3px solid #00bfff;
    border-radius:4px;
    padding:10px 14px;
}
[data-testid="stMetricValue"] {
    font-family:'Courier New',monospace!important;
    font-size:1.5rem!important;
}
[data-testid="stMetricLabel"] p {
    font-family:'Courier New',monospace!important;
    font-size:0.7rem!important;
    letter-spacing:1px;
    text-transform:uppercase;
    color:#5a90b0!important;
}
div[data-testid="stHorizontalBlock"] { gap:0.8rem; }
</style>""", unsafe_allow_html=True)

# ── Header + Refresh Button ───────────────────────────────────────────────────
hcol1, hcol2, hcol3 = st.columns([5, 1, 2])
with hcol1:
    st.markdown("""<div style="padding:10px 0 14px;border-bottom:2px solid #1c3a58;">
      <span style="font-family:monospace;font-size:1.3rem;color:#00bfff;
            letter-spacing:3px;font-weight:bold;">◈ MARKET INDICATORS</span>
      <span style="font-family:monospace;font-size:.75rem;color:#3a6080;margin-left:12px;">
        恐慌指標儀表板
      </span>
    </div>""", unsafe_allow_html=True)
with hcol2:
    st.markdown("<div style='padding-top:8px;'>", unsafe_allow_html=True)
    if st.button("🔄 更新", type="primary", use_container_width=True):
        st.cache_data.clear()
        # Button click already triggers a rerun — no explicit rerun needed
    st.markdown("</div>", unsafe_allow_html=True)
with hcol3:
    st.markdown(f"""<div style="padding:10px 0 14px;border-bottom:2px solid #1c3a58;text-align:right;">
      <span style="background:#0a1f12;border:1px solid #00c853;color:#00c853;
        font-family:monospace;font-size:.65rem;padding:3px 8px;border-radius:10px;">● LIVE</span>
      <span style="font-family:monospace;font-size:.7rem;color:#3a6080;margin-left:8px;">
        {datetime.now().strftime('%Y-%m-%d %H:%M')}
      </span>
    </div>""", unsafe_allow_html=True)

# ── Data Functions ────────────────────────────────────────────────────────────

@st.cache_data(ttl=600)
def get_vix_data(start, end):
    """CBOE VIX history + current value in one request."""
    try:
        resp = requests.get(
            'https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv',
            timeout=10
        )
        df = pd.read_csv(StringIO(resp.text))
        df.columns = [c.upper() for c in df.columns]
        df['date'] = pd.to_datetime(df['DATE'], format='%m/%d/%Y').dt.date
        df = df.rename(columns={'CLOSE': 'value'})
        curr = round(float(df['value'].iloc[-1]), 2)
        prev = round(float(df['value'].iloc[-2]), 2)
        change = round(curr - prev, 2)
        history = df[['date', 'value']]
        history = history[(history['date'] >= start) & (history['date'] <= end)].reset_index(drop=True)
        return history, {'value': curr, 'change': change, 'pct': round(change / prev * 100, 2)}
    except Exception:
        return pd.DataFrame(), None


@st.cache_data(ttl=60)
def get_taiwan_vix():
    """TAIFEX MIS real-time Taiwan VIX."""
    try:
        r = requests.post(
            'https://mis.taifex.com.tw/futures/api/getQuoteListVIX',
            json={},
            headers={
                'User-Agent': 'Mozilla/5.0',
                'Content-Type': 'application/json',
                'Referer': 'https://mis.taifex.com.tw/futures/VolatilityQuotes/',
            },
            timeout=10
        )
        quotes = r.json().get('RtData', {}).get('QuoteList', [])
        if quotes:
            q = quotes[0]
            try:
                val = float(q.get('CLastPrice', 0))
            except (ValueError, TypeError):
                val = 0.0
            if val <= 0:
                return None   # market closed or stale
            ref = float(q.get('CRefPrice', val))
            return {
                'value': val,
                'change': float(q.get('CDiff', 0)),
                'pct': float(q.get('CDiffRate', 0)) * 100,
                'ref': ref,
                'open': q.get('COpenPrice', '-'),
                'high': q.get('CHighPrice', '-'),
                'low': q.get('CLowPrice', '-'),
            }
    except Exception:
        pass
    return None


@st.cache_data(ttl=1800)
def get_fear_greed():
    try:
        import fear_and_greed
        current = fear_and_greed.get()
        return {'value': round(current.value, 1), 'description': current.description}
    except Exception:
        return None


@st.cache_data(ttl=1800)
def get_fear_greed_history(start):
    """CNN Fear & Greed historical data via CNN public API."""
    try:
        r = requests.get(
            f'https://production.dataviz.cnn.io/index/fearandgreed/graphdata/{start.strftime("%Y-%m-%d")}',
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
            timeout=10
        )
        hist = r.json().get('fear_and_greed_historical', {}).get('data', [])
        if hist:
            df = pd.DataFrame(hist)
            df['date'] = pd.to_datetime(df['x'], unit='ms').dt.date
            df = df.rename(columns={'y': 'value'})[['date', 'value']]
            return df.sort_values('date').reset_index(drop=True)
    except Exception:
        pass
    return pd.DataFrame()


@st.cache_data(ttl=3600)
def get_margin_maintenance_ratio():
    """大盤融資維持率 = Σ(非ETF融資股數 × 股價) / 大盤融資金額

    Uses TWSE exchangeReport/MI_MARGN for both margin balances and aggregate
    loan amount. Excludes ETF codes (starting with '00') from the numerator
    per the standard market definition.
    """
    try:
        # ── 1. Latest closing prices (TWSE STOCK_DAY_ALL) ─────────────────────
        r1 = requests.get(
            'https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL',
            params={'response': 'json'},
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=15,
        )
        p1 = r1.json()
        prices = {}
        data_date = p1.get('date', '')   # e.g. "20260313"
        for row in p1.get('data', []):
            try:
                code  = str(row[0]).strip()
                price = float(str(row[7]).replace(',', ''))
                prices[code] = price
            except Exception:
                pass

        # ── 2. MI_MARGN: per-stock balances + aggregate loan ──────────────────
        r2 = requests.get(
            'https://www.twse.com.tw/exchangeReport/MI_MARGN',
            params={'date': data_date, 'selectType': 'ALL', 'response': 'json'},
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=15,
        )
        payload = r2.json()
        if payload.get('stat') != 'OK':
            return None
        tables = payload.get('tables', [])
        if len(tables) < 2:
            return None
        t0, t1 = tables[0], tables[1]

        # Aggregate loan amount: 融資金額(仟元) 今日餘額 (column 5 = today)
        loan_row = next((row for row in t0.get('data', []) if '融資金額' in str(row[0])), None)
        if not loan_row:
            return None
        total_loan_nt = float(str(loan_row[5]).replace(',', '')) * 1000   # 仟元→元

        # Numerator: non-ETF margin positions × closing price
        numerator = 0.0
        for row in t1.get('data', []):
            code = str(row[0]).strip()
            if code.startswith('00'):    # exclude ETFs
                continue
            try:
                lots  = int(str(row[6]).replace(',', ''))   # 今日餘額 (張)
                price = prices.get(code, 0.0)
                numerator += lots * 1000 * price            # 張×1000→股×價
            except Exception:
                pass

        if total_loan_nt == 0:
            return None

        # Parse data_date "20260313" → "2026-03-13"
        date_str = f'{data_date[:4]}-{data_date[4:6]}-{data_date[6:]}' if len(data_date) == 8 else data_date

        return {
            'ratio': numerator / total_loan_nt * 100,
            'numerator': numerator,
            'denominator': total_loan_nt,
            'date': date_str,
        }
    except Exception:
        return None


@st.cache_data(ttl=3600)
def get_margin_history(start):
    """FinMind historical total margin loan balance (融資餘額, in 億元)."""
    try:
        r = requests.get(
            'https://api.finmindtrade.com/api/v4/data',
            params={
                'dataset': 'TaiwanStockTotalMarginPurchaseShortSale',
                'start_date': start.strftime('%Y-%m-%d'),
            },
            timeout=15
        )
        df = pd.DataFrame(r.json().get('data', []))
        if df.empty:
            return pd.DataFrame()
        money = df[df['name'] == 'MarginPurchaseMoney'][['date', 'TodayBalance']].copy()
        money['date'] = pd.to_datetime(money['date']).dt.date
        money['value'] = money['TodayBalance'].astype(float) / 1e8
        return money[['date', 'value']].sort_values('date').reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def get_margin_ratio_history(n_trading_days: int = 30):
    """Compute 大盤融資維持率 history using TWSE MI_MARGN + FinLab prices.

    For each trading day: fetches per-stock margin balances and aggregate loan
    amount from TWSE exchangeReport/MI_MARGN, then looks up that day's closing
    prices from FinLab's full historical price matrix.

    Formula: ratio = Σ(非ETF融資餘額張 × 1000 × 收盤價) / 融資金額(元) × 100
    Reference (2026): 3/9=153.81%, 3/10=158.11%, 3/11=166.13%, 3/12=164.60%
    """
    import time

    # Load FinLab full historical price matrix once (cached by Streamlit)
    try:
        import finlab as _fl, os as _os
        from finlab import data as _fd
        _fl.login(_os.getenv('FINLAB_API_KEY', ''))
        price_df = _fd.get('price:收盤價')   # DatetimeIndex × stock_code
    except Exception:
        price_df = None

    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.twse.com.tw/'}
    results = []
    dt = datetime.now()
    consecutive_miss = 0

    while len(results) < n_trading_days and consecutive_miss < 7:
        if dt.weekday() >= 5:          # skip weekends
            dt -= timedelta(days=1)
            continue

        date_str = dt.strftime('%Y%m%d')
        fetched  = False

        try:
            r = requests.get(
                'https://www.twse.com.tw/exchangeReport/MI_MARGN',
                params={'date': date_str, 'selectType': 'ALL', 'response': 'json'},
                headers=headers,
                timeout=12,
            )
            payload = r.json()
            if payload.get('stat') != 'OK':
                raise ValueError('stat != OK')

            tables = payload.get('tables', [])
            if len(tables) < 2:
                raise ValueError('no tables')
            t0, t1 = tables[0], tables[1]

            # Aggregate loan: 融資金額(仟元) 今日餘額 (index 5 = today's balance)
            loan_row = next(
                (row for row in t0.get('data', []) if '融資金額' in str(row[0])), None
            )
            if not loan_row:
                raise ValueError('no loan row')
            total_loan_nt = float(str(loan_row[5]).replace(',', '')) * 1000  # 仟元→元

            # Look up this date's prices from FinLab price matrix
            ts = pd.Timestamp(dt.date())
            prices_day = {}
            if price_df is not None:
                if ts in price_df.index:
                    prices_day = price_df.loc[ts].fillna(0).to_dict()
                else:
                    before = price_df.index[price_df.index <= ts]
                    if not before.empty:
                        prices_day = price_df.loc[before[-1]].fillna(0).to_dict()

            # Numerator: non-ETF stocks × 1000 shares/lot × price
            numerator = 0.0
            for row in t1.get('data', []):
                code = str(row[0]).strip()
                if code.startswith('00'):   # exclude ETFs
                    continue
                try:
                    lots  = int(str(row[6]).replace(',', ''))   # 今日餘額 (張)
                    price = float(prices_day.get(code, 0) or 0)
                    numerator += lots * 1000 * price
                except Exception:
                    pass

            if total_loan_nt > 0 and numerator > 0:
                results.append({
                    'date':  dt.date(),
                    'ratio': numerator / total_loan_nt * 100,
                })
                consecutive_miss = 0
                fetched = True

        except Exception:
            pass

        if not fetched:
            consecutive_miss += 1
        dt -= timedelta(days=1)
        time.sleep(0.2)   # rate-limit TWSE

    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values('date').reset_index(drop=True)
    return df


@st.cache_data(ttl=3600)
def get_taifex_oi():
    """Fetch TAIFEX institutional OI: P/C ratio, 外資期貨淨口數, 外資選擇權多空口數.

    Endpoints (POST, CSV, cp950):
      pcRatioDown           → P/C ratio history
      futContractsDateDown  → futures OI by investor type
      optContractsDateDown  → options OI by investor type
    Row order within each date×product block: 自營商(0), 投信(1), 外資及陸資(2)
    """
    from datetime import timedelta

    # Use yesterday as end date — today's data may not be published yet
    # (TAIFEX returns an HTML error page if the requested date has no data)
    today_dt = datetime.now()
    end_dt   = today_dt - timedelta(days=1)
    today    = end_dt.strftime('%Y/%m/%d')
    start    = (today_dt - timedelta(days=7)).strftime('%Y/%m/%d')
    hdrs = {
        'User-Agent': 'Mozilla/5.0',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Referer': 'https://www.taifex.com.tw/',
    }
    res = {}

    # ── P/C ratio ─────────────────────────────────────────────────────────────
    try:
        r = requests.post('https://www.taifex.com.tw/cht/3/pcRatioDown',
                          data={'queryStartDate': start, 'queryEndDate': today},
                          headers=hdrs, timeout=15)
        rows = [l.strip().split(',') for l in r.content.decode('cp950', errors='replace').strip().split('\n')
                if l.strip() and l.strip()[0].isdigit()]
        if rows:
            # Data is sorted descending (newest first) in the CSV
            last, prev = rows[0], (rows[1] if len(rows) >= 2 else None)
            res['pc_ratio']      = float(last[6]) if len(last) > 6 and last[6] else None
            res['pc_date']       = last[0]
            res['pc_ratio_prev'] = float(prev[6]) if prev and len(prev) > 6 and prev[6] else None
    except Exception:
        pass

    # ── Futures OI (外資及陸資 net lots, 台股期貨 = first 3 rows per date) ──────
    try:
        r = requests.post('https://www.taifex.com.tw/cht/3/futContractsDateDown',
                          data={'queryStartDate': start, 'queryEndDate': today},
                          headers=hdrs, timeout=15)
        rows = [l.strip().split(',') for l in r.content.decode('cp950', errors='replace').strip().split('\n')
                if l.strip() and l.strip()[0].isdigit()]
        by_date = {}
        for row in rows:
            by_date.setdefault(row[0], []).append(row)
        sorted_dates = sorted(by_date)

        def _fut_net(date_rows):
            # Row index 2 within each date = 外資及陸資 for first product (台股期貨)
            if len(date_rows) >= 3 and len(date_rows[2]) >= 14:
                try:
                    return int(date_rows[2][13])
                except (ValueError, IndexError):
                    pass
            return None

        if sorted_dates:
            res['fut_net_oi']      = _fut_net(by_date[sorted_dates[-1]])
            res['fut_date']        = sorted_dates[-1]
        if len(sorted_dates) >= 2:
            res['fut_net_oi_prev'] = _fut_net(by_date[sorted_dates[-2]])
    except Exception:
        pass

    # ── Options OI (外資及陸資 multi/空 口數, 台指選擇權 = first 3 rows per date) ─
    try:
        r = requests.post('https://www.taifex.com.tw/cht/3/optContractsDateDown',
                          data={'queryStartDate': start, 'queryEndDate': today},
                          headers=hdrs, timeout=15)
        rows = [l.strip().split(',') for l in r.content.decode('cp950', errors='replace').strip().split('\n')
                if l.strip() and l.strip()[0].isdigit()]
        by_date = {}
        for row in rows:
            by_date.setdefault(row[0], []).append(row)
        sorted_dates = sorted(by_date)

        def _opt_oi(date_rows):
            if len(date_rows) >= 3 and len(date_rows[2]) >= 14:
                r = date_rows[2]
                try:
                    return {
                        'long':      int(r[9]),    # 多方未平倉口數
                        'long_val':  int(r[10]),   # 多方未平倉金額(千元)
                        'short':     int(r[11]),   # 空方未平倉口數
                        'short_val': int(r[12]),   # 空方未平倉金額(千元)
                        'net':       int(r[13]),   # 淨口數
                    }
                except (ValueError, IndexError):
                    pass
            return None

        if sorted_dates:
            oi = _opt_oi(by_date[sorted_dates[-1]])
            if oi:
                res.update({'opt_long': oi['long'], 'opt_long_val': oi['long_val'],
                            'opt_short': oi['short'], 'opt_short_val': oi['short_val'],
                            'opt_net': oi['net'], 'opt_date': sorted_dates[-1]})
        if len(sorted_dates) >= 2:
            oi_prev = _opt_oi(by_date[sorted_dates[-2]])
            if oi_prev:
                res['opt_net_prev'] = oi_prev['net']
    except Exception:
        pass

    return res


def compute_fear_score(vix_us, tw_vix, fg_val, margin_ratio):
    """Composite fear score 0–100. Weights: US VIX 35% · TW VIX 25% · F&G 25% · 融資 15%"""
    components = []
    if vix_us is not None:
        components.append((min(100, max(0, (vix_us - 10) / 30 * 100)), 0.35))
    if tw_vix is not None:
        components.append((min(100, max(0, (tw_vix - 10) / 40 * 100)), 0.25))
    if fg_val is not None:
        components.append((100 - fg_val, 0.25))
    if margin_ratio is not None:
        # Calibrated for TWSE per-stock calculation (official ~7pp lower than this formula).
        # 137% ≈ 130% official (extreme fear=100), 173% ≈ 166% official (neutral=0)
        components.append((min(100, max(0, (173 - margin_ratio) / 36 * 100)), 0.15))
    if not components:
        return None
    total_w = sum(w for _, w in components)
    return round(sum(s * w for s, w in components) / total_w, 1)


def fear_info(score):
    if score is None: return "N/A",         "#888888", "—"
    if score >= 75:   return "EXTREME FEAR", "#ff2222", "市場極度恐慌，可能存在超賣機會"
    if score >= 60:   return "FEAR",         "#ff7700", "市場偏向悲觀，風險意識升高"
    if score >= 40:   return "NEUTRAL",      "#ffcc00", "市場情緒中性，觀望居多"
    if score >= 25:   return "GREED",        "#66dd44", "市場樂觀，需留意過熱風險"
    return                   "EXTREME GREED","#00cc00", "市場極度樂觀，警惕泡沫風險"


def fg_color(val):
    if val < 25:   return "#cc0000"
    if val < 45:   return "#ff6600"
    if val < 55:   return "#ffcc00"
    if val < 75:   return "#88dd44"
    return                "#00bb00"


# ── Date Range Picker ─────────────────────────────────────────────────────────
dcol1, dcol2 = st.columns(2)
with dcol1:
    start_date = st.date_input("起始日", value=datetime.now().date() - timedelta(days=90))
with dcol2:
    end_date = st.date_input("結束日", value=datetime.now().date())

# ── Fetch All Data ────────────────────────────────────────────────────────────
df_vix, vix_now = get_vix_data(start_date, end_date)
tw_vix          = get_taiwan_vix()
fg              = get_fear_greed()
df_fg           = get_fear_greed_history(start_date)
margin_result   = get_margin_maintenance_ratio()
df_margin       = get_margin_history(start_date)
taifex_oi       = get_taifex_oi()

vix_val      = vix_now['value']        if vix_now       else None
tw_vix_val   = tw_vix['value']         if tw_vix        else None
fg_val       = fg['value']             if fg            else None
margin_ratio = margin_result['ratio']  if margin_result else None

score              = compute_fear_score(vix_val, tw_vix_val, fg_val, margin_ratio)
label, color, desc = fear_info(score)

CHART_H = 300   # consistent chart height for all four panels
MINI_H  = 200   # quick-view mini gauge height

# ── Quick-View Row: 4 mini gauges ────────────────────────────────────────────
st.markdown("### ◈ 即時快覽")
qv1, qv2, qv3, qv4 = st.columns(4)

def mini_gauge(fig_val, gauge_range, steps, bar_color, title, suffix="", delta_ref=None):
    ind_args = dict(
        mode="gauge+number" + ("+delta" if delta_ref is not None else ""),
        value=fig_val,
        number={'font': {'size': 32}, 'suffix': suffix},
        title={'text': title, 'font': {'size': 11, 'color': '#5a90b0'}},
        gauge={
            'axis': {'range': gauge_range, 'tickfont': {'size': 8}},
            'bar': {'color': bar_color, 'thickness': 0.3},
            'bgcolor': 'rgba(0,0,0,0)', 'borderwidth': 0,
            'steps': steps,
        },
    )
    if delta_ref is not None:
        ind_args['delta'] = {'reference': delta_ref, 'valueformat': '.2f',
                              'font': {'size': 12}}
    fig = go.Figure(go.Indicator(**ind_args))
    fig.update_layout(
        template="plotly_dark", height=MINI_H,
        margin=dict(t=30, b=5, l=10, r=10),
        paper_bgcolor='rgba(0,0,0,0)',
    )
    return fig

with qv1:
    if vix_val is not None:
        vix_bar = "#ff2222" if vix_val >= 30 else ("#ff9900" if vix_val >= 20 else "#00cc44")
        st.plotly_chart(mini_gauge(
            vix_val, [0, 50],
            [{'range': [0,  20], 'color': 'rgba(0,200,0,0.10)'},
             {'range': [20, 30], 'color': 'rgba(255,165,0,0.12)'},
             {'range': [30, 50], 'color': 'rgba(255,0,0,0.16)'}],
            vix_bar, "🇺🇸 US VIX",
        ), use_container_width=True)
    else:
        st.info("US VIX N/A")

with qv2:
    if tw_vix_val is not None:
        tw_bar = "#ff2222" if tw_vix_val >= 30 else ("#ff9900" if tw_vix_val >= 20 else "#00cc44")
        st.plotly_chart(mini_gauge(
            tw_vix_val, [0, 60],
            [{'range': [0,  20], 'color': 'rgba(0,200,0,0.10)'},
             {'range': [20, 30], 'color': 'rgba(255,165,0,0.12)'},
             {'range': [30, 60], 'color': 'rgba(255,0,0,0.16)'}],
            tw_bar, "🇹🇼 TW VIX",
            delta_ref=tw_vix['ref'],
        ), use_container_width=True)
    else:
        st.info("TW VIX N/A")

with qv3:
    if fg_val is not None:
        st.plotly_chart(mini_gauge(
            fg_val, [0, 100],
            [{'range': [0,  25],  'color': 'rgba(180,0,0,0.16)'},
             {'range': [25, 45],  'color': 'rgba(255,80,0,0.10)'},
             {'range': [45, 55],  'color': 'rgba(255,200,0,0.10)'},
             {'range': [55, 75],  'color': 'rgba(100,220,60,0.10)'},
             {'range': [75, 100], 'color': 'rgba(0,180,0,0.16)'}],
            fg_color(fg_val), "😨 Fear & Greed",
        ), use_container_width=True)
    else:
        st.info("F&G N/A")

with qv4:
    if margin_ratio is not None:
        mr_bar = "#ff2222" if margin_ratio < 137 else ("#00bfff" if margin_ratio > 173 else "#00cc44")
        st.plotly_chart(mini_gauge(
            margin_ratio, [100, 230],
            [{'range': [100, 137], 'color': 'rgba(255,0,0,0.16)'},
             {'range': [137, 173], 'color': 'rgba(0,200,0,0.10)'},
             {'range': [173, 230], 'color': 'rgba(0,191,255,0.14)'}],
            mr_bar, "💰 融資維持率", suffix="%",
        ), use_container_width=True)
    else:
        st.info("融資維持率 N/A")

st.divider()

# ── TAIFEX 籌碼指標 Row ────────────────────────────────────────────────────────
st.markdown("### ◈ 期權籌碼")

def _alert_color(val, prev, threshold=0.25):
    """Return CSS color: orange if change > threshold × |prev|, else normal."""
    if val is None or prev is None or prev == 0:
        return "#aaaaaa"
    change_pct = abs(val - prev) / abs(prev)
    if change_pct > threshold:
        return "#ff6600"
    return "#00cc88" if val >= 0 else "#ff4444"

tc1, tc2, tc3, tc4, tc5 = st.columns(5)

with tc1:
    pc = taifex_oi.get('pc_ratio')
    pc_prev = taifex_oi.get('pc_ratio_prev')
    pc_date = taifex_oi.get('pc_date', '')
    if pc is not None:
        pc_delta = f"{pc - pc_prev:+.2f}" if pc_prev else ""
        pc_color = "#ff4444" if pc > 130 else ("#00cc88" if pc < 80 else "#ffcc00")
        st.markdown(f"""<div style="background:linear-gradient(135deg,#0d1827,#0f2236);
            border:1px solid #1c3a58;border-left:3px solid {pc_color};
            border-radius:4px;padding:10px 14px;text-align:center;">
          <div style="font-family:monospace;font-size:.65rem;color:#5a90b0;letter-spacing:1px;">
            PUT/CALL OI比率%</div>
          <div style="font-family:monospace;font-size:1.6rem;color:{pc_color};font-weight:bold;">
            {pc:.2f}</div>
          <div style="font-family:monospace;font-size:.7rem;color:#888;">{pc_delta} ｜ {pc_date}</div>
        </div>""", unsafe_allow_html=True)
    else:
        st.info("P/C Ratio N/A")

with tc2:
    fut_net = taifex_oi.get('fut_net_oi')
    fut_prev = taifex_oi.get('fut_net_oi_prev')
    fut_date = taifex_oi.get('fut_date', '')
    if fut_net is not None:
        fut_color = "#00cc88" if fut_net >= 0 else "#ff4444"
        fut_delta = fut_net - fut_prev if fut_prev is not None else None
        delta_str = f"{fut_delta:+,}" if fut_delta is not None else ""
        alert_col = _alert_color(fut_net, fut_prev)
        delta_color = alert_col if fut_delta is not None else "#888"
        st.markdown(f"""<div style="background:linear-gradient(135deg,#0d1827,#0f2236);
            border:1px solid #1c3a58;border-left:3px solid {fut_color};
            border-radius:4px;padding:10px 14px;text-align:center;">
          <div style="font-family:monospace;font-size:.65rem;color:#5a90b0;letter-spacing:1px;">
            外資期貨淨口數</div>
          <div style="font-family:monospace;font-size:1.6rem;color:{fut_color};font-weight:bold;">
            {fut_net:,}</div>
          <div style="font-family:monospace;font-size:.7rem;color:{delta_color};font-weight:bold;">
            {delta_str} ｜ {fut_date}</div>
        </div>""", unsafe_allow_html=True)
    else:
        st.info("外資期貨 N/A")

with tc3:
    opt_long = taifex_oi.get('opt_long')
    opt_long_val = taifex_oi.get('opt_long_val')
    opt_date = taifex_oi.get('opt_date', '')
    if opt_long is not None:
        long_val_b = f"{opt_long_val/1e5:.1f}億" if opt_long_val else ""
        st.markdown(f"""<div style="background:linear-gradient(135deg,#0d1827,#0f2236);
            border:1px solid #1c3a58;border-left:3px solid #00bfff;
            border-radius:4px;padding:10px 14px;text-align:center;">
          <div style="font-family:monospace;font-size:.65rem;color:#5a90b0;letter-spacing:1px;">
            外資選擇權多方OI</div>
          <div style="font-family:monospace;font-size:1.6rem;color:#00bfff;font-weight:bold;">
            {opt_long:,}</div>
          <div style="font-family:monospace;font-size:.7rem;color:#888;">{long_val_b} ｜ {opt_date}</div>
        </div>""", unsafe_allow_html=True)
    else:
        st.info("選擇權多方 N/A")

with tc4:
    opt_short = taifex_oi.get('opt_short')
    opt_short_val = taifex_oi.get('opt_short_val')
    if opt_short is not None:
        short_val_b = f"{opt_short_val/1e5:.1f}億" if opt_short_val else ""
        st.markdown(f"""<div style="background:linear-gradient(135deg,#0d1827,#0f2236);
            border:1px solid #1c3a58;border-left:3px solid #ff9900;
            border-radius:4px;padding:10px 14px;text-align:center;">
          <div style="font-family:monospace;font-size:.65rem;color:#5a90b0;letter-spacing:1px;">
            外資選擇權空方OI</div>
          <div style="font-family:monospace;font-size:1.6rem;color:#ff9900;font-weight:bold;">
            {opt_short:,}</div>
          <div style="font-family:monospace;font-size:.7rem;color:#888;">{short_val_b}</div>
        </div>""", unsafe_allow_html=True)
    else:
        st.info("選擇權空方 N/A")

with tc5:
    opt_net = taifex_oi.get('opt_net')
    opt_net_prev = taifex_oi.get('opt_net_prev')
    if opt_net is not None:
        opt_color = "#00cc88" if opt_net >= 0 else "#ff4444"
        opt_delta = opt_net - opt_net_prev if opt_net_prev is not None else None
        delta_str = f"{opt_delta:+,}" if opt_delta is not None else ""
        alert_col = _alert_color(opt_net, opt_net_prev)
        delta_color = alert_col if opt_delta is not None else "#888"
        st.markdown(f"""<div style="background:linear-gradient(135deg,#0d1827,#0f2236);
            border:1px solid #1c3a58;border-left:3px solid {opt_color};
            border-radius:4px;padding:10px 14px;text-align:center;">
          <div style="font-family:monospace;font-size:.65rem;color:#5a90b0;letter-spacing:1px;">
            外資選擇權淨口數</div>
          <div style="font-family:monospace;font-size:1.6rem;color:{opt_color};font-weight:bold;">
            {opt_net:,}</div>
          <div style="font-family:monospace;font-size:.7rem;color:{delta_color};font-weight:bold;">
            {delta_str}</div>
        </div>""", unsafe_allow_html=True)
    else:
        st.info("選擇權淨口數 N/A")

st.caption("TAIFEX · P/C比率(成交量基準) · 外資及陸資台股期貨未平倉淨口數 · 台指選擇權外資多空口數 · 每小時更新")

st.divider()

# ── Section 0: Composite Fear Score ──────────────────────────────────────────
st.markdown("### ◈ 綜合恐慌指數")

col_s1, col_s2 = st.columns(2)

with col_s1:
    if score is not None:
        fig_score = go.Figure(go.Indicator(
            mode="gauge+number",
            value=score,
            number={'font': {'size': 52, 'color': color}},
            title={'text': label, 'font': {'size': 16, 'color': color}},
            gauge={
                'axis': {'range': [0, 100], 'tickfont': {'color': '#5a90b0'}},
                'bar': {'color': color, 'thickness': 0.25},
                'bgcolor': 'rgba(0,0,0,0)', 'borderwidth': 0,
                'steps': [
                    {'range': [0,  25],  'color': 'rgba(0,200,0,0.12)'},
                    {'range': [25, 40],  'color': 'rgba(100,220,60,0.12)'},
                    {'range': [40, 60],  'color': 'rgba(255,200,0,0.12)'},
                    {'range': [60, 75],  'color': 'rgba(255,100,0,0.15)'},
                    {'range': [75, 100], 'color': 'rgba(255,0,0,0.18)'},
                ],
                'threshold': {'line': {'color': color, 'width': 4}, 'thickness': 0.8, 'value': score}
            }
        ))
        fig_score.update_layout(
            template="plotly_dark", height=320,
            margin=dict(t=30, b=10), paper_bgcolor='rgba(0,0,0,0)',
        )
        st.plotly_chart(fig_score, use_container_width=True)
    else:
        st.warning("資料不足，無法計算恐慌指數")

with col_s2:
    score_display = f"{score:.1f}" if score is not None else "N/A"
    st.markdown(f"""<div style="padding:20px 24px;
        background:linear-gradient(135deg,#0d1827,#0f2236);
        border:1px solid {color};border-radius:8px;margin-top:12px;">
      <div style="font-family:monospace;font-size:3rem;color:{color};
           font-weight:bold;text-align:center;line-height:1.1;">{score_display}</div>
      <div style="font-family:monospace;font-size:1.1rem;color:{color};
           text-align:center;letter-spacing:3px;margin-top:4px;">{label}</div>
      <div style="font-family:monospace;font-size:0.78rem;color:#7aaccc;
           text-align:center;margin-top:10px;line-height:1.5;">{desc}</div>
      <hr style="border-color:#1c3a58;margin:14px 0;">
    </div>""", unsafe_allow_html=True)

    rows = []
    if vix_val is not None:
        s = min(100, max(0, (vix_val - 10) / 30 * 100))
        rows.append({"指標": "US VIX", "數值": f"{vix_val:.1f}", "恐慌貢獻": f"{s:.0f}", "權重": "35%"})
    if tw_vix_val is not None:
        s = min(100, max(0, (tw_vix_val - 10) / 40 * 100))
        rows.append({"指標": "TW VIX", "數值": f"{tw_vix_val:.1f}", "恐慌貢獻": f"{s:.0f}", "權重": "25%"})
    if fg_val is not None:
        rows.append({"指標": "Fear & Greed", "數值": f"{fg_val:.0f}", "恐慌貢獻": f"{100 - fg_val:.0f}", "權重": "25%"})
    if margin_ratio is not None:
        s = min(100, max(0, (173 - margin_ratio) / 36 * 100))
        rows.append({"指標": "融資維持率", "數值": f"{margin_ratio:.1f}%", "恐慌貢獻": f"{s:.0f}", "權重": "15%"})
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.divider()

# ── Section 1: 走勢圖表 (2×2, all CHART_H) ───────────────────────────────────
st.markdown("### ◈ 走勢圖表")

GAUGE_LAYOUT = dict(
    template="plotly_dark", height=CHART_H,
    margin=dict(t=20, b=10), paper_bgcolor='rgba(0,0,0,0)',
)
LINE_LAYOUT = dict(
    template="plotly_dark", height=CHART_H,
    margin=dict(t=10, b=10, l=40, r=20),
    hovermode='x unified', paper_bgcolor='rgba(0,0,0,0)',
)

# ── Row 1: US VIX | TW VIX ───────────────────────────────────────────────────
r1c1, r1c2 = st.columns(2)

with r1c1:
    st.markdown("**🇺🇸 US VIX — 美股波動率指數**")
    if vix_now:
        m1, m2, m3 = st.columns(3)
        m1.metric("VIX", f"{vix_now['value']:.2f}", f"{vix_now['change']:+.2f}")
        m2.metric("漲跌 %", f"{vix_now['pct']:+.2f}%")
        m3.metric("狀態", "Low" if vix_now['value'] < 20 else ("Med" if vix_now['value'] < 30 else "High"))

    if not df_vix.empty:
        fig_vix = go.Figure()
        fig_vix.add_trace(go.Scatter(
            x=df_vix['date'], y=df_vix['value'],
            mode='lines', name='VIX',
            line=dict(color='#ff4444', width=2),
            fill='tozeroy', fillcolor='rgba(255,50,50,0.07)',
        ))
        fig_vix.add_hline(y=20, line_dash="dash", line_color="#ff9900",
                          annotation_text="20", annotation_font_color="#ff9900")
        fig_vix.add_hline(y=30, line_dash="dash", line_color="#ff2222",
                          annotation_text="30", annotation_font_color="#ff2222")
        fig_vix.update_layout(**LINE_LAYOUT, yaxis_title="VIX")
        st.plotly_chart(fig_vix, use_container_width=True)
        st.caption("CBOE · 每10分更新")
    else:
        st.warning("無法取得 VIX 歷史資料")

with r1c2:
    st.markdown("**🇹🇼 TW VIX (TVIX) — 台灣波動率指數**")
    if tw_vix:
        val = tw_vix['value']
        m1, m2, m3 = st.columns(3)
        m1.metric("TVIX", f"{val:.2f}", f"{tw_vix['change']:+.2f}")
        m2.metric("昨收", f"{tw_vix['ref']:.2f}")
        m3.metric("狀態", "Low" if val < 20 else ("Med" if val < 30 else "High"))

        fig_tvix = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=val,
            delta={'reference': tw_vix['ref'], 'valueformat': '.2f'},
            gauge={
                'axis': {'range': [0, 60]},
                'bar': {'color': '#ff9900'},
                'bgcolor': 'rgba(0,0,0,0)', 'borderwidth': 0,
                'steps': [
                    {'range': [0,  20], 'color': 'rgba(0,200,0,0.12)'},
                    {'range': [20, 30], 'color': 'rgba(255,165,0,0.15)'},
                    {'range': [30, 60], 'color': 'rgba(255,0,0,0.18)'},
                ],
                'threshold': {'line': {'color': '#ffffff', 'width': 3}, 'thickness': 0.75, 'value': val},
            }
        ))
        fig_tvix.update_layout(**GAUGE_LAYOUT)
        st.plotly_chart(fig_tvix, use_container_width=True)
        st.caption("TAIFEX MIS · 每分鐘更新")
    else:
        st.warning("台灣 VIX 不可用（非交易時段）")

# ── Row 2: Fear & Greed | 融資維持率 ────────────────────────────────────────
r2c1, r2c2 = st.columns(2)

with r2c1:
    st.markdown("**😨 CNN Fear & Greed — 市場情緒指數**")
    if fg:
        val = fg['value']
        lc = fg_color(val)
        m1, m2, m3 = st.columns(3)
        m1.metric("F&G 指數", f"{val:.0f}")
        m2.metric("情緒", fg['description'])
        m3.metric("恐慌貢獻", f"{100 - val:.0f}")

        if not df_fg.empty:
            fig_fg = go.Figure()
            fig_fg.add_trace(go.Scatter(
                x=df_fg['date'], y=df_fg['value'],
                mode='lines', name='Fear & Greed',
                line=dict(color=lc, width=2),
                fill='tozeroy', fillcolor='rgba(128,128,128,0.07)',
            ))
            fig_fg.add_hline(y=25, line_dash="dash", line_color="#cc0000",
                             annotation_text="Fear", annotation_font_color="#cc0000")
            fig_fg.add_hline(y=75, line_dash="dash", line_color="#00bb00",
                             annotation_text="Greed", annotation_font_color="#00bb00")
            fig_fg.add_hline(y=50, line_dash="dot", line_color="#555555",
                             annotation_text="Neutral", annotation_font_color="#555555")
            fig_fg.update_layout(**LINE_LAYOUT, yaxis={'range': [0, 100], 'title': 'F&G'})
            st.plotly_chart(fig_fg, use_container_width=True)
            st.caption("CNN · 每30分更新")
        else:
            # Fallback: gauge when no history
            fig_fg_g = go.Figure(go.Indicator(
                mode="gauge+number",
                value=val,
                gauge={
                    'axis': {'range': [0, 100]},
                    'bar': {'color': lc},
                    'bgcolor': 'rgba(0,0,0,0)', 'borderwidth': 0,
                    'steps': [
                        {'range': [0,  25],  'color': 'rgba(180,0,0,0.18)'},
                        {'range': [25, 45],  'color': 'rgba(255,80,0,0.12)'},
                        {'range': [45, 55],  'color': 'rgba(255,200,0,0.12)'},
                        {'range': [55, 75],  'color': 'rgba(100,220,60,0.12)'},
                        {'range': [75, 100], 'color': 'rgba(0,180,0,0.18)'},
                    ],
                    'threshold': {'line': {'color': '#ffffff', 'width': 3}, 'thickness': 0.75, 'value': val},
                }
            ))
            fig_fg_g.update_layout(**GAUGE_LAYOUT)
            st.plotly_chart(fig_fg_g, use_container_width=True)
            st.caption("CNN · 每30分更新")
    else:
        st.warning("Fear & Greed 資料不可用")

with r2c2:
    st.markdown("**💰 大盤融資維持率 — 市場槓桿指標**")
    if margin_result:
        ratio = margin_result['ratio']
        if ratio < 130:    m_risk, m_color = "極度恐慌", "#ff2222"
        elif ratio <= 166: m_risk, m_color = "正常",    "#00cc44"
        else:              m_risk, m_color = "樂觀",    "#00bfff"

        m1, m2, m3 = st.columns(3)
        m1.metric("維持率", f"{ratio:.1f}%", m_risk)
        m2.metric("融資市值", f"{margin_result['numerator'] / 1e8:.0f}億")
        m3.metric("融資餘額", f"{margin_result['denominator'] / 1e8:.1f}億")
        if not margin_result.get('date_aligned', True):
            st.caption(
                f"⚠️ 股價資料({margin_result.get('twse_date','')}) "
                f"與融資餘額資料({margin_result.get('date','')}) 日期差一天，"
                f"比率為估算值。"
            )

        df_ratio_hist = get_margin_ratio_history(30)
        if not df_ratio_hist.empty:
            fig_m = go.Figure()
            fig_m.add_trace(go.Scatter(
                x=df_ratio_hist['date'], y=df_ratio_hist['ratio'],
                mode='lines+markers', name='融資維持率',
                line=dict(color='#00aaff', width=2),
                marker=dict(size=5),
                fill='tozeroy', fillcolor='rgba(0,170,255,0.07)',
                hovertemplate='%{x|%Y-%m-%d}  %{y:.2f}%<extra></extra>',
            ))
            # Reference lines
            fig_m.add_hline(y=137, line_dash="dash", line_color="#ff2222",
                            annotation_text="137%（≈官方130%）危險", annotation_font_color="#ff2222")
            fig_m.add_hline(y=173, line_dash="dot", line_color="#00bfff",
                            annotation_text="173%（≈官方166%）中性", annotation_font_color="#00bfff")
            # Today's computed value as a marker
            fig_m.add_hline(
                y=ratio, line_dash="dot", line_color="#ffcc00",
                annotation_text=f"今日 {ratio:.2f}%",
                annotation_font_color="#ffcc00",
            )
            fig_m.update_layout(**LINE_LAYOUT, yaxis_title="融資維持率 (%)")
            st.plotly_chart(fig_m, use_container_width=True)
            st.caption(
                f"資料日期：{margin_result['date']} · TWSE MI_MARGN 計算值 {ratio:.2f}%"
                f"（官方值約低 6-7pp）· 每小時更新"
            )
        elif not df_margin.empty:
            # Fallback: show balance trend if TWSE API unavailable
            fig_m = go.Figure()
            fig_m.add_trace(go.Scatter(
                x=df_margin['date'], y=df_margin['value'],
                mode='lines', name='融資餘額(億)',
                line=dict(color='#00aaff', width=2),
                fill='tozeroy', fillcolor='rgba(0,170,255,0.07)',
            ))
            fig_m.update_layout(**LINE_LAYOUT, yaxis_title="融資餘額 (億元)")
            st.plotly_chart(fig_m, use_container_width=True)
            st.caption(f"TWSE × FinMind（備用：顯示融資餘額）· {margin_result['date']}")
        else:
            fig_m_g = go.Figure(go.Indicator(
                mode="gauge+number",
                value=ratio,
                number={'suffix': '%'},
                gauge={
                    'axis': {'range': [100, 250]},
                    'bar': {'color': m_color},
                    'bgcolor': 'rgba(0,0,0,0)', 'borderwidth': 0,
                    'steps': [
                        {'range': [100, 130], 'color': 'rgba(255,0,0,0.18)'},
                        {'range': [130, 166], 'color': 'rgba(0,200,0,0.12)'},
                        {'range': [166, 250], 'color': 'rgba(0,191,255,0.15)'},
                    ],
                    'threshold': {'line': {'color': '#ffffff', 'width': 3}, 'thickness': 0.75, 'value': ratio},
                }
            ))
            fig_m_g.update_layout(**GAUGE_LAYOUT)
            st.plotly_chart(fig_m_g, use_container_width=True)
            st.caption(f"TWSE × FinMind · {margin_result['date']}")
    else:
        st.warning("融資維持率資料不可用（非交易日）")

st.divider()

# ── Section 2: Summary Table ──────────────────────────────────────────────────
st.markdown("### ◈ 指標摘要")

now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
summary = []
if vix_now:
    v = vix_now['value']
    summary.append({'指標': 'US VIX', '數值': f"{v:.2f}",
                    '漲跌': f"{vix_now['change']:+.2f} ({vix_now['pct']:+.2f}%)",
                    '狀態': "Low" if v < 20 else ("Medium" if v < 30 else "High"),
                    '更新時間': now_str})
if tw_vix:
    tv = tw_vix['value']
    summary.append({'指標': 'TW VIX (TVIX)', '數值': f"{tv:.2f}",
                    '漲跌': f"{tw_vix['change']:+.2f} ({tw_vix['pct']:+.2f}%)",
                    '狀態': "Low" if tv < 20 else ("Medium" if tv < 30 else "High"),
                    '更新時間': now_str})
if fg:
    summary.append({'指標': 'Fear & Greed', '數值': f"{fg['value']:.0f}", '漲跌': '—',
                    '狀態': fg['description'], '更新時間': now_str})
if margin_result:
    ratio = margin_result['ratio']
    summary.append({'指標': '大盤融資維持率', '數值': f"{ratio:.2f}%", '漲跌': '—',
                    '狀態': "極度恐慌" if ratio < 130 else ("正常" if ratio <= 166 else "樂觀"),
                    '更新時間': now_str})
if score is not None:
    summary.append({'指標': '★ 綜合恐慌指數', '數值': f"{score:.1f}", '漲跌': '—',
                    '狀態': label, '更新時間': now_str})

if summary:
    st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)

st.info("💡 資料來源：US VIX (CBOE) · 台灣 VIX (TAIFEX MIS) · CNN Fear & Greed · TWSE OpenAPI · FinMind　｜　台灣 VIX 每分鐘更新，其他每 30–60 分鐘更新")
