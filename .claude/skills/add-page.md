# Add Dashboard Page

Add a new Streamlit page to the dashboard following project conventions.

## Steps

1. Ask the user for the page name and purpose if not provided
2. Determine the next page number by checking existing files in `src/dashboard/pages/`
3. Create the new page file `src/dashboard/pages/{N}_{PageName}.py` with:
   - `st.set_page_config()` with matching dark-theme style
   - The standard CSS block (tech-trader dark style from page 2)
   - Header section with monospace font and `#00bfff` color
   - `@st.cache_data(ttl=600)` for any data fetching functions
   - Plotly charts with `template="plotly_dark"`
4. If the page fetches external data, add appropriate error handling and loading spinners
5. Report the file path created and how to access it in the browser

## Conventions

- Page files: `src/dashboard/pages/{N}_{Name}.py`
- Dark theme CSS: copy the `<style>` block from `src/dashboard/pages/2_Financial_Indicators.py`
- Chart template: always `template="plotly_dark"`
- Taiwan stock colors: red=up (`#ef5350`), green=down (`#26a69a`)
- Cache: `@st.cache_data(ttl=600)` for data, `@st.cache_resource` for connections
- SQLAlchemy: use `conn.execute(query)` + `pd.DataFrame(result.fetchall(), columns=result.keys())`
- Imports: `import streamlit as st`, `import pandas as pd`, `import plotly.graph_objects as go`
