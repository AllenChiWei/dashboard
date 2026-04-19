import re
import requests
import streamlit as st
from bs4 import BeautifulSoup
from collections import Counter
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

try:
    from ddgs import DDGS
    _DDGS_OK = True
except ImportError:
    _DDGS_OK = False

st.set_page_config(page_title="股市新聞", page_icon="📰", layout="wide")

st.markdown("""
<style>
body, .stApp { background-color: #0e1117; color: #e0e0e0; }
.block-container { padding-top: 1.5rem; }
.news-card {
    background: #1e2130;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 10px;
    border-left: 3px solid #4c9be8;
}
.news-title a {
    font-size: 15px;
    font-weight: 600;
    color: #e0e0e0;
    text-decoration: none;
}
.news-title a:hover { color: #4c9be8; text-decoration: underline; }
.news-summary { font-size: 12px; color: #9e9e9e; margin-top: 5px; line-height: 1.5; }
.news-meta  { font-size: 11px; color: #616161; margin-top: 5px; }
.news-badge {
    display: inline-block; font-size: 10px; background: #2a2d3e;
    padding: 2px 7px; border-radius: 4px; color: #90caf9; margin-right: 4px;
}
</style>
""", unsafe_allow_html=True)

# ── Constants ──────────────────────────────────────────────────────────────────
CNYES_BASE    = "https://api.cnyes.com/media/api/v1"
GNEWS_BASE    = "https://news.google.com/rss/search"
HEADERS       = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
FIVE_DAYS_AGO = int((datetime.now() - timedelta(days=5)).timestamp())


# ── Raw fetch functions ────────────────────────────────────────────────────────
@st.cache_data(ttl=600)
def _cnyes_category(category: str, limit: int = 60) -> list[dict]:
    try:
        r = requests.get(f"{CNYES_BASE}/newslist/category/{category}",
                         headers=HEADERS, params={"limit": limit}, timeout=10)
        r.raise_for_status()
        items = r.json().get("items", {})
        if isinstance(items, dict):
            items = items.get("data", [])
        return [x for x in items if x.get("publishAt", 0) >= FIVE_DAYS_AGO]
    except Exception:
        return []


@st.cache_data(ttl=600)
def _cnyes_search(query: str, limit: int = 40) -> list[dict]:
    try:
        r = requests.get(f"{CNYES_BASE}/search/news",
                         headers=HEADERS, params={"q": query, "limit": limit}, timeout=10)
        r.raise_for_status()
        items = r.json().get("items", {})
        if isinstance(items, dict):
            items = items.get("data", [])
        return [x for x in items if x.get("publishAt", 0) >= FIVE_DAYS_AGO]
    except Exception:
        return []


@st.cache_data(ttl=600)
def _google_news(query: str, limit: int = 30) -> list[dict]:
    """Google News RSS — 工商時報, Yahoo股市, 聯合, 自由, 永豐金 etc."""
    try:
        r = requests.get(GNEWS_BASE, headers=HEADERS,
                         params={"q": query, "hl": "zh-TW", "gl": "TW",
                                 "ceid": "TW:zh-Hant"},
                         timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.content.decode("utf-8", errors="replace"), "xml")
        results = []
        for item in soup.find_all("item"):
            t_tag    = item.find("title")
            pub_tag  = item.find("pubDate")
            src_tag  = item.find("source")
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
            publisher = src_tag.text.strip() if src_tag else ""
            raw = t_tag.text.strip()
            if publisher:
                esc = re.escape(publisher)
                raw = re.sub(r"\s*-[^-]+-\s*" + esc + r"\s*$", "", raw).strip()
                raw = re.sub(r"\s*-\s*" + esc + r"\s*$", "", raw).strip()
            link = link_tag.text.strip() if link_tag and link_tag.text else ""
            results.append({"title": raw, "link": link, "ts": ts, "publisher": publisher})
            if len(results) >= limit:
                break
        return results
    except Exception:
        return []


_YAHOO_PUB_MAP = [
    ("中時電子報",                          "中時"),
    ("工商時報",                            "工商時報"),
    ("鉅亨網",                              "鉅亨網"),
    ("自由時報電子報",                       "自由時報"),
    ("太報",                                "太報"),
    ("三立新聞網 setn.com via Yahoo奇摩新聞","三立新聞"),
    ("三立新聞",                            "三立新聞"),
    ("ETtoday財經雲",                       "ETtoday"),
    ("ETtoday新聞雲",                       "ETtoday"),
    ("今周刊",                              "今周刊"),
    ("聯合新聞網",                          "聯合"),
    ("風傳媒 via Yahoo奇摩新聞",             "風傳媒"),
    ("風傳媒",                              "風傳媒"),
    ("EBC東森財經新聞",                     "東森財經"),
    ("NOWnews今日新聞",                     "NOWnews"),
    ("TVBS新聞網",                          "TVBS"),
    ("TVBS",                               "TVBS"),
    ("數位時代",                            "數位時代"),
    ("科技新報",                            "科技新報"),
    ("Yahoo奇摩",                           "Yahoo奇摩"),
    ("MoneyDJ理財網",                       "MoneyDJ"),
    ("商業周刊",                            "商業周刊"),
    ("鏡週刊",                              "鏡週刊"),
    ("天下雜誌",                            "天下雜誌"),
]


@st.cache_data(ttl=600)
def _yahoo_search(query: str, limit: int = 20) -> list[dict]:
    """Yahoo Taiwan search — returns real article URLs with approximate timestamps."""
    from urllib.parse import unquote as _unquote
    try:
        import urllib.parse as _up
        url = ("https://tw.search.yahoo.com/search?"
               + _up.urlencode({"fr": "finance", "fr2": "p:finvsrp,m:sb", "p": query}))
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.content.decode("utf-8", errors="replace"), "html.parser")

        seen: set[str] = set()
        results: list[dict] = []
        for elem in soup.find_all(string=re.compile(r"\d+\s*(?:天|小時)前")):
            a = elem.find_parent("a", href=True)
            if not a:
                continue
            href  = a.get("href", "")
            full  = a.get_text(strip=True)
            # convert relative time → timestamp
            tm = re.search(r"(\d+)\s*(天|小時)前", full)
            ts = 0
            if tm:
                val, unit = int(tm.group(1)), tm.group(2)
                delta = timedelta(days=val) if unit == "天" else timedelta(hours=val)
                ts = int((datetime.now() - delta).timestamp())
            if ts and ts < FIVE_DAYS_AGO:
                continue
            # strip time suffix from title
            clean = re.sub(r"\s*\d+\s*(?:天|小時)前\s*$", "", full).strip()
            # extract publisher from title prefix
            publisher = "Yahoo搜尋"
            for long_name, short_name in _YAHOO_PUB_MAP:
                if clean.startswith(long_name):
                    publisher = short_name
                    clean = clean[len(long_name):].strip()
                    break
            if not clean or len(clean) < 8:
                continue
            # extract real URL from Yahoo redirect
            m = re.search(r"/RU=([^/]+)/", href)
            real_url = _unquote(m.group(1)) if m else href
            if real_url in seen:
                continue
            seen.add(real_url)
            results.append({"title": clean, "url": real_url,
                             "ts": ts, "publisher": publisher, "summary": ""})
            if len(results) >= limit:
                break
        return results
    except Exception:
        return []


@st.cache_data(ttl=300)
def _yahoo_tw_news(url: str, label: str, limit: int = 30) -> list[dict]:
    """Scrape Yahoo Finance Taiwan news pages (台股盤勢 / 今日要聞)."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        seen, results = set(), []
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if "/news/" not in href:
                continue
            full_url = href if href.startswith("http") else "https://tw.stock.yahoo.com" + href
            title = a.get_text(strip=True)
            if not title or len(title) < 10 or full_url in seen:
                continue
            seen.add(full_url)
            results.append({"title": title, "url": full_url,
                             "ts": 0, "publisher": f"Yahoo!股市({label})", "summary": ""})
            if len(results) >= limit:
                break
        return results
    except Exception:
        return []


@st.cache_data(ttl=600)
def _ddg_search(query: str, limit: int = 20) -> list[dict]:
    """DuckDuckGo — Yahoo奇摩, 工商時報, 聯合, 自由, 今周刊, TVBS, 鏡週刊 etc."""
    if not _DDGS_OK:
        return []
    try:
        with DDGS() as ddgs:
            raw = list(ddgs.news(query + " 台股", region="tw-tzh",
                                 safesearch="off", max_results=limit))
        results = []
        for r in raw:
            ts = 0
            try:
                ts = int(datetime.fromisoformat(
                    r.get("date", "").replace("Z", "+00:00")).timestamp())
            except Exception:
                pass
            if ts and ts < FIVE_DAYS_AGO:
                continue
            results.append({
                "title":     r.get("title", ""),
                "link":      r.get("url", "#"),
                "ts":        ts,
                "publisher": r.get("source", ""),
                "summary":   (r.get("body", "") or "")[:120],
            })
        return results
    except Exception:
        return []


# ── Normalise ──────────────────────────────────────────────────────────────────
def _from_cnyes(raw: list[dict]) -> list[dict]:
    out = []
    for x in raw:
        title = x.get("title", "").replace("<mark>", "").replace("</mark>", "")
        if not title:
            continue
        news_id = x.get("newsId", "")
        out.append({
            "title":     title,
            "url":       f"https://news.cnyes.com/news/id/{news_id}" if news_id else "#",
            "ts":        x.get("publishAt", 0),
            "publisher": x.get("source", "") or "鉅亨網",
            "summary":   (x.get("summary", "") or "")[:120],
        })
    return out


def _from_gnews(raw: list[dict]) -> list[dict]:
    return [{"title": x["title"], "url": x.get("link", "#"),
             "ts": x.get("ts", 0), "publisher": x.get("publisher", ""),
             "summary": ""}
            for x in raw if x.get("title")]


def _from_ddg(raw: list[dict]) -> list[dict]:
    return [{"title": x["title"], "url": x.get("link", "#"),
             "ts": x.get("ts", 0), "publisher": x.get("publisher", ""),
             "summary": x.get("summary", "")}
            for x in raw if x.get("title")]


def _merge(*item_lists: list[dict]) -> list[dict]:
    seen: set[str] = set()
    merged: list[dict] = []
    for items in item_lists:
        for item in items:
            key = item["title"][:28]
            if key not in seen:
                seen.add(key)
                merged.append(item)
    merged.sort(key=lambda x: x["ts"], reverse=True)
    return merged


# ── Render ─────────────────────────────────────────────────────────────────────
def _news_html(items: list[dict]) -> str:
    parts = []
    for item in items:
        ts      = item["ts"]
        pub     = item["publisher"]
        summary = item.get("summary", "")
        dt_str  = datetime.fromtimestamp(ts).strftime("%m/%d %H:%M") if ts else ""
        badge   = f"<span class='news-badge'>{pub}</span>" if pub else ""
        s_html  = (f"<div class='news-summary'>{summary}{'…' if summary else ''}</div>"
                   if summary else "")
        parts.append(f"""
<div class='news-card'>
  <div class='news-title'><a href='{item["url"]}' target='_blank'>{item["title"]}</a></div>
  {s_html}
  <div class='news-meta'>{dt_str}{"　" + badge if badge else ""}</div>
</div>""")
    return "".join(parts)


def render_all_sources(
        cnyes_items:  list[dict],
        gnews_items:  list[dict],
        ddg_items:    list[dict],
        empty_msg:    str = "近5天無相關新聞",
        extra_items:  list[dict] | None = None):
    """Show source metrics then merged & deduplicated news list."""
    extra_items = extra_items or []
    all_items = _merge(cnyes_items, gnews_items, ddg_items, extra_items)

    # ── Per-source metrics ────────────────────────────────────────────────────
    if extra_items:
        c1, c2, c3, c4, c5 = st.columns(5)
        c5.metric("🟡 Yahoo!股市", f"{len(extra_items)} 則")
    else:
        c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔎 合計", f"{len(all_items)} 則")
    c2.metric("📡 Google News", f"{len(gnews_items)} 則")
    c3.metric("🌐 DuckDuckGo",  f"{len(ddg_items)} 則")
    c4.metric("📰 鉅亨網",      f"{len(cnyes_items)} 則")

    if not all_items:
        st.info(empty_msg)
        return

    st.markdown(_news_html(all_items), unsafe_allow_html=True)

    # Publisher breakdown caption
    pubs    = Counter(x["publisher"] for x in all_items if x["publisher"])
    pub_str = "　".join(f"{p} {c}則" for p, c in pubs.most_common(8))
    st.caption(f"來源分佈：{pub_str}")


# ── Page ───────────────────────────────────────────────────────────────────────
st.title("📰 股市新聞")
st.caption("整合 Google News（工商時報·Yahoo股市·聯合·自由·永豐金等）· DuckDuckGo · 鉅亨網　｜　近 5 天")

# ── Search ─────────────────────────────────────────────────────────────────────
st.markdown("### 🔍 個股 / 關鍵字新聞搜尋")
st.caption("同時查詢 Google News · DuckDuckGo · 鉅亨網 · Yahoo搜尋，彙整工商時報·Yahoo股市·MoneyDJ·聯合·自由等")

col_i, col_b = st.columns([4, 1])
with col_i:
    search_q = st.text_input(
        "search", label_visibility="collapsed",
        placeholder="例：2330　　台積電目標價　　AI伺服器概念股")
with col_b:
    st.button("搜尋", use_container_width=True)

if search_q.strip():
    q = search_q.strip()
    with st.spinner(f"同時查詢 Google News + DuckDuckGo + 鉅亨網 + Yahoo搜尋…"):
        s_cnyes = _from_cnyes(_cnyes_search(q, 30))
        s_gnews = _from_gnews(_google_news(f"{q} 台股", 30))
        s_ddg   = _from_ddg(_ddg_search(q, 25))
        s_yahoo = _yahoo_search(q, 20)
    st.markdown(f"#### 「{q}」近 5 天搜尋結果")
    render_all_sources(s_cnyes, s_gnews, s_ddg,
                       empty_msg=f"近 5 天找不到「{q}」的相關新聞，請嘗試其他關鍵字。",
                       extra_items=s_yahoo)

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
st.markdown("### 📌 近五天股市焦點新聞")
st.caption("Google News · DuckDuckGo · 鉅亨網 · Yahoo搜尋 四源彙整，來源含工商時報·Yahoo股市·永豐金·聯合·自由·今周刊 等")

tab_hot, tab_focus, tab_price, tab_target = st.tabs([
    "🔥 熱門股", "📊 盤中焦點股", "💰 漲價題材", "🎯 目標價",
])

# ─── 🔥 熱門股 ────────────────────────────────────────────────────────────────
with tab_hot:
    with st.spinner("載入熱門股新聞…"):
        hot_cnyes   = _from_cnyes(_cnyes_category("tw_stock_news", 50))
        hot_gnews   = _from_gnews(_google_news("台股 熱門", 25))
        hot_ddg     = _from_ddg(_ddg_search("熱門股", 20))
        hot_yahoo1  = _yahoo_tw_news("https://tw.stock.yahoo.com/tw-market/", "台股盤勢", 20)
        hot_yahoo2  = _yahoo_tw_news("https://tw.stock.yahoo.com/news/", "今日要聞", 20)
    render_all_sources(hot_cnyes, hot_gnews, hot_ddg,
                       extra_items=hot_yahoo1 + hot_yahoo2)

# ─── 📊 盤中焦點股 ────────────────────────────────────────────────────────────
with tab_focus:
    with st.spinner("載入盤中焦點股新聞…"):
        focus_cnyes = _from_cnyes(_cnyes_search("焦點股", 30))
        focus_gnews = _from_gnews(_google_news("盤中焦點股 台股", 30))
        focus_ddg   = _from_ddg(_ddg_search("盤中焦點股", 20))
        focus_yahoo = _yahoo_search("盤中焦點股", 20)
    render_all_sources(focus_cnyes, focus_gnews, focus_ddg,
                       empty_msg="近5天找不到焦點股相關報導。",
                       extra_items=focus_yahoo)

# ─── 💰 漲價題材 ──────────────────────────────────────────────────────────────
with tab_price:
    with st.spinner("載入漲價題材新聞…"):
        price_cnyes = _from_cnyes(_cnyes_search("漲價", 30))
        price_gnews = _from_gnews(_google_news("漲價 台股", 25))
        price_ddg   = _from_ddg(_ddg_search("漲價題材", 20))
        price_yahoo = _yahoo_search("漲價題材 台股", 20)
    render_all_sources(price_cnyes, price_gnews, price_ddg,
                       empty_msg="近5天找不到漲價題材相關報導。",
                       extra_items=price_yahoo)

# ─── 🎯 目標價 ────────────────────────────────────────────────────────────────
with tab_target:
    with st.spinner("載入目標價新聞…"):
        tw_all       = _cnyes_category("tw_stock", 80)
        target_cnyes = _from_cnyes([x for x in tw_all
                                    if "目標價" in x.get("title", "")
                                    or "最新調查" in x.get("title", "")])
        target_g1    = _from_gnews(_google_news("目標價 台積電 台股", 30))
        target_g2    = _from_gnews(_google_news("上調目標價 OR 調升目標價 台股", 20))
        target_gnews = _merge(target_g1, target_g2)   # pre-merge two gnews queries
        target_ddg   = _from_ddg(_ddg_search("目標價 台積電", 20))
        target_yahoo = _yahoo_search("目標價 台股 券商", 20)
    render_all_sources(target_cnyes, target_gnews, target_ddg,
                       empty_msg="近5天找不到目標價相關報導。",
                       extra_items=target_yahoo)
