# Add Market Indicator

Add a new market indicator (chart + metric) to the Financial Indicators page (`src/dashboard/pages/2_Financial_Indicators.py`).

## Steps

1. Ask the user what indicator to add (name, data source URL, update frequency) if not provided
2. Read the current `2_Financial_Indicators.py` to understand the existing structure
3. Add a new `@st.cache_data(ttl=N)` fetch function following the pattern of existing ones (e.g., `_get_vix_current()`, `_get_taiwan_vix()`)
4. Add the indicator value to the `_compute_fear_score()` weighted formula if it's a fear/sentiment indicator
5. Add a metric card in the top quick-view strip (5-column row)
6. Add a Plotly chart in the 2×2 chart grid, or extend to a new row
7. Update the composite fear score weights to sum to 1.0
8. Test that the page still renders without errors

## Data Source Patterns

- REST GET with JSON response: use `requests.get(url, timeout=10).json()`
- REST POST with JSON body: use `requests.post(url, json={}, headers={...}, timeout=10)`
- Python library (e.g., `fear_and_greed`): import inside the cached function
- TWSE open API: base URL `https://openapi.twse.com.tw/v1/`

## Fear Score Weights (current total = 1.0)

- US VIX: 0.35
- TW VIX: 0.25
- Fear & Greed: 0.25
- 融資維持率: 0.15

When adding a new indicator, redistribute weights proportionally so they still sum to 1.0.

## Chart Style

```python
fig = go.Figure()
fig.add_trace(go.Scatter(x=dates, y=values, mode='lines', line=dict(color='#00bfff', width=1.5)))
fig.update_layout(template='plotly_dark', height=280, margin=dict(l=40,r=20,t=30,b=30))
st.plotly_chart(fig, use_container_width=True)
```
