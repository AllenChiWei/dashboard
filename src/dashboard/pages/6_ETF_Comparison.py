import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from dotenv import load_dotenv
import finlab
from finlab import data

load_dotenv()

st.set_page_config(page_title="ETF 績效比較", page_icon="📊", layout="wide")

# ── FinLab login ──────────────────────────────────────────────────────────────
@st.cache_resource
def init_finlab():
    finlab.login(os.getenv("FINLAB_API_KEY", ""))

init_finlab()

# ── Load all price data & ETF list ────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_price_all():
    return data.get("price:收盤價")


@st.cache_data(ttl=3600)
def load_adj_price_all():
    """Load FinLab dividend-adjusted (還原權值) close prices (etl:adj_close)."""
    return data.get("etl:adj_close")

@st.cache_data(ttl=86400)
def get_etf_list(_close_df: pd.DataFrame):
    """Return (etf_codes, code_to_name_dict) for all '00*' stocks."""
    code_to_name = {}
    try:
        info = data.get("company_basic_info")
        name_col = next((c for c in ["公司簡稱", "name"] if c in info.columns), None)
        if name_col:
            if "stock_id" in info.columns:
                code_to_name = dict(zip(info["stock_id"].astype(str), info[name_col]))
            else:
                code_to_name = {str(idx): row[name_col] for idx, row in info.iterrows()}
    except Exception:
        pass

    etf_codes = sorted([c for c in _close_df.columns if str(c).startswith("00")])
    return etf_codes, code_to_name

# ── Color palette for up to 12 ETFs ──────────────────────────────────────────
COLORS = [
    "#4c9be8", "#ff6b6b", "#ffd166", "#06d6a0",
    "#a29bfe", "#fd79a8", "#55efc4", "#fdcb6e",
    "#e17055", "#74b9ff", "#b2bec3", "#00cec9",
]

# ── Helpers ───────────────────────────────────────────────────────────────────
def get_price_series(close_df: pd.DataFrame, code: str) -> pd.Series:
    if code in close_df.columns:
        return close_df[code].dropna()
    return pd.Series(dtype=float)

def build_comparison(price_df: pd.DataFrame, codes: list[str]) -> pd.DataFrame:
    """
    Align all selected ETFs to the shortest common history.
    Start date = max of each ETF's first valid date in price_df.
    Returns DataFrame indexed to 100 at start.
    """
    series_map = {c: get_price_series(price_df, c) for c in codes}
    series_map = {c: s for c, s in series_map.items() if not s.empty}
    if not series_map:
        return pd.DataFrame()

    # Common start = latest first date → shortest ETF sets the anchor
    start_date = max(s.index[0] for s in series_map.values())

    trimmed = {c: s[s.index >= start_date] for c, s in series_map.items()
               if not s[s.index >= start_date].empty}
    if not trimmed:
        return pd.DataFrame()

    df = pd.DataFrame(trimmed).sort_index()
    base = df.iloc[0]
    return (df / base * 100).round(4)

def drawdown_series(indexed: pd.Series) -> pd.Series:
    """Max drawdown from rolling peak."""
    peak = indexed.cummax()
    return ((indexed - peak) / peak * 100).round(2)

def hex_to_rgba(hex_color: str, alpha: float = 0.08) -> str:
    """Convert '#rrggbb' hex color to 'rgba(r,g,b,a)' string for Plotly."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

# ── Page layout ────────────────────────────────────────────────────────────────
st.title("📊 ETF 績效比較")
st.caption("以最晚上市的 ETF 為共同起始點，比較各 ETF 同期漲跌幅。")

with st.spinner("載入價格資料…"):
    close_df = load_price_all()
    etf_codes, name_map = get_etf_list(close_df)   # name_map: {code: name}

# ── Sidebar: ETF selection ─────────────────────────────────────────────────────
st.sidebar.header("ETF 選擇")

# Build display options: "0050 元大台灣50"
def disp(c):
    nm = name_map.get(c, "")
    return f"{c} {nm}" if nm else c

etf_display = [disp(c) for c in etf_codes]
disp_to_code = {disp(c): c for c in etf_codes}

# Defaults: common large ETFs if present
default_codes = ["0050", "0056", "00878", "00919", "00929"]
default_codes = [c for c in default_codes if c in etf_codes]
default_display = [disp(c) for c in default_codes]

selected_display = st.sidebar.multiselect(
    "選擇 ETF（可多選）",
    options=etf_display,
    default=default_display,
    max_selections=12,
)
selected_codes = [disp_to_code[d] for d in selected_display if d in disp_to_code]

# Also allow manual code entry (for non-ETF comparison)
extra_input = st.sidebar.text_input("手動新增代號（逗號分隔）", placeholder="e.g. 2330, 006208")
if extra_input.strip():
    for code in [x.strip() for x in extra_input.split(",")]:
        if code and code not in selected_codes and code in close_df.columns:
            selected_codes.append(code)

st.sidebar.markdown("---")
show_dd = st.sidebar.checkbox("顯示最大回撤走勢", value=True)
show_table = st.sidebar.checkbox("顯示數據表", value=True)

# ── Main content ───────────────────────────────────────────────────────────────
if len(selected_codes) < 2:
    st.info("請在左側至少選擇 **2 個** ETF 以進行比較。")
    st.stop()

with st.spinner("載入還原權值價格（FinLab etl:adj_close）…"):
    adj_df = load_adj_price_all()

    if not adj_df.empty:
        indexed = build_comparison(adj_df, selected_codes)
        price_label = "還原權值（FinLab etl:adj_close）"
    else:
        # Fallback: FinLab raw prices
        indexed = build_comparison(close_df, selected_codes)
        price_label = "未還原收盤價（FinLab，adj 資料失敗）"

if indexed.empty:
    st.error("無法取得所選 ETF 的價格資料，請確認代號是否正確。")
    st.stop()

start_date = indexed.index[0]
end_date   = indexed.index[-1]
total_days = (end_date - start_date).days
years      = total_days / 365

# Anchor: ETF whose first date determined the comparison start
first_dates = {c: get_price_series(adj_df, c).index[0]
               for c in indexed.columns if c in adj_df.columns}
if not first_dates:
    first_dates = {c: get_price_series(close_df, c).index[0]
                   for c in indexed.columns if c in close_df.columns}
anchor_code = max(first_dates, key=lambda c: first_dates[c])
anchor_name = disp(anchor_code)

st.info(
    f"比較起點：**{start_date.strftime('%Y-%m-%d')}**（由 **{anchor_name}** 上市日決定）"
    f"　 · 　比較天數：{total_days} 天（約 {years:.1f} 年）"
    f"　 · 　價格基準：{price_label}"
)

# ── 績效指標 ──────────────────────────────────────────────────────────────────
st.markdown("### 📈 同期績效")
perf_cols = st.columns(len(indexed.columns))
for i, code in enumerate(indexed.columns):
    s = indexed[code].dropna()
    if s.empty:
        with perf_cols[i]:
            st.markdown(
                f"""<div style='background:#1e2130;border-radius:8px;padding:10px 14px;text-align:center'>
                <div style='font-size:12px;color:#aaa'>{code}</div>
                <div style='font-size:14px;color:#888;margin-top:8px'>無資料</div>
                </div>""",
                unsafe_allow_html=True,
            )
        continue
    total_ret   = s.iloc[-1] - 100           # indexed starts at 100
    dd_s        = drawdown_series(s)
    max_dd      = dd_s.min()
    ann_ret     = ((s.iloc[-1] / 100) ** (1 / years) - 1) * 100 if years > 0 else 0
    color       = "#ff4b4b" if total_ret >= 0 else "#00cc66"
    with perf_cols[i]:
        nm = name_map.get(code, code)
        st.markdown(
            f"""<div style='background:#1e2130;border-radius:8px;padding:10px 14px;text-align:center'>
            <div style='font-size:12px;color:#aaa'>{code}</div>
            <div style='font-size:12px;color:#ccc;margin-bottom:4px'>{nm}</div>
            <div style='font-size:22px;font-weight:700;color:{color}'>{total_ret:+.2f}%</div>
            <div style='font-size:11px;color:#888;margin-top:4px'>
              年化 {ann_ret:+.1f}% &nbsp;|&nbsp; 最大回撤 {max_dd:.1f}%
            </div></div>""",
            unsafe_allow_html=True,
        )

st.divider()

# ── 指數化走勢圖 ─────────────────────────────────────────────────────────────
fig = go.Figure()
for i, code in enumerate(indexed.columns):
    s = indexed[code].dropna()
    if s.empty:
        continue
    color = COLORS[i % len(COLORS)]
    latest = s.iloc[-1] - 100
    label = f"{code} {name_map.get(code, '')}".strip()
    fig.add_trace(go.Scatter(
        x=s.index, y=s.values,
        name=f"{label} ({latest:+.1f}%)",
        line=dict(color=color, width=2),
        hovertemplate=f"<b>{label}</b><br>日期: %{{x|%Y-%m-%d}}<br>指數: %{{y:.2f}}<extra></extra>",
    ))

fig.add_hline(y=100, line_dash="dot", line_color="#555")
fig.update_layout(
    title=f"ETF 同期累積報酬（起點=100，從 {start_date.strftime('%Y-%m-%d')} 起）",
    template="plotly_dark",
    height=480,
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    xaxis_title="日期",
    yaxis_title="指數（起點=100）",
)
st.plotly_chart(fig, use_container_width=True)

# ── 最大回撤走勢圖 ─────────────────────────────────────────────────────────────
if show_dd:
    fig_dd = go.Figure()
    for i, code in enumerate(indexed.columns):
        s = indexed[code].dropna()
        if s.empty:
            continue
        dd = drawdown_series(s)
        color = COLORS[i % len(COLORS)]
        label = f"{code} {name_map.get(code, '')}".strip()
        fig_dd.add_trace(go.Scatter(
            x=dd.index, y=dd.values,
            name=label,
            line=dict(color=color, width=1.5),
            fill="tozeroy",
            fillcolor=hex_to_rgba(color),
            hovertemplate=f"<b>{label}</b><br>日期: %{{x|%Y-%m-%d}}<br>回撤: %{{y:.2f}}%<extra></extra>",
        ))
    fig_dd.update_layout(
        title="最大回撤走勢",
        template="plotly_dark",
        height=320,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis_title="日期",
        yaxis_title="回撤%",
        yaxis=dict(tickformat=".1f"),
    )
    st.plotly_chart(fig_dd, use_container_width=True)

# ── 數據表 ─────────────────────────────────────────────────────────────────────
if show_table:
    with st.expander("📋 每月指數數據表"):
        # Resample to month-end
        monthly = indexed.resample("ME").last().round(2)
        monthly.index = monthly.index.strftime("%Y-%m")
        # Show change vs previous month
        ret_df = monthly.copy()
        for c in ret_df.columns:
            ret_df[c] = ret_df[c].apply(lambda v: f"{v:.2f}")
        st.dataframe(ret_df, use_container_width=True)

    with st.expander("📊 年度報酬率"):
        yearly = indexed.resample("YE").last()
        yearly_ret = yearly.pct_change().dropna() * 100
        yearly_ret.index = yearly_ret.index.year
        yearly_ret = yearly_ret.round(2)
        # rename columns to display names
        yearly_ret.columns = [f"{c} {name_map.get(c,'')}".strip() for c in yearly_ret.columns]
        # Color positive/negative
        def _style(v):
            if isinstance(v, float):
                color = "#ff4b4b" if v >= 0 else "#00cc66"
                return f"color: {color}"
            return ""
        st.dataframe(yearly_ret.style.applymap(_style).format("{:+.2f}%"), use_container_width=True)

st.caption("資料來源：FinLab · 起點由最晚上市 ETF 決定 · 僅供參考，不構成投資建議。")
