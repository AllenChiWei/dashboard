import streamlit as st
import pandas as pd
from sqlalchemy import text
from src.database.connection import db

st.set_page_config(
    page_title="Financial AI Dashboard",
    page_icon="📈",
    layout="wide"
)

st.title("Financial AI Dashboard 🚀")
st.markdown("### Welcome to the Financial Data Intelligence System")

st.markdown("""
This dashboard provides real-time insights into financial markets using data collected via our automated ETL pipeline.

**Modules:**
- 📊 **Market Overview**: View historical data and technical indicators.
- 🤖 **AI Predictions**: (Coming Soon) Machine learning based trend forecasting.
- ⚙️ **System Status**: Check the health of crawlers and database.
""")

# Quick Stats / System Health
st.header("System Status")

try:
    session = db.get_session()
    # Count total records
    result = session.execute(text("SELECT COUNT(*) FROM market_data"))
    count = result.scalar()
    
    # Get latest update date
    result = session.execute(text("SELECT MAX(date) FROM market_data"))
    latest_date = result.scalar()
    
    col1, col2 = st.columns(2)
    col1.metric("Total Data Points", f"{count:,}")
    col2.metric("Last Data Update", str(latest_date))
    
    session.close()
except Exception as e:
    st.error(f"Database Connection Failed: {e}")
    st.warning("Please ensure the PostgreSQL database is running and configured correctly in .env")

st.sidebar.success("Select a page above.")
