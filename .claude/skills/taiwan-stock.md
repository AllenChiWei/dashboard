# Taiwan Stock Analysis

Look up a Taiwan stock and show analysis or add it to the dashboard.

## Steps

1. Ask for the stock symbol (e.g., "2330", "0050") if not provided
2. Use FinLab to fetch price and financial data:

```python
import finlab, os
finlab.login(os.getenv('FINLAB_API_KEY', ''))
from finlab import data

close = data.get('price:收盤價')[symbol]
volume = data.get('price:成交股數')[symbol]
pe = data.get('fundamental_features:本益比')[symbol]
```

3. Calculate key metrics: 52-week high/low, current price vs MA20/MA60, RSI-14
4. If adding to the K-line page (`3_Taiwan_Stocks.py`), follow the existing FinLab + Plotly candlestick pattern
5. For charts: use `type='category'` on x-axis with string dates to eliminate weekend gaps

## FinLab Data Keys (常用)

| 資料 | Key |
|------|-----|
| 收盤價 | `price:收盤價` |
| 成交量 | `price:成交股數` |
| 本益比 | `fundamental_features:本益比` |
| 股價淨值比 | `fundamental_features:股價淨值比` |
| 月營收 | `monthly_revenue:當月營收` |

## Chart Convention

```python
import plotly.graph_objects as go

fig = go.Figure(data=[go.Candlestick(
    x=df.index.astype(str),
    open=df['open'], high=df['high'],
    low=df['low'], close=df['close'],
    increasing_line_color='#ef5350',   # 漲=紅
    decreasing_line_color='#26a69a',   # 跌=綠
)])
fig.update_layout(
    template='plotly_dark',
    xaxis_type='category',  # 去除週末空白
    xaxis_rangeslider_visible=False
)
```

## Environment

- FinLab login: `finlab.login(os.getenv('FINLAB_API_KEY', ''))` (key in `.env`)
- User has VIP account — all data available
