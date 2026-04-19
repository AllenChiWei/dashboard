import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from dotenv import load_dotenv
import finlab
from finlab import data

load_dotenv()

st.set_page_config(page_title="可轉債資料", page_icon="📄", layout="wide")

st.markdown("""
<style>
body, .stApp { background-color: #0e1117; color: #e0e0e0; }
.block-container { padding-top: 1.5rem; }
[data-testid="stDataFrame"] { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)

# ── FinLab login ────────────────────────────────────────────────────────────────
@st.cache_resource
def init_finlab():
    finlab.login(os.getenv("FINLAB_API_KEY", ""))

init_finlab()

# ── Data fetch ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_cb_data():
    """Load CB info from FinLab cb_published_info (1 row per CB per day → deduplicate)."""
    cb_info      = data.get("cb_published_info")
    company_info = data.get("company_basic_info")
    close_prices = data.get("price:收盤價")  # DatetimeIndex × stock_code

    # Latest stock prices (Series: stock_code → price)
    latest_prices  = close_prices.iloc[-1]
    price_date     = close_prices.index[-1]

    # ── Deduplicate: one row per CB (latest date) ─────────────────────────────
    cb_info["date"] = pd.to_datetime(cb_info["date"], errors="coerce")
    cb_latest = (
        cb_info.sort_values("date")
               .groupby("symbol", as_index=False)
               .last()
    )

    # ── Filter out already-terminated CBs ────────────────────────────────────
    cb_latest["終止櫃檯買賣日"] = pd.to_datetime(cb_latest["終止櫃檯買賣日"], errors="coerce")
    today = pd.Timestamp.today()
    active_mask = cb_latest["終止櫃檯買賣日"].isna() | (cb_latest["終止櫃檯買賣日"] >= today)
    cb_latest = cb_latest[active_mask].copy()

    # ── Build lookup dicts from company_basic_info ────────────────────────────
    id_to_industry = {}
    id_to_name     = {}
    if "stock_id" in company_info.columns:
        for _, row in company_info[["stock_id", "公司簡稱", "產業類別"]].iterrows():
            sid = str(row["stock_id"]).strip()
            id_to_industry[sid] = row.get("產業類別", "")
            id_to_name[sid]     = row.get("公司簡稱", "")

    # ── Build output rows ─────────────────────────────────────────────────────
    rows = []
    for _, row in cb_latest.iterrows():
        cb_code    = str(row["symbol"]).strip()
        stock_code = str(row.get("stock_id", "")).strip()

        # Conversion price
        try:
            conv_price = float(row["轉換價格"])
        except (ValueError, TypeError):
            conv_price = None

        # Current stock price: prefer live FinLab; fall back to CB info field
        current_price = latest_prices.get(stock_code, None)
        if current_price is None or pd.isna(current_price):
            try:
                current_price = float(row["轉換標的股票價格"])
            except (ValueError, TypeError):
                current_price = None

        # CB reference price
        try:
            cb_ref_price = float(row["轉債參考價格"])
        except (ValueError, TypeError):
            cb_ref_price = None

        # 溢價率 = (conv_price - current_stock_price) / current_stock_price × 100
        premium = None
        if conv_price and current_price and current_price > 0:
            premium = round((conv_price - current_price) / current_price * 100, 2)

        # Issue amounts (億)
        def to_bn(val):
            try:
                return round(float(str(val).replace(",", "")) / 1e8, 2)
            except (ValueError, TypeError):
                return None

        maturity_str = ""
        mat_ts = row.get("終止櫃檯買賣日")
        if pd.notna(mat_ts):
            try:
                maturity_str = pd.Timestamp(mat_ts).strftime("%Y-%m-%d")
            except Exception:
                maturity_str = str(mat_ts)

        conv_start = ""
        conv_end   = ""
        try:
            conv_start = pd.Timestamp(row["轉換起日"]).strftime("%Y-%m-%d") if pd.notna(row.get("轉換起日")) else ""
            conv_end   = pd.Timestamp(row["轉換迄日"]).strftime("%Y-%m-%d") if pd.notna(row.get("轉換迄日")) else ""
        except Exception:
            pass

        rows.append({
            "CB代號":       cb_code,
            "CB名稱":       str(row.get("債券簡稱", "")),
            "股票代號":     stock_code,
            "公司名稱":     id_to_name.get(stock_code, ""),
            "產業別":       id_to_industry.get(stock_code, ""),
            "轉換價格":     conv_price,
            "目前股價":     round(current_price, 2) if current_price else None,
            "溢價率(%)":    premium,
            "CB參考價":     cb_ref_price,
            "原始發行(億)": to_bn(row.get("原始發行總額")),
            "發行餘額(億)": to_bn(row.get("上月底發行餘額")),
            "票面利率(%)":  row.get("票面利率", ""),
            "轉換起日":     conv_start,
            "轉換迄日":     conv_end,
            "到期日":       maturity_str,
        })

    df = pd.DataFrame(rows)
    return df, price_date


# ── Load ─────────────────────────────────────────────────────────────────────────
with st.spinner("載入可轉債資料…"):
    df, price_date = load_cb_data()

price_date_str = pd.Timestamp(price_date).strftime("%Y-%m-%d")

st.title("📄 可轉債資料")
st.caption(f"股價日期：**{price_date_str}**　｜　資料來源：FinLab / 公開資訊觀測站")

# ── Sidebar filters ──────────────────────────────────────────────────────────────
st.sidebar.header("篩選條件")

search_kw = st.sidebar.text_input("搜尋代號 / 名稱", placeholder="e.g. 3037 or 欣興")

industries = sorted(df["產業別"].dropna().unique().tolist())
industries = [i for i in industries if i]
sel_industries = st.sidebar.multiselect("產業別", options=industries, default=[])

premium_range = st.sidebar.slider(
    "溢價率(%) 範圍",
    min_value=-100.0, max_value=200.0,
    value=(-100.0, 50.0), step=5.0,
)

show_negative_premium = st.sidebar.checkbox("只顯示折價（溢價率 < 0）", value=False)

sort_col = st.sidebar.selectbox(
    "排序欄位",
    options=["溢價率(%)", "目前股價", "發行餘額(億)", "原始發行(億)", "到期日"],
    index=0,
)
sort_asc = st.sidebar.checkbox("升冪排列", value=True)

# ── Apply filters ────────────────────────────────────────────────────────────────
filtered = df.copy()

if search_kw.strip():
    kw = search_kw.strip()
    mask = (
        filtered["CB代號"].astype(str).str.contains(kw, case=False) |
        filtered["CB名稱"].str.contains(kw, case=False, na=False) |
        filtered["股票代號"].astype(str).str.contains(kw, case=False) |
        filtered["公司名稱"].str.contains(kw, case=False, na=False)
    )
    filtered = filtered[mask]

if sel_industries:
    filtered = filtered[filtered["產業別"].isin(sel_industries)]

if show_negative_premium:
    filtered = filtered[filtered["溢價率(%)"].fillna(999) < 0]
else:
    has_premium = filtered["溢價率(%)"].notna()
    in_range    = filtered["溢價率(%)"].between(premium_range[0], premium_range[1])
    filtered    = filtered[~has_premium | in_range]

filtered = filtered.sort_values(sort_col, ascending=sort_asc, na_position="last")
filtered = filtered.reset_index(drop=True)
filtered.index += 1

# ── Summary metrics ──────────────────────────────────────────────────────────────
valid_premium = filtered["溢價率(%)"].dropna()

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("CB 檔數",      f"{len(filtered):,}")
col2.metric("折價（<0%）",  f"{(valid_premium < 0).sum():,} 檔")
col3.metric("溢價率中位數", f"{valid_premium.median():.1f}%" if len(valid_premium) else "—")
col4.metric("溢價率最低",   f"{valid_premium.min():.1f}%" if len(valid_premium) else "—")
col5.metric("溢價率最高",   f"{valid_premium.max():.1f}%" if len(valid_premium) else "—")

st.divider()

# ── Tabs ─────────────────────────────────────────────────────────────────────────
tab_issued, tab_chart = st.tabs(["📋 已發行 CB 列表", "📊 溢價率分佈"])

DISPLAY_COLS = [
    "CB代號", "CB名稱", "股票代號", "公司名稱", "產業別",
    "轉換價格", "目前股價", "溢價率(%)", "CB參考價",
    "原始發行(億)", "發行餘額(億)", "票面利率(%)", "轉換起日", "轉換迄日", "到期日",
]
existing_cols = [c for c in DISPLAY_COLS if c in filtered.columns]

with tab_issued:
    st.markdown(f"#### 已發行可轉債（{len(filtered)} 檔）")

    # Color 溢價率 cells without Styler (avoids 262k-cell limit)
    def color_premium_col(series):
        return [
            "color: #ef5350; font-weight:600" if (not pd.isna(v) and v < 0)
            else ("color: #26a69a; font-weight:600" if not pd.isna(v) else "color: #888")
            for v in series
        ]

    styled = filtered[existing_cols].style.apply(color_premium_col, subset=["溢價率(%)"])
    st.dataframe(styled, use_container_width=True, height=600)

    csv = filtered[existing_cols].to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        label="下載 CSV",
        data=csv,
        file_name=f"cb_issued_{price_date_str}.csv",
        mime="text/csv",
    )

with tab_chart:
    chart_df = filtered.dropna(subset=["溢價率(%)"]).head(80)
    if not chart_df.empty:
        colors = ["#ef5350" if v < 0 else "#26a69a" for v in chart_df["溢價率(%)"]]
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=chart_df["CB代號"] + " " + chart_df["CB名稱"].fillna(""),
            y=chart_df["溢價率(%)"],
            marker_color=colors,
            hovertemplate=(
                "<b>%{x}</b><br>"
                "溢價率: %{y:.2f}%<br>"
                "轉換價: %{customdata[0]}<br>"
                "目前股價: %{customdata[1]}<extra></extra>"
            ),
            customdata=chart_df[["轉換價格", "目前股價"]].values,
        ))
        fig.add_hline(y=0, line_color="#555", line_width=1)
        fig.update_layout(
            title=f"可轉債溢價率（前 {len(chart_df)} 檔，依溢價率排序）",
            template="plotly_dark",
            height=420,
            xaxis=dict(tickangle=-45, tickfont=dict(size=9)),
            yaxis_title="溢價率 (%)",
            showlegend=False,
            margin=dict(b=140),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("目前篩選條件下無可繪製資料")

    # Premium distribution histogram
    if len(valid_premium) > 0:
        fig2 = go.Figure()
        fig2.add_trace(go.Histogram(
            x=valid_premium,
            nbinsx=50,
            marker_color="#4c9be8",
            hovertemplate="溢價率: %{x:.1f}% — %{y} 檔<extra></extra>",
        ))
        fig2.add_vline(
            x=0, line_color="#ef5350", line_width=2, line_dash="dash",
            annotation_text="轉換平衡點", annotation_position="top right",
        )
        fig2.update_layout(
            title="溢價率分佈直方圖",
            template="plotly_dark",
            height=320,
            xaxis_title="溢價率 (%)",
            yaxis_title="CB 檔數",
            showlegend=False,
        )
        st.plotly_chart(fig2, use_container_width=True)
