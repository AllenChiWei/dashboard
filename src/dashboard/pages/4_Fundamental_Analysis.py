import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from dotenv import load_dotenv
import finlab
from finlab import data

load_dotenv()

st.set_page_config(page_title="基本面分析", page_icon="📊", layout="wide")

# ── FinLab login ──────────────────────────────────────────────────────────────
@st.cache_resource
def init_finlab():
    finlab.login(os.getenv("FINLAB_API_KEY", ""))

init_finlab()

# ── Load stock name→code mapping ──────────────────────────────────────────────
@st.cache_data(ttl=86400)
def get_stock_map():
    """Returns dict {name: code} and list of 'CODE 名稱' display strings."""
    close = data.get("price:收盤價")
    # FinLab stock_info gives Chinese names
    try:
        info = data.get("company_basic_info")
        if "公司簡稱" in info.columns and "stock_id" in info.columns:
            mapping = dict(zip(info["公司簡稱"], info["stock_id"]))
        elif "stock_id" in info.columns:
            mapping = {str(c): c for c in info["stock_id"]}
        else:
            mapping = {}
    except Exception:
        mapping = {}
    codes = sorted(close.columns.tolist())
    # Build display: "0050 元大台灣50"
    name_to_code = {v: k for k, v in mapping.items()}  # code → name
    display = []
    for c in codes:
        nm = mapping.get(c, "")
        display.append(f"{c} {nm}" if nm else c)
    return codes, display, mapping, name_to_code

@st.cache_data(ttl=3600)
def get_fundamentals(symbol: str):
    """Load all fundamental series for a given stock code."""
    result = {}
    def safe_get(key):
        try:
            df = data.get(key)
            if symbol in df.columns:
                return df[symbol].dropna()
        except Exception:
            pass
        return pd.Series(dtype=float)

    result["roe"]       = safe_get("financial_statement:股東權益報酬率")
    result["gross"]     = safe_get("financial_statement:毛利率")
    result["eps"]       = safe_get("financial_statement:每股盈餘")
    result["revenue"]   = safe_get("monthly_revenue:當月營收")
    result["yoy"]       = safe_get("monthly_revenue:去年同月增減(%)")
    result["mom"]       = safe_get("monthly_revenue:上月比較增減(%)")
    return result

# ── Helpers ───────────────────────────────────────────────────────────────────
def last_n(series: pd.Series, n: int) -> pd.Series:
    return series.iloc[-n:] if len(series) >= n else series

def fmt_val(v, suffix="", decimals=2):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "N/A"
    return f"{v:.{decimals}f}{suffix}"

def trend_arrow(series: pd.Series):
    if len(series) < 2:
        return ""
    delta = series.iloc[-1] - series.iloc[-2]
    if delta > 0:
        return "↑"
    elif delta < 0:
        return "↓"
    return "→"

def color_arrow(val):
    if val is None or pd.isna(val):
        return "gray"
    return "#ff4b4b" if val >= 0 else "#00cc66"

def quarter_label(idx):
    """Convert a date index to 'YYYYQN' label."""
    try:
        d = pd.Timestamp(idx)
        q = (d.month - 1) // 3 + 1
        return f"{d.year}Q{q}"
    except Exception:
        return str(idx)[:7]

def month_label(idx):
    try:
        d = pd.Timestamp(idx)
        return f"{d.year}/{d.month:02d}"
    except Exception:
        return str(idx)[:7]

# ── Summary cards (近4季 / 近6月) ─────────────────────────────────────────────
def render_quarter_card(label, series, suffix="%", decimals=2):
    s4 = last_n(series, 4)
    if s4.empty:
        st.markdown(f"**{label}**: N/A")
        return
    latest = s4.iloc[-1]
    arrow = trend_arrow(s4)
    col = color_arrow(latest)
    quarters = " · ".join(
        f"{quarter_label(i)}: {fmt_val(v, suffix, decimals)}"
        for i, v in s4.items()
    )
    st.markdown(
        f"""<div style='background:#1e2130;border-radius:8px;padding:12px 16px;margin-bottom:8px'>
        <span style='font-size:13px;color:#aaa'>{label}</span><br>
        <span style='font-size:22px;font-weight:700;color:{col}'>{fmt_val(latest, suffix, decimals)}</span>
        <span style='font-size:18px;color:{col};margin-left:6px'>{arrow}</span><br>
        <span style='font-size:11px;color:#888'>{quarters}</span>
        </div>""",
        unsafe_allow_html=True,
    )

def render_revenue_card(rev, yoy, mom):
    if rev.empty:
        st.markdown("**營收**: N/A")
        return
    latest_rev = rev.iloc[-1]
    latest_yoy = yoy.iloc[-1] if not yoy.empty else None
    latest_mom = mom.iloc[-1] if not mom.empty else None
    yoy_col = color_arrow(latest_yoy)
    mom_col = color_arrow(latest_mom)
    rev_m = f"{latest_rev/1e8:.2f}億" if latest_rev >= 1e8 else f"{latest_rev/1e4:.2f}萬"
    st.markdown(
        f"""<div style='background:#1e2130;border-radius:8px;padding:12px 16px;margin-bottom:8px'>
        <span style='font-size:13px;color:#aaa'>最新月營收</span><br>
        <span style='font-size:22px;font-weight:700;color:#e0e0e0'>{rev_m}</span><br>
        <span style='font-size:13px;color:{yoy_col}'>YoY {fmt_val(latest_yoy, '%')}</span>
        &nbsp;&nbsp;
        <span style='font-size:13px;color:{mom_col}'>MoM {fmt_val(latest_mom, '%')}</span>
        </div>""",
        unsafe_allow_html=True,
    )

# ── Chart builders ─────────────────────────────────────────────────────────────
def bar_chart(series, title, suffix="", color="#4c9be8", n=16):
    s = last_n(series, n)
    labels = [quarter_label(i) for i in s.index]
    fig = go.Figure(go.Bar(
        x=labels, y=s.values,
        marker_color=color,
        text=[fmt_val(v, suffix) for v in s.values],
        textposition="outside",
    ))
    fig.update_layout(
        title=title,
        template="plotly_dark",
        height=300,
        margin=dict(t=40, b=30, l=40, r=20),
        yaxis_title=suffix or "",
        xaxis=dict(type="category"),
    )
    return fig

def revenue_chart(rev, yoy, mom, n=24):
    rev_s = last_n(rev, n)
    yoy_s = yoy.reindex(rev_s.index)
    mom_s = mom.reindex(rev_s.index)
    labels = [month_label(i) for i in rev_s.index]

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=labels, y=rev_s.values / 1e8,
        name="月營收(億)", marker_color="#4c9be8", opacity=0.8
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=labels, y=yoy_s.values,
        name="YoY%", mode="lines+markers",
        line=dict(color="#ff6b6b", width=2)
    ), secondary_y=True)
    fig.add_trace(go.Scatter(
        x=labels, y=mom_s.values,
        name="MoM%", mode="lines+markers",
        line=dict(color="#ffd166", width=1.5, dash="dash")
    ), secondary_y=True)
    fig.add_hline(y=0, line_dash="dot", line_color="gray", secondary_y=True)
    fig.update_layout(
        title="月營收趨勢",
        template="plotly_dark",
        height=360,
        margin=dict(t=40, b=30, l=40, r=40),
        xaxis=dict(type="category", tickangle=-45),
        legend=dict(orientation="h", y=1.08),
    )
    fig.update_yaxes(title_text="億元", secondary_y=False)
    fig.update_yaxes(title_text="%", secondary_y=True)
    return fig

def eps_quarterly_chart(eps, n=12):
    s = last_n(eps, n)
    colors = ["#ff4b4b" if v >= 0 else "#00cc66" for v in s.values]
    labels = [quarter_label(i) for i in s.index]
    fig = go.Figure(go.Bar(
        x=labels, y=s.values,
        marker_color=colors,
        text=[fmt_val(v) for v in s.values],
        textposition="outside",
    ))
    fig.update_layout(
        title="季EPS",
        template="plotly_dark",
        height=300,
        margin=dict(t=40, b=30, l=40, r=20),
        xaxis=dict(type="category"),
        yaxis_title="元",
    )
    return fig

# ── Page layout ────────────────────────────────────────────────────────────────
st.title("📊 基本面分析")

with st.spinner("載入股票清單…"):
    codes, display_list, mapping, name_to_code = get_stock_map()

# Search bar
search_input = st.text_input("輸入股票代號或名稱", placeholder="例：2330 或 台積電")

matched_code = None
if search_input.strip():
    q = search_input.strip()
    # Exact code match
    if q in codes:
        matched_code = q
    # Code prefix
    elif any(c.startswith(q) for c in codes):
        matched_code = next(c for c in codes if c.startswith(q))
    else:
        # Name match
        for nm, cd in mapping.items():
            if q in nm:
                matched_code = cd
                break

# Fallback: selectbox
if matched_code is None:
    col_search, col_select = st.columns([2, 3])
    with col_select:
        default_idx = 0
        selected_display = st.selectbox("或從清單選擇", display_list, index=default_idx)
        matched_code = selected_display.split()[0]

if not matched_code:
    st.info("請輸入股票代號或名稱以查看基本面資料。")
    st.stop()

# Show stock name
stock_name = name_to_code.get(matched_code, "")
st.subheader(f"{matched_code} {stock_name}")

with st.spinner(f"載入 {matched_code} 基本面資料…"):
    fd = get_fundamentals(matched_code)

roe   = fd["roe"]
gross = fd["gross"]
eps   = fd["eps"]
rev   = fd["revenue"]
yoy   = fd["yoy"]
mom   = fd["mom"]

# ── Summary row ───────────────────────────────────────────────────────────────
st.markdown("### 近況一覽")
c1, c2, c3, c4 = st.columns(4)
with c1:
    render_quarter_card("ROE（股東權益報酬率）", roe, suffix="%")
with c2:
    render_quarter_card("毛利率", gross, suffix="%")
with c3:
    render_quarter_card("每股盈餘 EPS", eps, suffix=" 元", decimals=2)
with c4:
    render_revenue_card(rev, yoy, mom)

st.divider()

# ── Expand: full trend charts ──────────────────────────────────────────────────
with st.expander("📈 點擊展開完整走勢圖", expanded=False):
    tab1, tab2, tab3, tab4 = st.tabs(["ROE", "毛利率", "EPS", "月營收"])

    with tab1:
        if not roe.empty:
            st.plotly_chart(bar_chart(roe, "ROE 歷史走勢", suffix="%", color="#4c9be8", n=20), use_container_width=True)
        else:
            st.warning("無 ROE 資料")

    with tab2:
        if not gross.empty:
            st.plotly_chart(bar_chart(gross, "毛利率 歷史走勢", suffix="%", color="#9b59b6", n=20), use_container_width=True)
        else:
            st.warning("無毛利率資料")

    with tab3:
        if not eps.empty:
            st.plotly_chart(eps_quarterly_chart(eps, n=20), use_container_width=True)
        else:
            st.warning("無 EPS 資料")

    with tab4:
        if not rev.empty:
            st.plotly_chart(revenue_chart(rev, yoy, mom, n=36), use_container_width=True)
        else:
            st.warning("無月營收資料")

st.divider()

# ── Raw data table ─────────────────────────────────────────────────────────────
with st.expander("📋 原始數據表"):
    tab_a, tab_b = st.tabs(["季報", "月營收"])
    with tab_a:
        q_df = pd.DataFrame({
            "季度": [quarter_label(i) for i in last_n(roe, 12).index] if not roe.empty else [],
            "ROE(%)": last_n(roe, 12).values if not roe.empty else [],
            "毛利率(%)": last_n(gross, 12).reindex(last_n(roe, 12).index).values if not gross.empty and not roe.empty else [],
            "EPS(元)": last_n(eps, 12).reindex(last_n(roe, 12).index).values if not eps.empty and not roe.empty else [],
        })
        st.dataframe(q_df.set_index("季度"), use_container_width=True)
    with tab_b:
        rev12 = last_n(rev, 24)
        r_df = pd.DataFrame({
            "月份": [month_label(i) for i in rev12.index],
            "月營收(億)": (rev12.values / 1e8).round(2),
            "YoY(%)": yoy.reindex(rev12.index).round(2).values if not yoy.empty else [],
            "MoM(%)": mom.reindex(rev12.index).round(2).values if not mom.empty else [],
        })
        st.dataframe(r_df.set_index("月份"), use_container_width=True)

st.caption("資料來源：FinLab，僅供參考，不構成投資建議。")
