import io
import re
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import xlrd
from xlrd.xldate import xldate_as_datetime

st.set_page_config(page_title="期貨損益分析", page_icon="📈", layout="wide")

st.markdown("""
<style>
body, .stApp { background-color: #0e1117; color: #e0e0e0; }
.block-container { padding-top: 1.5rem; }
.metric-card {
    background: #1e2130; border-radius: 8px; padding: 16px 20px;
    border-left: 3px solid #4c9be8; margin-bottom: 8px;
}
.metric-label { font-size: 12px; color: #9e9e9e; margin-bottom: 4px; }
.metric-value { font-size: 22px; font-weight: 700; }
.pos { color: #ef5350; } .neg { color: #26a69a; } .neu { color: #e0e0e0; }
thead tr th { background: #1e2130 !important; }
</style>
""", unsafe_allow_html=True)

DARK    = "plotly_dark"
CHART_H = 400          # unified chart height

# ── Helpers ────────────────────────────────────────────────────────────────────

def _base_product(name: str) -> str:
    """Strip contract month; group options under 'XX選擇權'."""
    name = name.strip()
    # Options: e.g. 台指32000202603P  →  base='台指' + '選擇權'
    m = re.match(r'^(.+?)\d{4,6}\d{6}[CP]$', name)
    if m:
        return (m.group(1) or '').strip() + '選擇權'
    # Futures: strip trailing YYYYMM
    return re.sub(r'\d{6}$', '', name).strip()


def _to_num(v) -> float:
    try:
        return float(str(v).strip())
    except Exception:
        return 0.0


def _find_col(headers: list[str], *keywords) -> int | None:
    """Return first column index whose header contains any keyword."""
    for kw in keywords:
        for i, h in enumerate(headers):
            if kw in h:
                return i
    return None


# ── Parsers ────────────────────────────────────────────────────────────────────

def parse_yuanta(raw: bytes) -> pd.DataFrame:
    """Parse 元大期貨 已實現損益 XLS (cp950/utf-16 mixed)."""
    wb = xlrd.open_workbook(file_contents=raw)
    ws = wb.sheet_by_index(0)

    # Locate header row (has '商品' somewhere)
    header_row = 0
    for r in range(min(6, ws.nrows)):
        vals = [str(ws.cell_value(r, c)) for c in range(ws.ncols)]
        if any('商品' in v or '結算' in v for v in vals):
            header_row = r
            break

    headers = [ws.cell_value(header_row, c).strip() for c in range(ws.ncols)]

    # Locate key column indices
    date_c    = _find_col(headers, '結算日期') or 0
    prod_c    = _find_col(headers, '商品名稱', '商品') or 2
    lots_c    = _find_col(headers, '口數') or 3
    gross_c   = _find_col(headers, '平倉損益') or 13
    comm_c    = _find_col(headers, '手續費') or 14
    tax_c     = _find_col(headers, '期交稅') or 15
    net_c     = _find_col(headers, '合計損益') or 16
    # Open/close columns are positional (duplicate header names)
    open_bs_c    = 6
    open_price_c = 7
    close_date_c = 8
    close_bs_c   = 10
    close_price_c= 11

    records = []
    for r in range(header_row + 1, ws.nrows):
        raw_prod = str(ws.cell_value(r, prod_c)).strip()
        if not raw_prod or raw_prod in ('nan', '商品名稱'):
            continue

        def date(c):
            v = ws.cell_value(r, c)
            if ws.cell_type(r, c) == xlrd.XL_CELL_DATE:
                return xldate_as_datetime(v, wb.datemode)
            return None

        records.append({
            'date':         date(date_c),
            'open_date':    date(4),
            'close_date':   date(close_date_c),
            'product':      raw_prod,
            'lots':         max(1, int(abs(_to_num(ws.cell_value(r, lots_c))))),
            'open_bs':      str(ws.cell_value(r, open_bs_c)).strip(),
            'open_price':   _to_num(ws.cell_value(r, open_price_c)),
            'close_bs':     str(ws.cell_value(r, close_bs_c)).strip(),
            'close_price':  _to_num(ws.cell_value(r, close_price_c)),
            'gross_pnl':    _to_num(ws.cell_value(r, gross_c)),
            'commission':   _to_num(ws.cell_value(r, comm_c)),
            'tax':          _to_num(ws.cell_value(r, tax_c)),
            'net_pnl':      _to_num(ws.cell_value(r, net_c)),
        })

    df = pd.DataFrame(records)
    if df.empty:
        return df
    df['date']      = pd.to_datetime(df['date'])
    df['open_date'] = pd.to_datetime(df['open_date'])
    df['close_date']= pd.to_datetime(df['close_date'])
    df['base_prod'] = df['product'].apply(_base_product)
    df['month']     = df['date'].dt.to_period('M').astype(str)
    df['direction'] = df['open_bs'].apply(lambda x: '多' if x == 'B' else '空')
    df['broker']    = '元大'
    return df.sort_values('date').reset_index(drop=True)


def parse_kgi(raw: bytes) -> pd.DataFrame:
    """Parse 凱基期貨 XLS (placeholder — update once sample is available)."""
    st.warning("凱基格式尚未實作，請提供樣本檔案。")
    return pd.DataFrame()


def detect_broker(raw: bytes) -> str:
    try:
        wb = xlrd.open_workbook(file_contents=raw)
        ws = wb.sheet_by_index(0)
        text = " ".join(str(ws.cell_value(r, c))
                        for r in range(min(5, ws.nrows))
                        for c in range(ws.ncols))
        if '結算日期' in text or '期交稅' in text:
            return '元大'
        if '凱基' in text:
            return '凱基'
    except Exception:
        pass
    return '元大'


# ── Statistics ─────────────────────────────────────────────────────────────────

def compute_stats(df: pd.DataFrame) -> dict:
    n = len(df)
    if n == 0:
        return {'n': 0}
    wins   = df[df['net_pnl'] > 0]['net_pnl']
    losses = df[df['net_pnl'] < 0]['net_pnl']
    n_win, n_loss = len(wins), len(losses)

    avg_win  = float(wins.mean())  if n_win  > 0 else 0.0
    avg_loss = float(losses.mean()) if n_loss > 0 else 0.0   # negative

    total_win  = float(wins.sum())
    total_loss = abs(float(losses.sum()))
    pf = total_win / total_loss if total_loss > 0 else float('inf')

    # 獲利因子 (signed): >1 positive when winning, <-1 negative when losing
    if pf == float('inf'):
        signed_pf = float('inf')
    elif pf == 0:
        signed_pf = -float('inf')   # no wins at all
    elif pf >= 1:
        signed_pf = pf              # e.g. 2.0 → earned 2x what was lost
    else:
        signed_pf = -(1 / pf)       # e.g. 0.5 → lost 2x what was earned → -2.0

    win_rate = n_win / n
    ev       = win_rate * avg_win + (1 - win_rate) * avg_loss

    # Max consecutive losses
    streak = max_streak = 0
    for p in df['net_pnl']:
        if p < 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0

    # 賠率 (payoff ratio, signed): avg_win / abs(avg_loss)
    if avg_loss == 0:
        payoff = float('inf')
    elif avg_win == 0:
        payoff = -float('inf')
    else:
        raw_payoff = avg_win / abs(avg_loss)
        payoff = raw_payoff if raw_payoff >= 1 else -(1 / raw_payoff)

    # Max Drawdown
    cum = np.cumsum(df['net_pnl'].values)
    running_max = np.maximum.accumulate(cum)
    drawdowns = cum - running_max
    mdd = float(drawdowns.min())

    return {
        'n': n, 'n_win': n_win, 'n_loss': n_loss,
        'win_rate': win_rate,
        'avg_win': avg_win, 'avg_loss': avg_loss,
        'payoff': payoff,
        'profit_factor': pf,
        'signed_pf': signed_pf,
        'ev': ev,
        'total_pnl': float(df['net_pnl'].sum()),
        'max_loss_streak': max_streak,
        'max_drawdown': mdd,
        'best_trade': float(df['net_pnl'].max()),
        'worst_trade': float(df['net_pnl'].min()),
    }


def stats_df(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Per-group statistics DataFrame."""
    rows = []
    for grp, sub in df.groupby(group_col):
        s = compute_stats(sub)
        if s['n'] == 0:
            continue
        rows.append({
            '商品': grp,
            '筆數': s['n'],
            '勝率': f"{s['win_rate']:.1%}",
            '賠率': (f"{s['profit_factor']:.2f}"
                     if s['profit_factor'] != float('inf') else '∞'),
            '期望值': f"{s['ev']:,.0f}",
            '平均獲利': f"{s['avg_win']:,.0f}",
            '平均虧損': f"{s['avg_loss']:,.0f}",
            '總損益': s['total_pnl'],
            '最大連敗': s['max_loss_streak'],
        })
    return pd.DataFrame(rows).sort_values('總損益', ascending=False).reset_index(drop=True)


# ── Render helpers ─────────────────────────────────────────────────────────────

def _color(v: float) -> str:
    return "#ef5350" if v > 0 else ("#26a69a" if v < 0 else "#e0e0e0")


def _metric(label: str, value: str, color: str = "#e0e0e0"):
    return f"""<div class="metric-card">
  <div class="metric-label">{label}</div>
  <div class="metric-value" style="color:{color}">{value}</div>
</div>"""


def _fmt_signed_pf(spf: float) -> str:
    if spf == float('inf'):
        return "+∞"
    if spf == -float('inf'):
        return "-∞"
    return f"{spf:+.2f}"


def render_summary(s: dict):
    cols = st.columns(5)
    items = [
        ("總交易筆數",  f"{s['n']}",                                        "#e0e0e0"),
        ("勝率",        f"{s['win_rate']:.1%}  ({s['n_win']}勝/{s['n_loss']}敗)",
                                                                            "#4c9be8"),
        ("獲利因子",    _fmt_signed_pf(s['signed_pf']),                     _color(s['signed_pf'])),
        ("期望值/筆",   f"{s['ev']:+,.0f} 元",                              _color(s['ev'])),
        ("最大回撤",    f"{s['max_drawdown']:,.0f} 元",                     "#ff9800"),
    ]
    for col, (label, val, color) in zip(cols, items):
        col.markdown(_metric(label, val, color), unsafe_allow_html=True)

    cols2 = st.columns(5)
    po = s['payoff']
    po_str = _fmt_signed_pf(po)
    items2 = [
        ("總損益",       f"{s['total_pnl']:+,.0f} 元",  _color(s['total_pnl'])),
        ("平均獲利",     f"{s['avg_win']:,.0f} 元",     "#ef5350"),
        ("平均虧損",     f"{s['avg_loss']:,.0f} 元",    "#26a69a"),
        ("賠率",         po_str,                        _color(po)),
        ("最大連敗筆數", f"{s['max_loss_streak']} 筆",  "#ff9800"),
    ]
    for col, (label, val, color) in zip(cols2, items2):
        col.markdown(_metric(label, val, color), unsafe_allow_html=True)


def render_equity_curve(df: pd.DataFrame):
    dates = df['date'].values
    cum   = df['net_pnl'].cumsum().values

    # Max Drawdown
    running_max  = np.maximum.accumulate(cum)
    drawdown     = cum - running_max          # always <= 0
    mdd          = float(drawdown.min())
    mdd_idx      = int(drawdown.argmin())

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.65, 0.35],
        vertical_spacing=0.06,
        subplot_titles=('累計損益曲線', 'Max Drawdown'),
    )

    # ── Equity curve ────────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=dates, y=cum,
        mode='lines', name='累計損益',
        line=dict(color='#4c9be8', width=2),
        fill='tozeroy', fillcolor='rgba(76,155,232,0.10)',
    ), row=1, col=1)
    fig.add_hline(y=0, line_color='#616161', line_dash='dot', row=1, col=1)

    # ── Drawdown ─────────────────────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=dates, y=drawdown,
        mode='lines', name='回撤',
        line=dict(color='#ef5350', width=1.5),
        fill='tozeroy', fillcolor='rgba(239,83,80,0.15)',
    ), row=2, col=1)
    # Mark the deepest drawdown point
    fig.add_trace(go.Scatter(
        x=[dates[mdd_idx]], y=[mdd],
        mode='markers+text',
        marker=dict(color='#ff9800', size=10, symbol='x'),
        text=[f" MDD {mdd:,.0f}"],
        textposition='middle right',
        textfont=dict(color='#ff9800', size=11),
        name='最大回撤',
        showlegend=False,
    ), row=2, col=1)

    fig.update_layout(
        template=DARK,
        height=CHART_H,
        margin=dict(t=50, b=30),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
    )
    fig.update_yaxes(title_text='損益 (TWD)', row=1, col=1)
    fig.update_yaxes(title_text='回撤 (TWD)', row=2, col=1)
    fig.update_xaxes(title_text='日期', row=2, col=1)

    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"最大回撤 (Max Drawdown)：**{mdd:,.0f} TWD**")


def render_distribution(df: pd.DataFrame):
    fig = px.histogram(
        df, x='net_pnl', nbins=60,
        color_discrete_sequence=['#4c9be8'],
        labels={'net_pnl': '單筆損益 (TWD)', 'count': '筆數'},
        title='單筆損益分佈',
        template=DARK,
    )
    fig.add_vline(x=0, line_color='#ef5350', line_dash='dash')
    fig.update_layout(height=CHART_H, margin=dict(t=40, b=30))
    st.plotly_chart(fig, use_container_width=True)


def render_monthly(df: pd.DataFrame):
    mdf = (df.groupby('month')['net_pnl'].sum()
             .reset_index()
             .rename(columns={'net_pnl': '月損益'}))
    mdf['color'] = mdf['月損益'].apply(lambda v: '#ef5350' if v > 0 else '#26a69a')

    fig = go.Figure(go.Bar(
        x=mdf['month'], y=mdf['月損益'],
        marker_color=mdf['color'], name='月損益',
        text=mdf['月損益'].apply(lambda v: f"{v:+,.0f}"),
        textposition='outside',
    ))
    fig.update_layout(
        template=DARK, title='每月損益',
        xaxis_title='月份', yaxis_title='損益 (TWD)',
        height=CHART_H, margin=dict(t=40, b=30),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Monthly stats table
    rows = []
    for month, sub in df.groupby('month'):
        s = compute_stats(sub)
        rows.append({
            '月份': month,
            '筆數': s['n'],
            '勝率': f"{s['win_rate']:.1%}",
            '月損益': s['total_pnl'],
        })
    mst = pd.DataFrame(rows)

    def color_row(row):
        c = '#3d1a1a' if row['月損益'] > 0 else '#0d2b2b'
        return [f'background-color:{c}'] * len(row)

    mst['月損益'] = mst['月損益'].apply(lambda v: f"{v:+,.0f}")
    st.dataframe(mst, use_container_width=True, hide_index=True)


def render_product_table(sdf: pd.DataFrame):
    def color_pnl(val):
        try:
            v = float(str(val).replace(',', ''))
            return f'color: {"#ef5350" if v > 0 else "#26a69a"}'
        except Exception:
            return ''

    styled = sdf.copy()
    styled['總損益'] = styled['總損益'].apply(lambda v: f"{v:+,.0f}")
    st.dataframe(
        styled.style.applymap(color_pnl, subset=['總損益', '期望值', '平均虧損']),
        use_container_width=True, hide_index=True,
    )


def render_product_bars(df: pd.DataFrame, sdf: pd.DataFrame):
    sdf2 = sdf.copy()
    # '總損益' is numeric float at this point (formatted only in render_product_table)
    sdf2['pnl_val'] = pd.to_numeric(sdf2['總損益'], errors='coerce').fillna(0)
    sdf2['color']   = sdf2['pnl_val'].apply(lambda v: '#ef5350' if v > 0 else '#26a69a')
    sdf2['text']    = sdf2['pnl_val'].apply(lambda v: f"{v:+,.0f}")

    fig = go.Figure(go.Bar(
        x=sdf2['商品'], y=sdf2['pnl_val'],
        marker_color=sdf2['color'],
        text=sdf2['text'], textposition='outside',
    ))
    fig.update_layout(template=DARK, title='各商品總損益', height=CHART_H,
                      xaxis_title='商品', yaxis_title='損益 (TWD)',
                      margin=dict(t=40, b=30))
    st.plotly_chart(fig, use_container_width=True)


# ── Group analysis ─────────────────────────────────────────────────────────────

GROUP_ALGO = '程式交易'    # 小台指 + 小電子
GROUP_OPT  = '台指選擇權'
GROUP_DISC = '主觀交易'    # 微台指, 台指期, 其他股票期貨

GROUP_COLORS = {
    GROUP_ALGO: '#4c9be8',   # blue
    GROUP_OPT:  '#ff9800',   # orange
    GROUP_DISC: '#26a69a',   # teal
}
GROUP_ICONS = {
    GROUP_ALGO: '🤖',
    GROUP_OPT:  '📊',
    GROUP_DISC: '🧠',
}


def classify_group(base_prod: str) -> str:
    if base_prod in ('小台指', '小電子'):
        return GROUP_ALGO
    if '選擇權' in base_prod:
        return GROUP_OPT
    return GROUP_DISC


def render_group_comparison(df: pd.DataFrame):
    """Full-width comparison equity curve for all 3 groups."""
    fig = go.Figure()
    for grp, color in GROUP_COLORS.items():
        sub = df[df['group'] == grp].sort_values('date')
        if sub.empty:
            continue
        cum = sub['net_pnl'].cumsum().values
        fig.add_trace(go.Scatter(
            x=sub['date'].values, y=cum,
            mode='lines', name=grp,
            line=dict(color=color, width=2),
        ))
    fig.add_hline(y=0, line_color='#616161', line_dash='dot')
    fig.update_layout(
        template=DARK, title='三組累計損益比較',
        xaxis_title='日期', yaxis_title='損益 (TWD)',
        height=CHART_H, margin=dict(t=40, b=30),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_compact_summary(s: dict, color: str):
    """Slim key-value stats for group comparison columns."""
    if s.get('n', 0) == 0:
        st.info("此區間無資料")
        return
    items = [
        ("筆數",     f"{s['n']}"),
        ("勝率",     f"{s['win_rate']:.1%}  ({s['n_win']}勝/{s['n_loss']}敗)"),
        ("獲利因子",  _fmt_signed_pf(s['signed_pf'])),
        ("賠率",     _fmt_signed_pf(s['payoff'])),
        ("期望值/筆", f"{s['ev']:+,.0f} 元"),
        ("總損益",    f"{s['total_pnl']:+,.0f} 元"),
        ("最大回撤",  f"{s['max_drawdown']:,.0f} 元"),
        ("最大連敗",  f"{s['max_loss_streak']} 筆"),
    ]
    for label, val in items:
        st.markdown(
            f"<div style='display:flex;justify-content:space-between;"
            f"padding:5px 0;border-bottom:1px solid #2a2d3e'>"
            f"<span style='color:#9e9e9e;font-size:12px'>{label}</span>"
            f"<span style='color:{color};font-weight:600;font-size:13px'>{val}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )


# ── Page ───────────────────────────────────────────────────────────────────────

st.title("📈 期貨交易損益分析")
st.caption("支援 元大期貨 已實現損益明細 (.xls)　｜　凱基格式即將支援")

uploaded = st.file_uploader(
    "上傳期貨損益明細 (.xls / .xlsx)",
    type=["xls", "xlsx"],
    help="從券商後台匯出「已實現損益明細」Excel 檔後上傳",
)

if uploaded is None:
    st.info("請上傳元大或凱基期貨匯出的已實現損益明細 Excel 檔 (.xls)")
    st.markdown("""
**元大匯出路徑：**
元大期貨網路下單 → 交易查詢 → 已實現損益查詢 → 匯出 Excel

**凱基匯出路徑：**
凱基期貨 → 損益查詢 → 已實現損益 → 匯出
    """)
    st.stop()

raw = uploaded.read()

# Auto-detect broker, allow manual override
auto_broker = detect_broker(raw)
broker = st.radio("券商格式", ["元大", "凱基"], index=0 if auto_broker == '元大' else 1,
                  horizontal=True)
st.caption(f"自動偵測：{auto_broker}")

with st.spinner("解析資料中…"):
    if broker == '元大':
        df = parse_yuanta(raw)
    else:
        df = parse_kgi(raw)

if df.empty:
    st.error("無法解析檔案，請確認格式是否正確。")
    st.stop()

# ── Date range filter ──────────────────────────────────────────────────────────
min_d, max_d = df['date'].min().date(), df['date'].max().date()
col_a, col_b = st.columns(2)
with col_a:
    start_d = st.date_input("起始日期", value=min_d, min_value=min_d, max_value=max_d)
with col_b:
    end_d   = st.date_input("結束日期", value=max_d, min_value=min_d, max_value=max_d)

df = df[(df['date'].dt.date >= start_d) & (df['date'].dt.date <= end_d)]
if df.empty:
    st.warning("所選日期範圍內無資料。")
    st.stop()

df['group'] = df['base_prod'].apply(classify_group)

st.divider()

# ── Overall stats ──────────────────────────────────────────────────────────────
st.markdown("### 📊 整體績效")
s = compute_stats(df)
render_summary(s)

st.divider()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_curve, tab_groups, tab_prod, tab_month, tab_detail = st.tabs([
    "📉 損益曲線", "📈 分組績效", "🏷️ 各商品分析", "📅 月度分析", "📋 交易明細"
])

with tab_curve:
    col1, col2 = st.columns(2)
    with col1:
        render_equity_curve(df)
    with col2:
        render_distribution(df)

with tab_groups:
    # ── Overview comparison ─────────────────────────────────────────────────
    render_group_comparison(df)
    st.divider()

    # ── Per-group compact stats ─────────────────────────────────────────────
    st.markdown("#### 各組整體績效")
    gcols = st.columns(3)
    for col, (grp, color) in zip(gcols, GROUP_COLORS.items()):
        with col:
            icon = GROUP_ICONS[grp]
            st.markdown(
                f"<div style='font-size:16px;font-weight:700;"
                f"color:{color};margin-bottom:8px'>{icon} {grp}</div>",
                unsafe_allow_html=True,
            )
            sub = df[df['group'] == grp]
            render_compact_summary(compute_stats(sub), color)

    st.divider()

    # ── Per-group equity curve + distribution ───────────────────────────────
    st.markdown("#### 各組損益曲線")
    g_sub_tabs = st.tabs([
        f"{GROUP_ICONS[g]} {g}" for g in GROUP_COLORS
    ])
    for subtab, grp in zip(g_sub_tabs, GROUP_COLORS):
        with subtab:
            sub = df[df['group'] == grp].sort_values('date').reset_index(drop=True)
            if sub.empty:
                st.info(f"{grp} 在所選區間無資料")
            else:
                c1, c2 = st.columns(2)
                with c1:
                    render_equity_curve(sub)
                with c2:
                    render_distribution(sub)

with tab_prod:
    sdf = stats_df(df, 'base_prod')
    sdf = sdf.rename(columns={'商品': '商品'})
    render_product_bars(df, sdf)
    st.markdown("#### 各商品統計")
    render_product_table(sdf)

with tab_month:
    render_monthly(df)

with tab_detail:
    # Filters
    prods = ['全部'] + sorted(df['base_prod'].unique().tolist())
    sel_prod = st.selectbox("篩選商品", prods)
    show_df = df if sel_prod == '全部' else df[df['base_prod'] == sel_prod]

    disp = show_df[['date', 'base_prod', 'lots', 'direction',
                     'open_price', 'close_price', 'gross_pnl',
                     'commission', 'tax', 'net_pnl']].copy()
    disp.columns = ['日期', '商品', '口數', '方向',
                    '開倉價', '平倉價', '毛損益', '手續費', '期交稅', '淨損益']
    disp['日期'] = disp['日期'].dt.strftime('%Y-%m-%d')

    def color_net(val):
        try:
            return f'color: {"#ef5350" if float(val) > 0 else "#26a69a"}'
        except Exception:
            return ''

    st.dataframe(
        disp.style.applymap(color_net, subset=['毛損益', '淨損益']),
        use_container_width=True, hide_index=True, height=520,
    )

    # Download
    csv = disp.to_csv(index=False, encoding='utf-8-sig')
    st.download_button("⬇️ 下載明細 CSV", csv, "futures_pnl.csv", "text/csv")
