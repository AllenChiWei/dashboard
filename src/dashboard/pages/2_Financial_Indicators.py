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
            val = float(q.get('CLastPrice', 0))
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
    """大盤融資維持率 = Σ(融資股數 × 股價) / 大盤融資餘額"""
    try:
        r1 = requests.get('https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL', timeout=15)
        prices = {}
        for item in r1.json():
            try:
                prices[str(item.get('Code', '')).strip()] = float(
                    str(item.get('ClosingPrice', '0')).replace(',', '')
                )
            except Exception:
                pass

        r2 = requests.get('https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN', timeout=15)
        margin_rows = r2.json()
        if not margin_rows:
            return None

        keys = list(margin_rows[0].keys())
        code_key = keys[0]
        balance_key = next(
            (k for k in keys if '今日餘額' in k or ('餘額' in k and '融資' in k)),
            keys[3] if len(keys) > 3 else keys[1]
        )

        start_dt = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
        r3 = requests.get(
            'https://api.finmindtrade.com/api/v4/data',
            params={'dataset': 'TaiwanStockTotalMarginPurchaseShortSale', 'start_date': start_dt},
            timeout=15
        )
        money_rows = [x for x in r3.json().get('data', []) if x.get('name') == 'MarginPurchaseMoney']
        if not money_rows:
            return None
        denominator = float(money_rows[-1]['TodayBalance'])
        if denominator == 0:
            return None

        numerator = 0.0
        for item in margin_rows:
            try:
                code = str(item.get(code_key, '')).strip()
                lots = float(str(item.get(balance_key, '0')).replace(',', ''))
                numerator += lots * 1000 * prices.get(code, 0.0)
            except Exception:
                pass

        return {
            'ratio': numerator / denominator * 100,
            'numerator': numerator,
            'denominator': denominator,
            'date': money_rows[-1].get('date', ''),
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
        # 130% = extreme fear (100), 166% = neutral (0), >166% = optimistic (clamped 0)
        components.append((min(100, max(0, (166 - margin_ratio) / 36 * 100)), 0.15))
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
        mr_bar = "#ff2222" if margin_ratio < 130 else ("#00bfff" if margin_ratio > 166 else "#00cc44")
        st.plotly_chart(mini_gauge(
            margin_ratio, [100, 220],
            [{'range': [100, 130], 'color': 'rgba(255,0,0,0.16)'},
             {'range': [130, 166], 'color': 'rgba(0,200,0,0.10)'},
             {'range': [166, 220], 'color': 'rgba(0,191,255,0.14)'}],
            mr_bar, "💰 融資維持率", suffix="%",
        ), use_container_width=True)
    else:
        st.info("融資維持率 N/A")

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
        s = min(100, max(0, (166 - margin_ratio) / 36 * 100))
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
        m3.metric("融資餘額", f"{margin_result['denominator'] / 1e8:.0f}億")

        if not df_margin.empty:
            fig_m = go.Figure()
            fig_m.add_trace(go.Scatter(
                x=df_margin['date'], y=df_margin['value'],
                mode='lines', name='融資餘額',
                line=dict(color='#00aaff', width=2),
                fill='tozeroy', fillcolor='rgba(0,170,255,0.07)',
            ))
            # Mark today's denominator value
            today_val = margin_result['denominator'] / 1e8
            fig_m.add_hline(
                y=today_val, line_dash="dot", line_color="#ffcc00",
                annotation_text=f"今日 {today_val:.0f}億",
                annotation_font_color="#ffcc00",
            )
            fig_m.update_layout(**LINE_LAYOUT, yaxis_title="融資餘額 (億元)")
            st.plotly_chart(fig_m, use_container_width=True)
            st.caption(f"TWSE × FinMind · {margin_result['date']} · 每小時更新")
        else:
            # Fallback: gauge when no history
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
