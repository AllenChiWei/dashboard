import os
import re
import calendar as cal
import requests
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from bs4 import BeautifulSoup
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

# ── Fund catalog (MoneyDJ code → display name) ────────────────────────────────
FUND_CATALOG = {
    "ACDD04": "安聯台灣科技基金",
    "ACPS10": "統一奔騰基金",
    "ACPS02": "統一黑馬基金",
    "ACDD01": "安聯台灣大壩基金-A累積型(台幣)",
    "AC0001": "野村鴻運基金",
}

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

@st.cache_data(ttl=3600)
def fetch_moneydj_fund_nav(fund_code: str) -> pd.Series:
    """Fetch fund NAV from MoneyDJ.
    Returns last ~30 trading days of daily NAV + monthly reconstructed data (~12 months).
    """
    _headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.moneydj.com/",
    }

    # ── Step 1: last ~33 trading days (yp010000) ──────────────────────────────
    daily_data: dict[pd.Timestamp, float] = {}
    ref = pd.Timestamp.now()
    try:
        r = requests.get(
            f"https://www.moneydj.com/funddj/ya/yp010000.djhtm?a={fund_code}",
            headers=_headers, timeout=15)
        soup = BeautifulSoup(r.content.decode("cp950", errors="replace"), "html.parser")
        tables = soup.find_all("table")
        if len(tables) > 4:
            for row in tables[4].find_all("tr")[2:]:
                cells = row.find_all("td")
                if len(cells) >= 2:
                    d_str = cells[0].get_text(strip=True)
                    n_str = cells[1].get_text(strip=True).replace(",", "")
                    if "/" in d_str:
                        try:
                            mm, dd = map(int, d_str.split("/"))
                            nav = float(n_str)
                            yr = ref.year if mm <= ref.month else ref.year - 1
                            daily_data[pd.Timestamp(yr, mm, dd)] = nav
                        except Exception:
                            pass
    except Exception:
        pass

    if not daily_data:
        return pd.Series(dtype=float)

    daily_s = pd.Series(daily_data).sort_index()

    # ── Step 2: find last month-end in daily data as anchor ───────────────────
    anchor_date: pd.Timestamp | None = None
    anchor_nav: float | None = None
    for dt in sorted(daily_s.index, reverse=True):
        next_bd = dt + pd.offsets.BDay(1)
        if next_bd.month != dt.month:
            anchor_date = dt
            anchor_nav = float(daily_s[dt])
            break

    if anchor_date is None:
        return daily_s

    # ── Step 3: monthly returns (yp012001 table 9) ────────────────────────────
    monthly_nav: dict[pd.Timestamp, float] = {}
    try:
        r2 = requests.get(
            f"https://www.moneydj.com/funddj/ya/yp012001.djhtm?a={fund_code}",
            headers=_headers, timeout=15)
        soup2 = BeautifulSoup(r2.content.decode("cp950", errors="replace"), "html.parser")

        for table in soup2.find_all("table"):
            rows = table.find_all("tr")
            if len(rows) < 3:
                continue

            row0 = [c.get_text(strip=True) for c in rows[0].find_all(["td", "th"])]
            years = [int(x) for x in row0 if re.match(r"^20\d{2}$", x.strip())]
            if len(years) < 2:
                continue

            row1 = [c.get_text(strip=True) for c in rows[1].find_all(["td", "th"])]
            months = [int(x) for x in row1
                      if re.match(r"^\d{1,2}$", x.strip()) and 1 <= int(x) <= 12]
            if len(months) < 6:
                continue

            row2 = [c.get_text(strip=True) for c in rows[2].find_all(["td", "th"])]
            rets: list[float] = []
            for x in row2:
                try:
                    rets.append(float(x))
                except Exception:
                    pass
            if len(rets) < 6:
                continue

            # Assign years: months are descending within each year; a month > previous → year boundary
            yr_assignments: list[int] = []
            yr_idx = 0
            for j, mv in enumerate(months):
                if j > 0 and mv > months[j - 1] and yr_idx < len(years) - 1:
                    yr_idx += 1
                yr_assignments.append(years[yr_idx])

            # Reconstruct NAV backwards from anchor_date
            cur_nav = anchor_nav
            started = False
            for j, (mv, yr) in enumerate(zip(months, yr_assignments)):
                if yr == anchor_date.year and mv == anchor_date.month:
                    started = True
                if started and j < len(rets):
                    last_day = cal.monthrange(yr, mv)[1]
                    monthly_nav[pd.Timestamp(yr, mv, last_day)] = cur_nav
                    cur_nav = cur_nav / (1 + rets[j] / 100)
            break  # processed monthly table

    except Exception:
        pass

    if monthly_nav:
        monthly_s = pd.Series(monthly_nav).sort_index()
        # Remove monthly points whose month is already covered by daily data
        daily_months = set(daily_s.index.to_period("M"))
        monthly_s = monthly_s[~monthly_s.index.to_period("M").isin(daily_months)]
        return pd.concat([monthly_s, daily_s]).sort_index()

    return daily_s


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
    # Supplement ETF names from tw_etf_basic_info (company_basic_info lacks ETF names)
    try:
        _etf_info = data.get("tw_etf_basic_info")
        name_map.update(dict(zip(_etf_info["stock_id"].astype(str), _etf_info["證券簡稱"])))
    except Exception:
        pass

# ── Sidebar: ETF selection ─────────────────────────────────────────────────────
st.sidebar.header("ETF 選擇")

# Build display options: "0050 元大台灣50"
def disp(c):
    nm = name_map.get(c, "")
    return f"{c} {nm}" if nm else c

etf_display = [disp(c) for c in etf_codes]
disp_to_code = {disp(c): c for c in etf_codes}

# Defaults: common large ETFs if present
default_codes = ["0050", "00981A", "00982A", "00988A", "00992A", "00891", "00830"]
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
st.sidebar.header("基金選擇（MoneyDJ）")
fund_options = list(FUND_CATALOG.keys())
fund_display_map = {f"{c} {n}": c for c, n in FUND_CATALOG.items()}
fund_display_options = list(fund_display_map.keys())
selected_fund_display = st.sidebar.multiselect(
    "選擇基金（可多選）",
    options=fund_display_options,
    default=fund_display_options,  # all selected by default
)
selected_fund_codes = [fund_display_map[d] for d in selected_fund_display]

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

# ── Merge fund NAV into indexed ────────────────────────────────────────────────
if selected_fund_codes:
    with st.spinner("載入基金淨值（MoneyDJ）…"):
        for fund_code in selected_fund_codes:
            nav_s = fetch_moneydj_fund_nav(fund_code)
            if nav_s.empty:
                st.warning(f"無法取得 {FUND_CATALOG.get(fund_code, fund_code)} 淨值資料")
                continue

            # Find base NAV: last available point at or before start_date
            pre = nav_s[nav_s.index <= start_date]
            post = nav_s[nav_s.index > start_date]
            if not pre.empty:
                base_nav = float(pre.iloc[-1])
            elif not post.empty:
                base_nav = float(post.iloc[0])
            else:
                continue

            # Normalize and forward-fill onto indexed date range
            full_idx = indexed.index.union(nav_s.index).sort_values()
            ratio_ext = (nav_s / base_nav * 100).reindex(full_idx).ffill()
            fund_col = ratio_ext.reindex(indexed.index)

            # Set NaN before fund's actual first date if fund starts after start_date
            if pre.empty and not post.empty:
                fund_col[indexed.index < post.index[0]] = float("nan")

            indexed[fund_code] = fund_col
            name_map[fund_code] = FUND_CATALOG[fund_code]

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
# Sort codes by total return descending (best → worst, left → right)
def _total_ret(code):
    s = indexed[code].dropna()
    return s.iloc[-1] - 100 if not s.empty else float("-inf")
sorted_codes = sorted(indexed.columns, key=_total_ret, reverse=True)

# Build all cards in a single HTML block so CSS grid can unify heights
card_items = []
for code in sorted_codes:
    s = indexed[code].dropna()
    nm = name_map.get(code, code)
    if s.empty:
        card_items.append(
            f"<div class='pcard'>"
            f"<div class='pcode'>{code}</div>"
            f"<div class='pname'>{nm}</div>"
            f"<div class='pret' style='color:#888'>無資料</div>"
            f"<div class='psub'>&nbsp;</div>"
            f"</div>"
        )
        continue
    total_ret = s.iloc[-1] - 100
    dd_s      = drawdown_series(s)
    max_dd    = dd_s.min()
    ann_ret   = ((s.iloc[-1] / 100) ** (1 / years) - 1) * 100 if years > 0 else 0
    color     = "#ff4b4b" if total_ret >= 0 else "#00cc66"
    card_items.append(
        f"<div class='pcard'>"
        f"<div class='pcode'>{code}</div>"
        f"<div class='pname'>{nm}</div>"
        f"<div class='pret' style='color:{color}'>{total_ret:+.2f}%</div>"
        f"<div class='psub'>年化 {ann_ret:+.1f}% | 最大回撤 {max_dd:.1f}%</div>"
        f"</div>"
    )

n_cols = len(sorted_codes)
st.markdown(
    f"""
<style>
.pgrid {{
    display: grid;
    grid-template-columns: repeat({n_cols}, 1fr);
    gap: 8px;
    align-items: stretch;
}}
.pcard {{
    background: #1e2130;
    border-radius: 8px;
    padding: 10px 14px;
    text-align: center;
    display: flex;
    flex-direction: column;
    justify-content: center;
}}
.pcode {{ font-size: 12px; color: #aaa; }}
.pname {{ font-size: 12px; color: #ccc; margin: 4px 0; word-break: break-all; }}
.pret  {{ font-size: 22px; font-weight: 700; margin: 4px 0; }}
.psub  {{ font-size: 11px; color: #888; margin-top: 4px; }}
</style>
<div class='pgrid'>{''.join(card_items)}</div>
""",
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

st.caption("ETF 資料來源：FinLab（還原權值）· 基金淨值來源：MoneyDJ（近一年月資料 + 近 30 日日資料）· 僅供參考，不構成投資建議。")
