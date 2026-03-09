# Debug Data Fetch

Debug a failing data fetch function in the dashboard. Diagnose API issues, parse errors, or missing fields.

## Steps

1. Ask which page/function is failing if not specified
2. Read the relevant page file to find the fetch function
3. Check the data source:
   - For external APIs: verify the URL, headers, and response schema
   - For TWSE/FinMind APIs: check if rate limits or schema changes occurred
   - For `finlab`: verify API key is set in `.env` and `finlab.login()` is called
   - For `yfinance`: check ticker symbol validity
4. If the API response format changed, update the field name extraction logic
5. Add or improve error handling so the page degrades gracefully (returns `None` instead of crashing)
6. Confirm the fix by tracing through the logic with a sample response

## Common Issues

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `KeyError` on JSON field | API schema changed | Re-check response structure |
| `requests.exceptions.Timeout` | Slow API | Increase `timeout=` parameter |
| `None` returned silently | Exception swallowed | Add `print(e)` inside `except` temporarily |
| FinLab `LoginError` | Bad API key or expired | Re-check `FINLAB_API_KEY` in `.env` |
| VIX CSV parse error | CBOE format change | Re-inspect column names from `df.columns` |
| Taiwan VIX empty | Market closed / weekend | Check `CLastPrice` is non-zero |

## Environment

- Python: `C:/Users/Master/Anaconda3/envs/dashboard/python.exe`
- Working dir: `D:/ai/Dashboard`
- `.env` file contains real credentials (never commit)
- Run a quick test: `C:/Users/Master/Anaconda3/envs/dashboard/python.exe -c "from src.dashboard.pages.X import ..."`
