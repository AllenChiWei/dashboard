import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from sqlalchemy import text
from src.database.connection import db

st.set_page_config(page_title="Market Overview", page_icon="📊", layout="wide")

st.title("Market Overview 📊")

@st.cache_data(ttl=600)
def load_data(symbol):
    query = text(
        "SELECT * FROM market_data WHERE symbol = :symbol ORDER BY date ASC"
    )
    with db.engine.connect() as conn:
        result = conn.execute(query, {'symbol': symbol})
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
    return df

# Sidebar controls
st.sidebar.header("Filter Options")

# Get available symbols
try:
    session = db.get_session()
    symbols = session.execute(text("SELECT DISTINCT symbol FROM market_data ORDER BY symbol")).scalars().all()
    session.close()
except:
    symbols = []

if not symbols:
    st.warning("No stock data found in database. Please run the ETL pipeline first.")
    selected_symbol = st.text_input("Enter Symbol manually (e.g., 2330.TW)", "2330.TW")
else:
    selected_symbol = st.sidebar.selectbox("Select Symbol", symbols)

# Display stock data
if selected_symbol:
    df = load_data(selected_symbol)
    
    if not df.empty:
        st.subheader(f"Price History: {selected_symbol}")
        
        # Create tabs for different views
        tab1, tab2, tab3 = st.tabs(["Chart", "Analysis", "Raw Data"])
        
        with tab1:
            # Candlestick Chart
            fig = go.Figure(data=[go.Candlestick(x=df['date'],
                            open=df['open'],
                            high=df['high'],
                            low=df['low'],
                            close=df['close'],
                            name=selected_symbol)])
            
            fig.update_layout(
                title=f"{selected_symbol} Candlestick Chart",
                xaxis_rangeslider_visible=False,
                template="plotly_dark",
                height=500
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Volume Chart
            fig_vol = go.Figure()
            fig_vol.add_trace(go.Bar(x=df['date'], y=df['volume'], name='Volume',
                                     marker=dict(color='lightblue')))
            fig_vol.update_layout(
                title=f"{selected_symbol} Trading Volume",
                xaxis_title="Date",
                yaxis_title="Volume",
                template="plotly_dark",
                height=300
            )
            st.plotly_chart(fig_vol, use_container_width=True)
        
        with tab2:
            # Technical Analysis
            st.subheader("Technical Indicators")
            
            col1, col2, col3, col4 = st.columns(4)
            
            latest = df.iloc[-1]
            with col1:
                st.metric("Current Close", f"{latest['close']:.2f}")
            with col2:
                prev_close = df.iloc[-2]['close'] if len(df) > 1 else latest['close']
                change = latest['close'] - prev_close
                pct_change = (change / prev_close * 100) if prev_close != 0 else 0
                st.metric("Change", f"{change:.2f}", f"{pct_change:.2f}%")
            with col3:
                st.metric("Day High", f"{latest['high']:.2f}")
            with col4:
                st.metric("Day Low", f"{latest['low']:.2f}")
            
            # Calculate and display moving averages
            if len(df) >= 20:
                df_copy = df.copy()
                df_copy['MA20'] = df_copy['close'].rolling(window=20).mean()
                df_copy['MA50'] = df_copy['close'].rolling(window=50).mean() if len(df) >= 50 else None
                
                fig_ma = go.Figure()
                fig_ma.add_trace(go.Scatter(x=df_copy['date'], y=df_copy['close'],
                                           name='Close', line=dict(color='blue')))
                fig_ma.add_trace(go.Scatter(x=df_copy['date'], y=df_copy['MA20'],
                                           name='MA20', line=dict(color='orange', dash='dash')))
                if df_copy['MA50'] is not None:
                    fig_ma.add_trace(go.Scatter(x=df_copy['date'], y=df_copy['MA50'],
                                               name='MA50', line=dict(color='red', dash='dash')))
                
                fig_ma.update_layout(
                    title=f"{selected_symbol} Moving Averages",
                    xaxis_title="Date",
                    yaxis_title="Price",
                    template="plotly_dark",
                    height=400
                )
                st.plotly_chart(fig_ma, use_container_width=True)
        
        with tab3:
            st.dataframe(df.sort_values(by='date', ascending=False), use_container_width=True)
            
    else:
        st.info(f"No data available for {selected_symbol}")

# Display correlation matrix
st.divider()
st.header("Market Correlation Analysis")

try:
    session = db.get_session()
    # Get data for top symbols
    top_symbols_query = text(
        "SELECT DISTINCT symbol FROM market_data GROUP BY symbol LIMIT 10"
    )
    top_symbols = session.execute(top_symbols_query).scalars().all()
    session.close()
    
    if top_symbols and len(top_symbols) > 1:
        correlation_data = {}
        
        for symbol in top_symbols:
            df_sym = load_data(symbol)
            if not df_sym.empty and 'close' in df_sym.columns:
                # Normalize dates
                df_sym['date'] = pd.to_datetime(df_sym['date'])
                correlation_data[symbol] = df_sym.set_index('date')['close']
        
        if correlation_data:
            df_corr = pd.DataFrame(correlation_data)
            corr_matrix = df_corr.corr()
            
            fig_corr = go.Figure(data=go.Heatmap(
                z=corr_matrix.values,
                x=corr_matrix.columns,
                y=corr_matrix.columns,
                colorscale='RdBu',
                zmid=0,
                zmin=-1,
                zmax=1
            ))
            
            fig_corr.update_layout(
                title="Price Correlation Matrix",
                height=500
            )
            st.plotly_chart(fig_corr, use_container_width=True)
except:
    st.info("Correlation analysis data not available")

st.sidebar.info("💡 Tip: Use the ETL pipeline to fetch latest market data regularly.")
