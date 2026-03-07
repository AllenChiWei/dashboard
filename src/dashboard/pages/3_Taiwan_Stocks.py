import os
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from dotenv import load_dotenv
import finlab
from finlab import data

load_dotenv()

st.set_page_config(page_title="Taiwan Stocks", page_icon="🇹🇼", layout="wide")

# Login FinLab
@st.cache_resource
def init_finlab():
    api_key = os.getenv("FINLAB_API_KEY", "")
    finlab.login(api_key)

init_finlab()

st.title("🇹🇼 台灣股市總覽")

# --- Load stock list ---
@st.cache_data(ttl=3600)
def get_stock_list():
    close = data.get('price:收盤價')
    return sorted(close.columns.tolist())

@st.cache_data(ttl=600)
def get_price_data(symbol):
    close = data.get('price:收盤價')
    open_ = data.get('price:開盤價')
    high = data.get('price:最高價')
    low = data.get('price:最低價')
    volume = data.get('price:成交股數')

    df = pd.DataFrame({
        'close': close[symbol],
        'open': open_[symbol],
        'high': high[symbol],
        'low': low[symbol],
        'volume': volume[symbol],
    }).dropna()
    return df

@st.cache_data(ttl=3600)
def get_fundamental(symbol):
    try:
        pe = data.get('price_earning_ratio:本益比')
        pb = data.get('price_earning_ratio:股價淨值比')
        return {
            'PE': round(pe[symbol].dropna().iloc[-1], 2) if symbol in pe.columns else None,
            'PB': round(pb[symbol].dropna().iloc[-1], 2) if symbol in pb.columns else None,
        }
    except:
        return {}

# --- Sidebar ---
st.sidebar.header("選股設定")

with st.spinner("載入股票清單..."):
    stock_list = get_stock_list()

selected = st.sidebar.selectbox("選擇股票代號", stock_list, index=stock_list.index("0050") if "0050" in stock_list else 0)

days = st.sidebar.selectbox("顯示期間", [30, 60, 90, 180, 365], index=2)

st.sidebar.markdown("---")
st.sidebar.subheader("均線設定")
ma_options = st.sidebar.multiselect(
    "顯示均線",
    options=[5, 10, 20, 60, 120, 240],
    default=[5, 20, 60]
)

MA_COLORS = {5: 'yellow', 10: 'cyan', 20: 'orange', 60: 'red', 120: 'magenta', 240: 'lightgreen'}

# --- Load data ---
with st.spinner(f"載入 {selected} 資料..."):
    df = get_price_data(selected)

if df.empty:
    st.warning(f"查無 {selected} 的資料")
    st.stop()

df_filtered = df.last(f"{days}D")

# --- Metrics ---
latest = df_filtered.iloc[-1]
prev = df_filtered.iloc[-2] if len(df_filtered) > 1 else latest
change = latest['close'] - prev['close']
pct = change / prev['close'] * 100 if prev['close'] else 0

fund = get_fundamental(selected)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("收盤價", f"{latest['close']:.2f}", f"{change:+.2f} ({pct:+.2f}%)")
col2.metric("最高", f"{latest['high']:.2f}")
col3.metric("最低", f"{latest['low']:.2f}")
if fund.get('PE'):
    col4.metric("本益比 (PE)", f"{fund['PE']:.1f}")
if fund.get('PB'):
    col5.metric("股價淨值比 (PB)", f"{fund['PB']:.2f}")

# 只保留有交易的日期（去除空值），並轉成字串作為類別軸，消除週末與假日空白
df_plot = df_filtered.dropna(subset=['open', 'high', 'low', 'close'])
x_labels = df_plot.index.strftime('%Y-%m-%d').tolist()

# 計算均線（用完整資料避免邊界值不足）
df_ma = df.copy()
for ma in ma_options:
    df_ma[f'MA{ma}'] = df_ma['close'].rolling(ma).mean()
df_ma_filtered = df_ma.loc[df_plot.index]

# --- K線圖（含均線）---
fig = go.Figure()

fig.add_trace(go.Candlestick(
    x=x_labels,
    open=df_plot['open'],
    high=df_plot['high'],
    low=df_plot['low'],
    close=df_plot['close'],
    name=selected,
    increasing_line_color='red',
    decreasing_line_color='green'
))

for ma in ma_options:
    col_name = f'MA{ma}'
    fig.add_trace(go.Scatter(
        x=x_labels,
        y=df_ma_filtered[col_name],
        name=col_name,
        line=dict(color=MA_COLORS.get(ma, 'white'), width=1.5),
        hovertemplate=f'MA{ma}: %{{y:.2f}}<extra></extra>'
    ))

fig.update_layout(
    title=f"{selected} K線圖",
    xaxis=dict(
        type='category',
        tickangle=-45,
        rangeslider_visible=False,
    ),
    yaxis_title="價格",
    template="plotly_dark",
    height=550,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    hovermode='x unified'
)
st.plotly_chart(fig, use_container_width=True)

# --- 成交量 ---
vol_colors = ['red' if df_plot['close'].iloc[i] >= df_plot['open'].iloc[i] else 'green'
              for i in range(len(df_plot))]
fig_vol = go.Figure()
fig_vol.add_trace(go.Bar(x=x_labels, y=df_plot['volume'], marker_color=vol_colors, name='成交量'))
fig_vol.update_layout(
    xaxis=dict(type='category', tickangle=-45),
    template="plotly_dark",
    height=200,
    margin=dict(t=10)
)
st.plotly_chart(fig_vol, use_container_width=True)

# --- RSI ---
delta = df_ma_filtered['close'].diff()
gain = delta.clip(lower=0).rolling(14).mean()
loss = (-delta.clip(upper=0)).rolling(14).mean()
rsi = 100 - (100 / (1 + gain / loss))

fig_rsi = go.Figure()
fig_rsi.add_trace(go.Scatter(x=x_labels, y=rsi.values, name='RSI(14)', line=dict(color='cyan')))
fig_rsi.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="超買 70")
fig_rsi.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="超賣 30")
fig_rsi.update_layout(
    title="RSI (14)",
    xaxis=dict(type='category', tickangle=-45),
    template="plotly_dark",
    height=200,
    yaxis=dict(range=[0, 100]),
    margin=dict(t=30)
)
st.plotly_chart(fig_rsi, use_container_width=True)

st.caption("資料來源：FinLab，僅供參考，不構成投資建議。")
