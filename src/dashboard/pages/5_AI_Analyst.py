"""
AI 市場分析師
Uses MarketAnalyst (Claude Opus 4.6 + adaptive thinking) to interpret
the four panic indicators and answer user questions in a chat interface.
"""

import streamlit as st
from datetime import datetime, timedelta
import requests
from io import StringIO
import pandas as pd

st.set_page_config(
    page_title="AI Market Analyst",
    page_icon="🤖",
    layout="wide",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""<style>
[data-testid="metric-container"] {
    background:linear-gradient(135deg,#0d1827,#0f2236);
    border:1px solid #1c3a58;border-left:3px solid #00bfff;
    border-radius:4px;padding:10px 14px;
}
[data-testid="stMetricValue"] {
    font-family:'Courier New',monospace!important;font-size:1.4rem!important;
}
[data-testid="stMetricLabel"] p {
    font-family:'Courier New',monospace!important;font-size:0.7rem!important;
    letter-spacing:1px;text-transform:uppercase;color:#5a90b0!important;
}
div[data-testid="stChatMessage"] {
    background:linear-gradient(135deg,#0d1827,#0f2236);
    border:1px solid #1c3a58;border-radius:8px;
    margin-bottom:8px;
}
</style>""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(f"""<div style="display:flex;justify-content:space-between;align-items:center;
    padding:10px 0 14px;border-bottom:2px solid #1c3a58;margin-bottom:20px;">
  <span style="font-family:monospace;font-size:1.3rem;color:#00bfff;
        letter-spacing:3px;font-weight:bold;">◈ AI MARKET ANALYST
    <span style="font-size:.75rem;color:#3a6080;margin-left:12px;">
      由 Claude Opus 4.6 驅動
    </span>
  </span>
  <span style="font-family:monospace;font-size:.7rem;color:#3a6080;">
    {datetime.now().strftime('%Y-%m-%d %H:%M')}
  </span>
</div>""", unsafe_allow_html=True)

# ── Load MarketAnalyst ────────────────────────────────────────────────────────
try:
    from src.dashboard.agents import MarketAnalyst, build_context
    analyst = MarketAnalyst()
    analyst_ok = True
except EnvironmentError as e:
    st.error(f"⚠️ {e}")
    st.info("請在 `.env` 中設定 `ANTHROPIC_API_KEY=sk-ant-...` 後重新啟動 server。")
    analyst_ok = False
    st.stop()
except Exception as e:
    st.error(f"初始化失敗：{e}")
    analyst_ok = False
    st.stop()

# ── Fetch Market Data (reuse cached functions from indicators page) ────────────

@st.cache_data(ttl=600)
def _get_vix_current():
    try:
        resp = requests.get(
            'https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv',
            timeout=10
        )
        df = pd.read_csv(StringIO(resp.text))
        curr = round(float(df.iloc[-1]['CLOSE']), 2)
        prev = round(float(df.iloc[-2]['CLOSE']), 2)
        change = round(curr - prev, 2)
        return {'value': curr, 'change': change, 'pct': round(change / prev * 100, 2)}
    except Exception:
        return None

@st.cache_data(ttl=60)
def _get_taiwan_vix():
    try:
        r = requests.post(
            'https://mis.taifex.com.tw/futures/api/getQuoteListVIX',
            json={},
            headers={'User-Agent': 'Mozilla/5.0',
                     'Content-Type': 'application/json',
                     'Referer': 'https://mis.taifex.com.tw/futures/VolatilityQuotes/'},
            timeout=10
        )
        quotes = r.json().get('RtData', {}).get('QuoteList', [])
        if quotes:
            q = quotes[0]
            val = float(q.get('CLastPrice', 0))
            return {'value': val,
                    'change': float(q.get('CDiff', 0)),
                    'pct': float(q.get('CDiffRate', 0)) * 100,
                    'ref': float(q.get('CRefPrice', val))}
    except Exception:
        pass
    return None

@st.cache_data(ttl=1800)
def _get_fear_greed():
    try:
        import fear_and_greed
        current = fear_and_greed.get()
        return {'value': round(current.value, 1), 'description': current.description}
    except Exception:
        return None

@st.cache_data(ttl=3600)
def _get_margin_ratio():
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
        twse_date_raw = ''
        for item in r1.json()[:1]:
            twse_date_raw = item.get('Date', '')
        twse_date = ''
        if len(twse_date_raw) == 7:
            twse_date = f'{int(twse_date_raw[:3]) + 1911}-{twse_date_raw[3:5]}-{twse_date_raw[5:]}'

        start_dt = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
        r3 = requests.get(
            'https://api.finmindtrade.com/api/v4/data',
            params={'dataset': 'TaiwanStockTotalMarginPurchaseShortSale', 'start_date': start_dt},
            timeout=15
        )
        money_rows = [x for x in r3.json().get('data', []) if x.get('name') == 'MarginPurchaseMoney']
        if not money_rows:
            return None
        finmind_date = money_rows[-1].get('date', '')
        denominator = float(money_rows[-1]['TodayBalance'])
        if denominator == 0:
            return None

        r2 = requests.get('https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN', timeout=15)
        margin_rows = r2.json()
        if not margin_rows:
            return None
        keys = list(margin_rows[0].keys())
        code_key = keys[0]
        today_key = next((k for k in keys if '今日餘額' in k), keys[6] if len(keys) > 6 else keys[3])
        prev_key  = next((k for k in keys if '前日餘額' in k), keys[5] if len(keys) > 5 else keys[3])
        balance_key = today_key if (finmind_date == twse_date) else prev_key

        numerator = 0.0
        for item in margin_rows:
            try:
                code = str(item.get(code_key, '')).strip()
                lots = float(str(item.get(balance_key, '0')).replace(',', ''))
                numerator += lots * 1000 * prices.get(code, 0.0)
            except Exception:
                pass
        return {'ratio': numerator / denominator * 100}
    except Exception:
        return None


def _compute_fear_score(vix_us, tw_vix, fg_val, margin_ratio):
    components = []
    if vix_us is not None:
        components.append((min(100, max(0, (vix_us - 10) / 30 * 100)), 0.35))
    if tw_vix is not None:
        components.append((min(100, max(0, (tw_vix - 10) / 40 * 100)), 0.25))
    if fg_val is not None:
        components.append((100 - fg_val, 0.25))
    if margin_ratio is not None:
        components.append((min(100, max(0, (166 - margin_ratio) / 36 * 100)), 0.15))
    if not components:
        return None
    total_w = sum(w for _, w in components)
    return round(sum(s * w for s, w in components) / total_w, 1)


def _fear_label(score):
    if score is None: return "N/A"
    if score >= 75:   return "EXTREME FEAR"
    if score >= 60:   return "FEAR"
    if score >= 40:   return "NEUTRAL"
    if score >= 25:   return "GREED"
    return "EXTREME GREED"

# ── Fetch ─────────────────────────────────────────────────────────────────────
vix_now      = _get_vix_current()
tw_vix       = _get_taiwan_vix()
fg           = _get_fear_greed()
margin_result = _get_margin_ratio()

vix_val      = vix_now['value']       if vix_now       else None
tw_vix_val   = tw_vix['value']        if tw_vix        else None
fg_val       = fg['value']            if fg            else None
margin_ratio = margin_result['ratio'] if margin_result else None

score = _compute_fear_score(vix_val, tw_vix_val, fg_val, margin_ratio)
label = _fear_label(score)

# Build context dict
ctx = build_context(vix_now, tw_vix, fg, margin_result, score, label)

# ── Current Indicators Strip ──────────────────────────────────────────────────
st.markdown("**📊 當前指標快覽**")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("綜合恐慌指數", f"{score:.1f}" if score else "N/A", label)
c2.metric("US VIX", ctx["vix"], ctx["vix_chg"])
c3.metric("TW VIX", ctx["tw_vix"], ctx["tw_vix_chg"])
c4.metric("Fear & Greed", ctx["fg"], ctx.get("fg_desc", ""))
c5.metric("融資維持率", f"{ctx['margin']}%")

st.divider()

# ── Session State ─────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

if "context_injected" not in st.session_state:
    st.session_state.context_injected = False

# ── Auto-Analyze Button ────────────────────────────────────────────────────────
col_btn1, col_btn2, _ = st.columns([1, 1, 4])

with col_btn1:
    run_auto = st.button("🔍 自動分析", type="primary", use_container_width=True)

with col_btn2:
    if st.button("🗑️ 清除對話", use_container_width=True):
        st.session_state.messages = []
        st.session_state.context_injected = False

if run_auto:
    from src.dashboard.agents.config import build_auto_prompt
    prompt_text = build_auto_prompt(ctx)
    st.session_state.messages.append({"role": "user", "content": prompt_text})
    st.session_state.context_injected = True

# ── Chat History ──────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    display_content = msg["content"]
    # Shorten auto-analysis prompts for display
    if msg["role"] == "user" and "[當前市場數據]" in display_content:
        display_content = "(市場數據已注入) " + display_content.split("\n\n", 1)[-1][:80] + "..."
    elif msg["role"] == "user" and "┌─────" in display_content:
        display_content = "📊 自動市場分析請求"

    with st.chat_message(msg["role"]):
        st.markdown(display_content)

# ── Generate Response If Last Message Is From User ────────────────────────────
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    # Build message list for API — inject context into first user message
    api_messages = []
    for i, msg in enumerate(st.session_state.messages):
        content = msg["content"]
        if i == 0 and not st.session_state.context_injected:
            content = analyst.context_block(ctx) + content
        api_messages.append({"role": msg["role"], "content": content})

    with st.chat_message("assistant"):
        response_text = st.write_stream(analyst.stream(api_messages))

    st.session_state.messages.append({"role": "assistant", "content": response_text})

# ── Chat Input ────────────────────────────────────────────────────────────────
if user_input := st.chat_input("問我任何關於目前市場的問題..."):
    # Inject context on first user message
    content = user_input
    if not st.session_state.messages:
        content = analyst.context_block(ctx) + user_input
        st.session_state.context_injected = True

    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.chat_message("user"):
        st.markdown(user_input)

    api_messages = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[:-1]]
    api_messages.append({"role": "user", "content": content})

    with st.chat_message("assistant"):
        response_text = st.write_stream(analyst.stream(api_messages))

    st.session_state.messages.append({"role": "assistant", "content": response_text})

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "💡 由 **Claude Opus 4.6 + Adaptive Thinking** 驅動 · "
    "市場數據自動注入對話上下文 · "
    "分析僅供參考，不構成投資建議"
)
