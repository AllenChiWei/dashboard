import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from dotenv import load_dotenv
import finlab
from finlab import data

load_dotenv()

st.set_page_config(page_title="月營收排名", page_icon="📋", layout="wide")

st.markdown("""
<style>
body, .stApp { background-color: #0e1117; color: #e0e0e0; }
.metric-card {
    background: #1e2130; border-radius: 8px; padding: 12px 16px;
    text-align: center; margin-bottom: 8px;
}
.block-container { padding-top: 1.5rem; }
[data-testid="stDataFrame"] { border-radius: 8px; }
[data-testid="stMetricLabel"] { color: #ffffff !important; }
[data-testid="stMetricValue"] { color: #ffffff !important; }
[data-testid="stMetricDelta"] { color: #ffffff !important; }
</style>
""", unsafe_allow_html=True)

# ── FinLab login ───────────────────────────────────────────────────────────────
@st.cache_resource
def init_finlab():
    finlab.login(os.getenv("FINLAB_API_KEY", ""))

init_finlab()

# ── Data fetch ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_revenue_data():
    with data.universe(market="TSE_OTC"):
        rev_yoy  = data.get("monthly_revenue:去年同月增減(%)")
        rev_mom  = data.get("monthly_revenue:上月比較增減(%)")
        rev_amt  = data.get("monthly_revenue:當月營收")          # 千元
        info     = data.get("company_basic_info")

    last_date = rev_yoy.T.columns[-1]

    # Extract latest period values
    yoy_series = rev_yoy.T[last_date].dropna()
    mom_series = rev_mom.T[last_date].dropna()
    amt_series = rev_amt.T[last_date].dropna()

    # Build name / industry lookup from info
    id_to_name = {}
    id_to_industry = {}
    if "stock_id" in info.columns:
        for _, row in info[["stock_id", "公司簡稱", "產業類別"]].iterrows():
            sid = str(row["stock_id"])
            id_to_name[sid]     = row.get("公司簡稱", "")
            id_to_industry[sid] = row.get("產業類別", "")

    # Union of all codes
    all_codes = yoy_series.index.union(mom_series.index)

    rows = []
    for code in all_codes:
        rows.append({
            "代號":   code,
            "名稱":   id_to_name.get(str(code), ""),
            "產業":   id_to_industry.get(str(code), ""),
            "當月營收(億)": round(amt_series.get(code, float("nan")) / 1e5, 2),
            "年增率(%)": round(yoy_series.get(code, float("nan")), 2),
            "月增率(%)": round(mom_series.get(code, float("nan")), 2),
        })

    df = pd.DataFrame(rows)
    return df, last_date


# ── Load ───────────────────────────────────────────────────────────────────────
with st.spinner("載入月營收資料…"):
    df, last_date = load_revenue_data()

date_str = pd.Timestamp(last_date).strftime("%Y-%m")

st.title("📋 月營收排名")
st.caption(f"資料日期：**{date_str}**　｜　TSE + OTC 全市場　｜　資料來源：FinLab / 公開資訊觀測站")

# ── Sidebar filters ────────────────────────────────────────────────────────────
st.sidebar.header("篩選條件")

industries = sorted(df["產業"].dropna().unique().tolist())
industries = [i for i in industries if i]
sel_industries = st.sidebar.multiselect("產業類別", options=industries, default=[])

min_rev = st.sidebar.number_input("最低當月營收（億）", min_value=0.0, value=0.0, step=1.0)

min_yoy = st.sidebar.number_input("年增率門檻（%）≥", min_value=-999.0, value=20.0, step=5.0)
min_mom = st.sidebar.number_input("月增率門檻（%）≥", min_value=-999.0, value=0.0, step=5.0)

show_top = st.sidebar.selectbox("顯示筆數", options=[50, 100, 200, 500, 0], index=4,
                                 format_func=lambda x: "全部" if x == 0 else f"Top {x}")

search_kw = st.sidebar.text_input("搜尋代號 / 名稱", placeholder="e.g. 2330 or 台積電")

# ── Apply filters ──────────────────────────────────────────────────────────────
filtered = df.copy()
filtered = filtered[filtered["當月營收(億)"].fillna(0) >= min_rev]
if not search_kw.strip():   # bypass growth filters when searching by code/name
    filtered = filtered[filtered["年增率(%)"].fillna(-999) >= min_yoy]
    filtered = filtered[filtered["月增率(%)"].fillna(-999) >= min_mom]

if sel_industries:
    filtered = filtered[filtered["產業"].isin(sel_industries)]

if search_kw.strip():
    kw = search_kw.strip()
    mask = (filtered["代號"].astype(str).str.contains(kw, case=False) |
            filtered["名稱"].str.contains(kw, case=False, na=False))
    filtered = filtered[mask]

# Base df for "最低" ranking: apply revenue & industry filters but NOT yoy/mom thresholds
filtered_base = df.copy()
filtered_base = filtered_base[filtered_base["當月營收(億)"].fillna(0) >= min_rev]
if sel_industries:
    filtered_base = filtered_base[filtered_base["產業"].isin(sel_industries)]

# ── Summary metrics ────────────────────────────────────────────────────────────
valid_yoy = filtered["年增率(%)"].dropna()
valid_mom = filtered["月增率(%)"].dropna()

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("總家數", f"{len(filtered):,}")
col2.metric("年增率 > 0", f"{(valid_yoy > 0).sum():,} 家")
col3.metric("年增率中位數", f"{valid_yoy.median():.1f}%")
col4.metric("月增率 > 0", f"{(valid_mom > 0).sum():,} 家")
col5.metric("月增率中位數", f"{valid_mom.median():.1f}%")

st.divider()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_yoy, tab_mom = st.tabs(["📈 年增率排名", "📊 月增率排名"])

def color_growth(val):
    """Color positive green, negative red for styling."""
    if pd.isna(val):
        return "color: #888"
    return "color: #ef5350; font-weight:600" if val > 0 else "color: #26a69a; font-weight:600"

def render_tab(sort_col: str, chart_label: str):
    sorted_df = filtered.dropna(subset=[sort_col]).sort_values(sort_col, ascending=False)
    sorted_df = sorted_df.reset_index(drop=True)
    sorted_df.index += 1   # rank from 1

    top_df = sorted_df.head(show_top) if show_top > 0 else sorted_df

    # 最低: sort ascending from full base (no yoy/mom threshold), take bottom 100
    base_sorted = filtered_base.dropna(subset=[sort_col]).sort_values(sort_col, ascending=True)
    base_sorted = base_sorted.reset_index(drop=True)
    base_sorted.index += 1
    bottom_df = base_sorted.head(100)

    # Bar chart: top & bottom N
    n_chart = min(30, show_top if show_top > 0 else 30)
    top_n    = sorted_df.head(n_chart)
    bottom_n = sorted_df.tail(n_chart).iloc[::-1]
    chart_df = pd.concat([top_n, bottom_n]).drop_duplicates(subset=["代號"])

    fig = go.Figure()
    colors = ["#ef5350" if v >= 0 else "#26a69a" for v in chart_df[sort_col]]
    fig.add_trace(go.Bar(
        x=chart_df["代號"] + " " + chart_df["名稱"].fillna(""),
        y=chart_df[sort_col],
        marker_color=colors,
        hovertemplate=(
            "<b>%{x}</b><br>"
            f"{chart_label}: %{{y:.1f}}%<br>"
            "當月營收: %{customdata:.2f} 億<extra></extra>"
        ),
        customdata=chart_df["當月營收(億)"],
    ))
    fig.add_hline(y=0, line_color="#555", line_width=1)
    fig.update_layout(
        title=f"前後 {n_chart} 名 {chart_label}（{date_str}）",
        template="plotly_dark",
        height=380,
        xaxis=dict(tickangle=-45, tickfont=dict(size=10)),
        yaxis_title=chart_label,
        showlegend=False,
        margin=dict(b=120),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Tables: top & bottom side by side
    display_cols = ["代號", "名稱", "產業", "當月營收(億)", "年增率(%)", "月增率(%)"]

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"#### 🔺 {chart_label} 最高（{len(top_df)} 筆）")
        st.dataframe(
            top_df[display_cols].style
                .applymap(color_growth, subset=["年增率(%)", "月增率(%)"]),
            use_container_width=True,
            height=500,
        )
    with c2:
        if not bottom_df.empty:
            st.markdown(f"#### 🔻 {chart_label} 最低（{len(bottom_df)} 筆）")
            st.dataframe(
                bottom_df[display_cols].style
                    .applymap(color_growth, subset=["年增率(%)", "月增率(%)"]),
                use_container_width=True,
                height=500,
            )

with tab_yoy:
    render_tab("年增率(%)", "營收年增率")

with tab_mom:
    render_tab("月增率(%)", "營收月增率")

# ── Full data download ─────────────────────────────────────────────────────────
st.divider()
with st.expander("📥 下載完整資料"):
    full_sorted = filtered.sort_values("年增率(%)", ascending=False).reset_index(drop=True)
    st.dataframe(full_sorted, use_container_width=True, height=400)
    csv = full_sorted.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        label="下載 CSV",
        data=csv,
        file_name=f"revenue_ranking_{date_str}.csv",
        mime="text/csv",
    )
