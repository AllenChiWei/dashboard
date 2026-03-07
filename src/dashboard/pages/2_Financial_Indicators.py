import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

st.set_page_config(page_title="Market Indicators", page_icon="📊", layout="wide")

st.title("📊 Market Indicators Dashboard")

# --- 日期範圍 ---
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start Date", value=datetime.now().date() - timedelta(days=90))
with col2:
    end_date = st.date_input("End Date", value=datetime.now().date())

# ── 1. US VIX ──────────────────────────────────────────────────────────────
st.header("📈 Volatility Index (VIX)")

@st.cache_data(ttl=600)
def get_vix(start, end):
    try:
        import requests
        from io import StringIO
        resp = requests.get(
            'https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv',
            timeout=10
        )
        df = pd.read_csv(StringIO(resp.text))
        df.columns = [c.upper() for c in df.columns]
        df['date'] = pd.to_datetime(df['DATE'], format='%m/%d/%Y').dt.date
        df = df.rename(columns={'CLOSE': 'value'})[['date', 'value']]
        df = df[(df['date'] >= start) & (df['date'] <= end)]
        return df.reset_index(drop=True)
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=600)
def get_vix_current():
    try:
        import requests
        from io import StringIO
        resp = requests.get(
            'https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv',
            timeout=10
        )
        df = pd.read_csv(StringIO(resp.text))
        curr = round(float(df.iloc[-1]['CLOSE']), 2)
        prev = round(float(df.iloc[-2]['CLOSE']), 2)
        change = round(curr - prev, 2)
        pct = round(change / prev * 100, 2)
        return {'value': curr, 'change': change, 'pct': pct}
    except:
        return None

@st.cache_data(ttl=60)
def get_taiwan_vix():
    """從 TAIFEX MIS 取得台灣 VIX（臺指波動率指數）即時數值"""
    try:
        import requests
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
        d = r.json()
        quotes = d.get('RtData', {}).get('QuoteList', [])
        if quotes:
            q = quotes[0]
            val = float(q.get('CLastPrice', 0))
            diff = float(q.get('CDiff', 0))
            diff_rate = float(q.get('CDiffRate', 0)) * 100
            ref = float(q.get('CRefPrice', val))
            return {
                'value': val, 'change': diff, 'pct': diff_rate,
                'ref': ref,
                'open': q.get('COpenPrice', '-'),
                'high': q.get('CHighPrice', '-'),
                'low': q.get('CLowPrice', '-'),
                'date': q.get('CDate', ''),
            }
    except Exception:
        pass
    return None

col_vix1, col_vix2 = st.columns(2)

with col_vix1:
    st.subheader("🇺🇸 US VIX Index")
    try:
        df_vix = get_vix(start_date, end_date)
        vix_now = get_vix_current()

        if vix_now:
            val = vix_now['value']
            change = vix_now['change']
            pct = vix_now['pct']
            status = "Low (<20)" if val < 20 else ("Medium (20-30)" if val < 30 else "High (>30)")
            c1, c2, c3 = st.columns(3)
            c1.metric("VIX", f"{val:.2f}", f"{change:+.2f} ({pct:+.2f}%)")
            c2.metric("前日", f"{round(val - change, 2):.2f}")
            c3.metric("狀態", status)

        if not df_vix.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df_vix['date'], y=df_vix['value'],
                mode='lines', name='VIX', line=dict(color='red', width=2),
                fill='tozeroy', fillcolor='rgba(255,0,0,0.1)'
            ))
            fig.add_hline(y=20, line_dash="dash", line_color="orange", annotation_text="20")
            fig.add_hline(y=30, line_dash="dash", line_color="red", annotation_text="30")
            fig.update_layout(
                yaxis_title="VIX", template="plotly_dark",
                height=320, hovermode='x unified', margin=dict(t=10)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("無法取得 VIX 歷史資料")
    except Exception as e:
        st.error(f"Error loading US VIX: {e}")

with col_vix2:
    st.subheader("🇹🇼 台灣 VIX（臺指波動率指數）")
    try:
        tw_vix = get_taiwan_vix()

        if tw_vix:
            val = tw_vix['value']
            change = tw_vix['change']
            pct = tw_vix['pct']
            tw_status = "Low (<20)" if val < 20 else ("Medium (20-30)" if val < 30 else "High (>30)")

            c1, c2, c3 = st.columns(3)
            c1.metric("TVIX", f"{val:.2f}", f"{change:+.2f} ({pct:+.2f}%)")
            c2.metric("昨收", f"{tw_vix['ref']:.2f}")
            c3.metric("狀態", tw_status)

            col_ohlv1, col_ohlv2, col_ohlv3 = st.columns(3)
            col_ohlv1.metric("開盤", tw_vix['open'])
            col_ohlv2.metric("最高", tw_vix['high'])
            col_ohlv3.metric("最低", tw_vix['low'])

            fig2 = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=val,
                delta={'reference': tw_vix['ref'], 'valueformat': '.2f'},
                title={'text': "臺指波動率指數 TVIX", 'font': {'size': 16}},
                gauge={
                    'axis': {'range': [0, 60]},
                    'bar': {'color': 'orange'},
                    'steps': [
                        {'range': [0, 20], 'color': 'rgba(0,200,0,0.2)'},
                        {'range': [20, 30], 'color': 'rgba(255,165,0,0.2)'},
                        {'range': [30, 60], 'color': 'rgba(255,0,0,0.2)'},
                    ],
                    'threshold': {'line': {'color': 'white', 'width': 3}, 'thickness': 0.75, 'value': val}
                }
            ))
            fig2.update_layout(template="plotly_dark", height=320, margin=dict(t=10))
            st.plotly_chart(fig2, use_container_width=True)
            st.caption("資料來源：TAIFEX MIS 即時報價，每分鐘更新")
        else:
            st.warning("無法取得台灣 VIX 資料（非交易時段）")
    except Exception as e:
        st.error(f"Error loading TW VIX: {e}")

# ── 2. Fear & Greed ─────────────────────────────────────────────────────────
st.header("😨 CNN Fear & Greed Index")

@st.cache_data(ttl=1800)
def get_fear_greed():
    try:
        import fear_and_greed
        current = fear_and_greed.get()
        return {'value': round(current.value, 1), 'description': current.description}
    except:
        return None

fg = get_fear_greed()

if fg:
    val = fg['value']
    desc = fg['description']

    if val < 25:
        gauge_color = "darkred"
    elif val < 45:
        gauge_color = "red"
    elif val < 55:
        gauge_color = "gold"
    elif val < 75:
        gauge_color = "lightgreen"
    else:
        gauge_color = "green"

    col_fg1, col_fg2 = st.columns([1, 2])
    with col_fg1:
        st.metric("目前指數", f"{val:.0f}", desc)
        st.markdown("""
        **情緒解讀：**
        - 🔴 Extreme Fear: 0–25
        - 😟 Fear: 25–45
        - 😐 Neutral: 45–55
        - 😊 Greed: 55–75
        - 🤑 Extreme Greed: 75–100
        """)

    with col_fg2:
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=val,
            title={'text': "Fear & Greed Index", 'font': {'size': 18}},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': gauge_color},
                'steps': [
                    {'range': [0, 25], 'color': 'rgba(139,0,0,0.3)'},
                    {'range': [25, 45], 'color': 'rgba(255,0,0,0.2)'},
                    {'range': [45, 55], 'color': 'rgba(255,215,0,0.2)'},
                    {'range': [55, 75], 'color': 'rgba(144,238,144,0.2)'},
                    {'range': [75, 100], 'color': 'rgba(0,128,0,0.2)'},
                ],
                'threshold': {'line': {'color': "white", 'width': 3}, 'thickness': 0.75, 'value': val}
            }
        ))
        fig_gauge.update_layout(template="plotly_dark", height=300)
        st.plotly_chart(fig_gauge, use_container_width=True)
else:
    st.warning("無法取得 Fear & Greed 資料")

# ── 3. 台股融資維持率 ────────────────────────────────────────────────────────
st.header("💰 台股融資維持率")

@st.cache_data(ttl=3600)
def get_margin_rate():
    try:
        import requests
        resp = requests.get(
            "https://www.twse.com.tw/exchangeReport/MI_5MINS",
            params={'response': 'json', 'date': datetime.now().strftime('%Y%m%d')},
            timeout=10
        )
        d = resp.json()
        if 'data' in d and d['data']:
            latest = d['data'][-1]
            rate = float(latest[4].replace('%', '')) if len(latest) > 4 else None
            return rate
    except:
        pass
    return None

margin = get_margin_rate()

if margin is not None:
    if margin < 200:
        risk = "低風險"
        margin_color = "green"
    elif margin < 300:
        risk = "中風險"
        margin_color = "orange"
    else:
        risk = "高風險"
        margin_color = "red"

    col_m1, col_m2 = st.columns([1, 2])
    with col_m1:
        st.metric("融資維持率", f"{margin:.2f}%", risk)
        st.markdown("""
        **風險區間：**
        - 🟢 低風險: < 200%
        - 🟡 中風險: 200–300%
        - 🔴 高風險: > 300%
        """)
    with col_m2:
        fig_m = go.Figure(go.Indicator(
            mode="gauge+number",
            value=margin,
            number={'suffix': '%'},
            title={'text': "融資維持率"},
            gauge={
                'axis': {'range': [100, 400]},
                'bar': {'color': margin_color},
                'steps': [
                    {'range': [100, 200], 'color': 'rgba(0,200,0,0.2)'},
                    {'range': [200, 300], 'color': 'rgba(255,165,0,0.2)'},
                    {'range': [300, 400], 'color': 'rgba(255,0,0,0.2)'},
                ],
                'threshold': {'line': {'color': "white", 'width': 3}, 'thickness': 0.75, 'value': margin}
            }
        ))
        fig_m.update_layout(template="plotly_dark", height=300)
        st.plotly_chart(fig_m, use_container_width=True)
else:
    st.warning("無法取得融資維持率資料（可能今日未開市）")

# ── 4. 指標摘要 ──────────────────────────────────────────────────────────────
st.header("📋 指標摘要")

summary = []
vix_now_val = get_vix_current()
if vix_now_val:
    v = vix_now_val['value']
    vix_status = "Low" if v < 20 else ("Medium" if v < 30 else "High")
    summary.append({
        '指標': 'US VIX',
        '數值': f"{v:.2f}",
        '漲跌': f"{vix_now_val['change']:+.2f} ({vix_now_val['pct']:+.2f}%)",
        '狀態': vix_status,
        '更新時間': datetime.now().strftime('%Y-%m-%d %H:%M')
    })
tw_vix_summary = get_taiwan_vix()
if tw_vix_summary:
    tv = tw_vix_summary['value']
    tv_status = "Low" if tv < 20 else ("Medium" if tv < 30 else "High")
    summary.append({
        '指標': 'TW VIX (TVIX)',
        '數值': f"{tv:.2f}",
        '漲跌': f"{tw_vix_summary['change']:+.2f} ({tw_vix_summary['pct']:+.2f}%)",
        '狀態': tv_status,
        '更新時間': datetime.now().strftime('%Y-%m-%d %H:%M')
    })
if fg:
    summary.append({'指標': 'Fear & Greed', '數值': f"{fg['value']:.0f}", '漲跌': '-', '狀態': fg['description'], '更新時間': datetime.now().strftime('%Y-%m-%d %H:%M')})
if margin is not None:
    summary.append({'指標': '融資維持率', '數值': f"{margin:.2f}%", '漲跌': '-', '狀態': risk, '更新時間': datetime.now().strftime('%Y-%m-%d %H:%M')})

if summary:
    st.dataframe(pd.DataFrame(summary), use_container_width=True, hide_index=True)

st.info("💡 資料來源：US VIX (CBOE)、台灣 VIX (TAIFEX MIS)、CNN Fear & Greed、TWSE。台灣 VIX 每分鐘更新，其他每 10–30 分鐘更新。")
