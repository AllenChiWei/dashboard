import re
import requests
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

st.set_page_config(page_title="處置 / 注意股", page_icon="🚨", layout="wide")

st.markdown("""
<style>
body, .stApp { background-color: #0e1117; color: #e0e0e0; }
.block-container { padding-top: 1.5rem; }
[data-testid="stMetricLabel"] { color: #ffffff !important; }
[data-testid="stMetricValue"] { color: #ffffff !important; }
[data-testid="stDataFrame"] { border-radius: 8px; }
.news-card {
    background: #1e2130;
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 8px;
    border-left: 3px solid #4c9be8;
}
.news-card.cnyes  { border-left-color: #26a69a; }
.news-card.yahoo  { border-left-color: #7B68EE; }
.news-card.moneydj { border-left-color: #FFA726; }
.news-title a {
    font-size: 14px;
    font-weight: 600;
    color: #e0e0e0;
    text-decoration: none;
}
.news-title a:hover { color: #4c9be8; text-decoration: underline; }
.news-meta { font-size: 11px; color: #616161; margin-top: 4px; }
.news-source-badge {
    display: inline-block; font-size: 10px; background: #2a2d3e;
    padding: 1px 5px; border-radius: 3px; color: #90caf9; margin-right: 4px;
}
</style>
""", unsafe_allow_html=True)


# ── Constants ─────────────────────────────────────────────────────────────────
FIVE_DAYS_AGO = int((datetime.now() - timedelta(days=5)).timestamp())
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# ── Helpers ───────────────────────────────────────────────────────────────────
def roc_to_date(roc_str: str) -> str:
    try:
        s = str(roc_str).strip()
        return f"{int(s[:3])+1911}-{s[3:5]}-{s[5:7]}"
    except Exception:
        return roc_str


def roc_period_to_ce(period: str) -> str:
    def _conv(m):
        return f"{int(m.group(1))+1911}/{m.group(2)}/{m.group(3)}"
    return re.sub(r"(\d{3})/(\d{2})/(\d{2})", _conv, period)


def last_n_trading_days(n: int = 5) -> tuple[str, str]:
    end = datetime.today()
    start = end - timedelta(days=n * 2)
    return start.strftime("%Y%m%d"), end.strftime("%Y%m%d")


# ── K-line chart ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=600)
def fetch_kline(code: str, period: str = "3mo") -> pd.DataFrame:
    """Try .TW then .TWO suffix; return OHLCV DataFrame or empty."""
    for suffix in [".TW", ".TWO"]:
        try:
            df = yf.download(
                code + suffix, period=period, interval="1d",
                progress=False, auto_adjust=True
            )
            if len(df) >= 5:
                # Flatten MultiIndex columns
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
                df.index = pd.to_datetime(df.index)
                return df
        except Exception:
            continue
    return pd.DataFrame()


def _nearest_date(target: str, dates: list[str]) -> str | None:
    """Return the closest date string in dates to target ('YYYY-MM-DD')."""
    try:
        target_dt = datetime.strptime(target, "%Y-%m-%d")
        return min(dates, key=lambda d: abs((datetime.strptime(d, "%Y-%m-%d") - target_dt).days))
    except Exception:
        return None


def _parse_disp_period(period: str) -> tuple[str, str]:
    """Extract (start, end) from '2026/04/17 ～ 2026/04/30' → ('2026-04-17', '2026-04-30')."""
    matches = re.findall(r"(\d{4})/(\d{2})/(\d{2})", period)
    if len(matches) >= 2:
        s = f"{matches[0][0]}-{matches[0][1]}-{matches[0][2]}"
        e = f"{matches[1][0]}-{matches[1][1]}-{matches[1][2]}"
        return s, e
    if len(matches) == 1:
        s = f"{matches[0][0]}-{matches[0][1]}-{matches[0][2]}"
        return s, s
    return "", ""


def render_kline(code: str, name: str, disp_period: str = ""):
    """Draw candlestick + volume chart; optionally mark disposition period."""
    df = fetch_kline(code)
    if df.empty:
        st.warning(f"找不到 **{code}** 的 K 線資料（權證或已下市標的不支援）。")
        return

    # Use string dates to eliminate weekend/holiday gaps
    dates = df.index.strftime("%Y-%m-%d").tolist()

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.7, 0.3],
        vertical_spacing=0.03,
    )

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=dates,
        open=df["Open"], high=df["High"],
        low=df["Low"],   close=df["Close"],
        name="K線",
        increasing_line_color="#ef5350",
        decreasing_line_color="#26a69a",
    ), row=1, col=1)

    # Volume bars
    colors = [
        "#ef5350" if c >= o else "#26a69a"
        for c, o in zip(df["Close"], df["Open"])
    ]
    fig.add_trace(go.Bar(
        x=dates,
        y=df["Volume"],
        name="成交量",
        marker_color=colors,
        showlegend=False,
    ), row=2, col=1)

    # Mark disposition start date — annotation sits in top margin, never overlaps data
    if disp_period:
        disp_start, disp_end = _parse_disp_period(disp_period)
        nearest = _nearest_date(disp_start, dates) if disp_start else None
        if nearest:
            x_idx = dates.index(nearest)
            # Small tick mark in the margin above the K-line subplot
            fig.add_shape(
                type="line",
                x0=x_idx, x1=x_idx,
                y0=1.0, y1=1.06,          # stays above the plot area (domain coords)
                xref="x", yref="y domain",
                line=dict(color="#FFA726", width=2),
            )
            # Small tick mark in the margin above the volume subplot
            fig.add_shape(
                type="line",
                x0=x_idx, x1=x_idx,
                y0=1.0, y1=1.12,
                xref="x", yref="y2 domain",
                line=dict(color="#FFA726", width=2),
            )
            # Label above the K-line subplot (yanchor="bottom" → text is above y=1.0)
            fig.add_annotation(
                x=x_idx, y=1.07,
                xref="x", yref="y domain",
                text=f"▼ 處置起始 {disp_start}",
                showarrow=False,
                font=dict(color="#FFA726", size=10),
                bgcolor="rgba(20,22,35,0.85)",
                bordercolor="#FFA726",
                borderwidth=1,
                xanchor="center",
                yanchor="bottom",
            )

    fig.update_layout(
        title=f"{code} {name}　日K線（近3個月）",
        template="plotly_dark",
        height=520,
        xaxis_type="category",
        xaxis_rangeslider_visible=False,
        xaxis2_type="category",
        yaxis_title="價格",
        yaxis2_title="成交量",
        margin=dict(t=70, b=30, l=60, r=20),
        legend=dict(orientation="h", y=1.02, x=0),
    )
    st.plotly_chart(fig, use_container_width=True)


# ── News fetch helpers ────────────────────────────────────────────────────────
@st.cache_data(ttl=600)
def fetch_cnyes_news(code: str, limit: int = 15) -> list[dict]:
    try:
        r = requests.get(
            "https://api.cnyes.com/media/api/v1/search/news",
            headers=HEADERS, params={"q": code, "limit": limit}, timeout=10
        )
        r.raise_for_status()
        items = r.json().get("items", {})
        if isinstance(items, dict):
            items = items.get("data", [])
        return [x for x in items if x.get("publishAt", 0) >= FIVE_DAYS_AGO]
    except Exception:
        return []


@st.cache_data(ttl=600)
def fetch_yahoo_news(code: str, count: int = 15) -> list[dict]:
    try:
        r = requests.get(
            "https://query2.finance.yahoo.com/v1/finance/search",
            headers={**HEADERS, "Accept": "application/json"},
            params={
                "q": f"{code}.TW",
                "newsCount": count,
                "enableFuzzyQuery": "false",
                "lang": "zh-Hant-TW",
                "region": "TW",
            },
            timeout=10,
        )
        r.raise_for_status()
        news = r.json().get("news", [])
        return [x for x in news if x.get("providerPublishTime", 0) >= FIVE_DAYS_AGO]
    except Exception:
        return []


@st.cache_data(ttl=600)
def fetch_gnews_news(code: str, name: str, limit: int = 15) -> list[dict]:
    """Google News RSS — returns articles from 工商時報, Yahoo股市, 聯合, 自由, 永豐金 etc."""
    try:
        from email.utils import parsedate_to_datetime
        query = f"{code} {name} 台股" if name else f"{code} 台股"
        r = requests.get(
            "https://news.google.com/rss/search",
            headers=HEADERS,
            params={"q": query, "hl": "zh-TW", "gl": "TW", "ceid": "TW:zh-Hant"},
            timeout=10,
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        items, seen = [], set()
        for item in soup.find_all("item"):
            t_tag   = item.find("title")
            pub_tag = item.find("pubDate")
            src_tag = item.find("source")
            link_tag = item.find("link")
            if not t_tag:
                continue
            ts = 0
            try:
                ts = int(parsedate_to_datetime(pub_tag.text).timestamp()) if pub_tag else 0
            except Exception:
                pass
            if ts and ts < FIVE_DAYS_AGO:
                continue
            publisher = src_tag.text.strip() if src_tag else "Google News"
            raw = t_tag.text.strip()
            if publisher:
                esc = re.escape(publisher)
                raw = re.sub(r"\s*-[^-]+-\s*" + esc + r"\s*$", "", raw).strip()
                raw = re.sub(r"\s*-\s*" + esc + r"\s*$", "", raw).strip()
            link = link_tag.text.strip() if link_tag and link_tag.text else ""
            uid = raw[:25]
            if uid in seen:
                continue
            seen.add(uid)
            items.append({"title": raw, "link": link, "ts": ts, "publisher": publisher})
            if len(items) >= limit:
                break
        return items
    except Exception:
        return []


@st.cache_data(ttl=600)
def fetch_moneydj_news(code: str, limit: int = 10) -> list[dict]:
    try:
        r = requests.get(
            f"https://www.moneydj.com/KMDJ/News/NewsViewer.aspx",
            headers=HEADERS,
            params={"a": "taistock", "b": code},
            timeout=15,
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        seen, items = set(), []
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if "/kmdj/news/newsviewer.aspx" not in href.lower():
                continue
            m = re.search(r"a=([0-9a-f\-]+)", href, re.I)
            if not m:
                continue
            uid = m.group(1)
            if uid in seen:
                continue
            seen.add(uid)
            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            url = "https://www.moneydj.com" + href if href.startswith("/") else href
            items.append({"title": title, "link": url})
            if len(items) >= limit:
                break
        return items
    except Exception:
        return []


def _news_card(title: str, url: str, source: str, dt_str: str, card_class: str) -> str:
    return f"""
<div class='news-card {card_class}'>
  <div class='news-title'><a href='{url}' target='_blank'>{title}</a></div>
  <div class='news-meta'>
    <span class='news-source-badge'>{source}</span>
    {dt_str}
  </div>
</div>"""


def render_stock_news(code: str, name: str):
    """Fetch and display news from cnyes, Google News RSS, Yahoo Finance, and MoneyDJ."""
    st.markdown(f"##### 📰 {code} {name} — 近 5 天相關新聞")

    cnyes_items   = fetch_cnyes_news(code)
    gnews_items   = fetch_gnews_news(code, name)
    yahoo_items   = fetch_yahoo_news(code)
    moneydj_items = fetch_moneydj_news(code)

    # Normalise all sources to unified format: {title, url, ts, publisher}
    unified: list[dict] = []
    for item in cnyes_items:
        title = item.get("title", "").replace("<mark>", "").replace("</mark>", "")
        news_id = item.get("newsId", "")
        unified.append({
            "title": title,
            "url":   f"https://news.cnyes.com/news/id/{news_id}",
            "ts":    item.get("publishAt", 0),
            "publisher": item.get("source", "") or "鉅亨網",
            "card_class": "cnyes",
        })
    for item in gnews_items:
        unified.append({
            "title": item.get("title", ""),
            "url":   item.get("link", "#"),
            "ts":    item.get("ts", 0),
            "publisher": item.get("publisher", "Google News"),
            "card_class": "yahoo",   # reuse purple style for Google News
        })
    for item in yahoo_items:
        unified.append({
            "title": item.get("title", ""),
            "url":   item.get("link", "#"),
            "ts":    item.get("providerPublishTime", 0),
            "publisher": item.get("publisher", "Yahoo股市"),
            "card_class": "yahoo",
        })
    # MoneyDJ has no timestamp — append last
    mdj_cards = [
        {"title": x.get("title",""), "url": x.get("link","#"),
         "ts": 0, "publisher": "MoneyDJ", "card_class": "moneydj"}
        for x in moneydj_items
    ]

    # Deduplicate by title prefix, sort by date (MoneyDJ at the end)
    seen: set[str] = set()
    merged: list[dict] = []
    for item in unified:
        key = item["title"][:28]
        if key and key not in seen:
            seen.add(key)
            merged.append(item)
    merged.sort(key=lambda x: x["ts"], reverse=True)
    for item in mdj_cards:
        key = item["title"][:28]
        if key and key not in seen:
            seen.add(key)
            merged.append(item)

    if not merged:
        st.info("近 5 天找不到相關新聞。")
        return

    cards = []
    for item in merged:
        dt_str = (datetime.fromtimestamp(item["ts"]).strftime("%m/%d %H:%M")
                  if item["ts"] else "")
        cards.append(_news_card(item["title"], item["url"],
                                item["publisher"], dt_str, item["card_class"]))

    st.markdown("".join(cards), unsafe_allow_html=True)
    st.caption(
        f"共 {len(merged)} 則　｜　"
        f"鉅亨網 {len(cnyes_items)} 則 ｜ "
        f"Google News {len(gnews_items)} 則 ｜ "
        f"Yahoo股市 {len(yahoo_items)} 則 ｜ "
        f"MoneyDJ {len(moneydj_items)} 則"
    )


# ── K-line section ─────────────────────────────────────────────────────────────
def show_kline_section(df_display: pd.DataFrame, table_key: str,
                       height: int = 400, disp_period_col: str = ""):
    """
    Render a selectable dataframe and show K-line below when a row is clicked.
    disp_period_col: column name containing the disposition period string (optional).
    """
    event = st.dataframe(
        df_display,
        use_container_width=True,
        height=height,
        on_select="rerun",
        selection_mode="single-row",
        key=table_key,
    )
    sel_rows = event.selection.get("rows", []) if event and event.selection else []
    if sel_rows:
        idx = sel_rows[0]
        row = df_display.iloc[idx]
        code = str(row["代號"]).strip()
        name = str(row["名稱"]).strip()
        disp_period = str(row.get(disp_period_col, "")) if disp_period_col else ""
        with st.container():
            st.markdown(f"##### 📈 {code} {name} — 日K線")
            render_kline(code, name, disp_period=disp_period)
        with st.container():
            with st.spinner(f"載入 {code} 相關新聞…"):
                render_stock_news(code, name)
    return event


# ── Data fetch ────────────────────────────────────────────────────────────────
@st.cache_data(ttl=900)
def fetch_disposal() -> pd.DataFrame:
    r = requests.get(
        "https://openapi.twse.com.tw/v1/announcement/punish",
        headers={"User-Agent": "Mozilla/5.0"}, timeout=10
    )
    r.raise_for_status()
    rows = []
    for item in r.json():
        code = item.get("Code", "").strip()
        if not code:
            continue
        dm = item.get("DispositionMeasures", "")
        rows.append({
            "代號":     code,
            "名稱":     item.get("Name", ""),
            "公告日":   roc_to_date(item.get("Date", "")),
            "處置原因": item.get("ReasonsOfDisposition", ""),
            "處置期間": roc_period_to_ce(item.get("DispositionPeriod", "")),
            "處置措施": dm,
            "處置次數": item.get("NumberOfAnnouncement", ""),
            "類型":     "🔴 20分鐘制" if any(x in dm for x in ["第二次", "第三次", "第四次", "第五次"])
                        else "🟡 5分鐘制",
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Parse disposition end date from '2026/04/17 ～ 2026/04/30'
    def _end_date(period: str) -> pd.Timestamp:
        matches = re.findall(r"(\d{4})/(\d{2})/(\d{2})", period)
        if len(matches) >= 2:
            return pd.Timestamp(f"{matches[1][0]}-{matches[1][1]}-{matches[1][2]}")
        return pd.Timestamp.min

    df["_end"] = df["處置期間"].apply(_end_date)
    today = pd.Timestamp(datetime.today().date())

    # Keep only active dispositions (end date >= today)
    df = df[df["_end"] >= today]

    # Deduplicate: per stock keep the record with the latest end date
    df = (df.sort_values("_end", ascending=False)
            .drop_duplicates(subset=["代號"])
            .drop(columns=["_end"])
            .sort_values(["類型", "公告日"], ascending=[True, False])
            .reset_index(drop=True))
    return df


@st.cache_data(ttl=900)
def fetch_attention():
    start_str, end_str = last_n_trading_days(5)
    r = requests.get(
        "https://www.twse.com.tw/rwd/zh/announcement/notice",
        headers={"User-Agent": "Mozilla/5.0"},
        params={"startDate": start_str, "endDate": end_str},
        timeout=15
    )
    r.raise_for_status()
    payload = r.json()
    fields = payload.get("fields", [])
    rows   = payload.get("data", [])

    if not rows:
        return pd.DataFrame(), pd.DataFrame(), ""

    df = pd.DataFrame(rows, columns=fields)
    rename = {
        "證券代號": "代號", "證券名稱": "名稱", "累計次數": "累計次數",
        "注意交易資訊": "注意原因", "日期": "日期(民國)",
        "收盤價": "收盤價", "本益比": "本益比",
    }
    df = df.rename(columns=rename)
    df["累計次數"] = pd.to_numeric(df["累計次數"], errors="coerce").fillna(0).astype(int)

    def roc_dot_to_ce(s):
        try:
            parts = str(s).strip().split(".")
            return f"{int(parts[0])+1911}-{parts[1]}-{parts[2]}"
        except Exception:
            return s
    df["日期"] = df["日期(民國)"].apply(roc_dot_to_ce)
    df["收盤價"] = df["收盤價"].astype(str).str.strip()
    df["本益比"] = df["本益比"].astype(str).str.strip()

    latest_date = df["日期"].max()

    df_first = (
        df[(df["累計次數"] == 1) & (df["日期"] == latest_date)]
        .drop(columns=["日期(民國)", "編號"], errors="ignore")
        .sort_values("代號")
        .reset_index(drop=True)
    )
    df_first.index += 1

    df_consec = (
        df[df["累計次數"] >= 2]
        .sort_values("日期", ascending=False)
        .drop_duplicates(subset=["代號"])
        .drop(columns=["日期(民國)", "編號"], errors="ignore")
    )
    df_consec["⚠️ 風險"] = df_consec["累計次數"].apply(
        lambda x: "🔴 高（連3次可能進處置）" if x >= 3 else "🟡 中（連2次）"
    )
    df_consec = df_consec.sort_values("累計次數", ascending=False).reset_index(drop=True)
    df_consec.index += 1

    return df_first, df_consec, latest_date


# ── Load ──────────────────────────────────────────────────────────────────────
with st.spinner("載入監控資料…"):
    df_disposal = fetch_disposal()
    result = fetch_attention()

df_first, df_consec, latest_date = (result if len(result) == 3
                                    else (pd.DataFrame(), pd.DataFrame(), ""))

# ── Header ────────────────────────────────────────────────────────────────────
st.title("🚨 處置股 / 注意股監控")
st.caption("資料來源：TWSE OpenAPI　｜　每15分鐘自動更新　｜　點選列可查看 K 線圖")

# ── Summary metrics ───────────────────────────────────────────────────────────
n_5min   = (df_disposal["類型"] == "🟡 5分鐘制").sum() if not df_disposal.empty else 0
n_20min  = (df_disposal["類型"] == "🔴 20分鐘制").sum() if not df_disposal.empty else 0
n_first  = len(df_first)
n_consec = len(df_consec)
n_high   = int((df_consec["累計次數"] >= 3).sum()) if not df_consec.empty else 0

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("🟡 5分鐘處置", f"{n_5min} 檔")
c2.metric("🔴 20分鐘處置", f"{n_20min} 檔")
c3.metric("📅 第一次注意", f"{n_first} 檔" if n_first else "無資料")
c4.metric("🔁 連續注意", f"{n_consec} 檔")
c5.metric("⚠️ 高風險（連3次）", f"{n_high} 檔")

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_disposal, tab_attention = st.tabs(["🔒 處置股", "👁️ 注意股"])


# ── 處置股 Tab ────────────────────────────────────────────────────────────────
with tab_disposal:
    if df_disposal.empty:
        st.info("目前無處置股資料。")
    else:
        df_5  = df_disposal[df_disposal["類型"] == "🟡 5分鐘制"].reset_index(drop=True)
        df_20 = df_disposal[df_disposal["類型"] == "🔴 20分鐘制"].reset_index(drop=True)
        df_5.index += 1
        df_20.index += 1

        display_cols = ["代號", "名稱", "處置措施", "處置期間", "處置原因", "處置次數", "公告日"]

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"#### 🟡 5分鐘制處置（{len(df_5)} 檔）")
            st.caption("買賣申報每 **5 分鐘** 撮合一次　｜　點選列查看 K 線")
            if df_5.empty:
                st.info("目前無 5 分鐘制處置股。")
            else:
                show_kline_section(df_5[display_cols], "tbl_5min", height=420,
                                   disp_period_col="處置期間")

        with col2:
            st.markdown(f"#### 🔴 20分鐘制處置（{len(df_20)} 檔）")
            st.caption("買賣申報每 **20 分鐘** 撮合一次　｜　點選列查看 K 線")
            if df_20.empty:
                st.info("目前無 20 分鐘制處置股。")
            else:
                show_kline_section(df_20[display_cols], "tbl_20min", height=420,
                                   disp_period_col="處置期間")

        st.divider()
        with st.expander("📋 全部處置股（合併）"):
            df_all = df_disposal.copy()
            df_all.index = range(1, len(df_all) + 1)
            st.dataframe(df_all[["類型"] + display_cols], use_container_width=True, height=400)
            csv = df_all.to_csv(index=False, encoding="utf-8-sig")
            st.download_button("下載 CSV", csv, "disposal_stocks.csv", "text/csv")


# ── 注意股 Tab ────────────────────────────────────────────────────────────────
with tab_attention:
    date_label = f"（{latest_date}）" if latest_date else ""

    # ── 第一次注意 ─────────────────────────────────────────────────────────────
    st.markdown(f"#### 📅 第一次注意股 {date_label}")
    st.caption("當日首次被列為注意股，累計次數 = 1　｜　點選列查看 K 線")
    if df_first.empty:
        st.info("無第一次注意股資料（市場休市或當日尚無資料）。")
    else:
        disp_cols_first = ["代號", "名稱", "累計次數", "注意原因", "日期", "收盤價", "本益比"]
        disp_cols_first = [c for c in disp_cols_first if c in df_first.columns]
        show_kline_section(
            df_first[disp_cols_first], "tbl_first",
            height=max(200, min(500, len(df_first) * 38 + 40))
        )
        csv1 = df_first.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("下載 CSV", csv1, "attention_first.csv", "text/csv", key="dl_first")

    st.divider()

    # ── 連續注意 ───────────────────────────────────────────────────────────────
    st.markdown("#### 🔁 連續注意股（近 5 個交易日）")
    st.caption("連續 **3 次**注意將觸發處置程序　｜　點選列查看 K 線")
    if df_consec.empty:
        st.info("近期無連續注意股資料。")
    else:
        def highlight_risk(row):
            if row["累計次數"] >= 3:
                return ["background-color: rgba(239,83,80,0.15)"] * len(row)
            elif row["累計次數"] == 2:
                return ["background-color: rgba(255,193,7,0.10)"] * len(row)
            return [""] * len(row)

        disp_cols_consec = ["代號", "名稱", "累計次數", "⚠️ 風險", "注意原因", "日期", "收盤價"]
        disp_cols_consec = [c for c in disp_cols_consec if c in df_consec.columns]

        # Note: style + on_select don't mix — use plain dataframe for selectability
        show_kline_section(
            df_consec[disp_cols_consec], "tbl_consec",
            height=max(200, min(500, len(df_consec) * 38 + 40))
        )
        csv2 = df_consec.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("下載 CSV", csv2, "attention_consec.csv", "text/csv", key="dl_consec")
