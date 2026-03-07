import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from sqlalchemy import text
from src.database.connection import db

st.set_page_config(
    page_title="Market Indicators",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Market Indicators Dashboard")

# Initialize session
session = db.get_session()

# Define date range selector
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input(
        "Start Date",
        value=datetime.now().date() - timedelta(days=30)
    )
with col2:
    end_date = st.date_input(
        "End Date",
        value=datetime.now().date()
    )

try:
    # 1. VIX Indicators
    st.header("📈 Volatility Index (VIX)")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("US VIX Index")
        try:
            query = text("""
                SELECT date, value, status FROM vix_data 
                WHERE index_name = 'vix' 
                AND date BETWEEN :start_date AND :end_date
                ORDER BY date ASC
            """)
            df_vix = pd.read_sql(query, session, params={
                'start_date': start_date,
                'end_date': end_date
            })
            
            if not df_vix.empty:
                # Chart
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_vix['date'], y=df_vix['value'],
                    mode='lines', name='VIX',
                    line=dict(color='red', width=2)
                ))
                fig.update_layout(
                    title="US VIX Trend",
                    xaxis_title="Date",
                    yaxis_title="VIX Value",
                    height=400,
                    hovermode='x unified'
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Latest value
                latest = df_vix.iloc[-1]
                st.metric(
                    "Current VIX",
                    f"{latest['value']:.2f}",
                    f"Status: {latest['status']}"
                )
            else:
                st.warning("No US VIX data available")
        except Exception as e:
            st.error(f"Error loading US VIX data: {e}")
    
    with col2:
        st.subheader("Taiwan TVIX Index")
        try:
            query = text("""
                SELECT date, value, status FROM vix_data 
                WHERE index_name = 'tvix' 
                AND date BETWEEN :start_date AND :end_date
                ORDER BY date ASC
            """)
            df_tvix = pd.read_sql(query, session, params={
                'start_date': start_date,
                'end_date': end_date
            })
            
            if not df_tvix.empty:
                # Chart
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_tvix['date'], y=df_tvix['value'],
                    mode='lines', name='TVIX',
                    line=dict(color='orange', width=2)
                ))
                fig.update_layout(
                    title="Taiwan TVIX Trend",
                    xaxis_title="Date",
                    yaxis_title="TVIX Value",
                    height=400,
                    hovermode='x unified'
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Latest value
                latest = df_tvix.iloc[-1]
                st.metric(
                    "Current TVIX",
                    f"{latest['value']:.2f}",
                    f"Status: {latest['status']}"
                )
            else:
                st.warning("No Taiwan TVIX data available")
        except Exception as e:
            st.error(f"Error loading Taiwan TVIX data: {e}")
    
    # 2. Taiwan Margin Maintenance Rate
    st.header("💰 Taiwan Margin Maintenance Rate")
    try:
        query = text("""
            SELECT date, margin_maintenance_rate, status FROM margin_data 
            WHERE market = 'taiwan'
            AND date BETWEEN :start_date AND :end_date
            ORDER BY date ASC
        """)
        df_margin = pd.read_sql(query, session, params={
            'start_date': start_date,
            'end_date': end_date
        })
        
        if not df_margin.empty:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_margin['date'], y=df_margin['margin_maintenance_rate'],
                    mode='lines+markers', name='Margin Rate',
                    line=dict(color='green', width=2),
                    marker=dict(size=8)
                ))
                
                # Add risk threshold bands
                fig.add_hline(y=200, line_dash="dash", line_color="yellow",
                             annotation_text="Low Risk Threshold", 
                             annotation_position="right")
                fig.add_hline(y=300, line_dash="dash", line_color="red",
                             annotation_text="High Risk Threshold",
                             annotation_position="right")
                
                fig.update_layout(
                    title="Taiwan Stock Margin Maintenance Rate (%)",
                    xaxis_title="Date",
                    yaxis_title="Rate (%)",
                    height=400,
                    hovermode='x unified'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                latest = df_margin.iloc[-1]
                st.metric(
                    "Current Rate",
                    f"{latest['margin_maintenance_rate']:.2f}%",
                    f"Risk: {latest['status']}"
                )
                
                # Risk interpretation
                st.info("""
                    **Risk Levels:**
                    - 🟢 Low Risk: < 200%
                    - 🟡 Medium Risk: 200-300%
                    - 🔴 High Risk: > 300%
                """)
        else:
            st.warning("No margin data available")
    except Exception as e:
        st.error(f"Error loading margin data: {e}")
    
    # 3. Fear & Greed Index
    st.header("😨 CNN Fear & Greed Index")
    try:
        query = text("""
            SELECT date, value, status FROM sentiment_data 
            WHERE name = 'fear_and_greed'
            AND date BETWEEN :start_date AND :end_date
            ORDER BY date ASC
        """)
        df_fg = pd.read_sql(query, session, params={
            'start_date': start_date,
            'end_date': end_date
        })
        
        if not df_fg.empty:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                fig = go.Figure()
                colors = []
                for val in df_fg['value']:
                    if val < 25:
                        colors.append('darkred')
                    elif val < 45:
                        colors.append('red')
                    elif val < 55:
                        colors.append('yellow')
                    elif val < 75:
                        colors.append('lightgreen')
                    else:
                        colors.append('darkgreen')
                
                fig.add_trace(go.Bar(
                    x=df_fg['date'], y=df_fg['value'],
                    marker=dict(color=colors),
                    name='Fear & Greed'
                ))
                
                fig.update_layout(
                    title="CNN Fear & Greed Index (0-100)",
                    xaxis_title="Date",
                    yaxis_title="Index Value",
                    height=400,
                    yaxis=dict(range=[0, 100])
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                latest = df_fg.iloc[-1]
                st.metric(
                    "Current Index",
                    f"{latest['value']:.0f}",
                    f"Sentiment: {latest['status'].upper()}"
                )
                
                # Sentiment interpretation
                st.info("""
                    **Sentiment Scale:**
                    - 🔴 Extreme Fear: 0-25
                    - 😟 Fear: 25-45
                    - 😐 Neutral: 45-55
                    - 😊 Greed: 55-75
                    - 🤑 Extreme Greed: 75-100
                """)
        else:
            st.warning("No Fear & Greed data available")
    except Exception as e:
        st.error(f"Error loading Fear & Greed data: {e}")
    
    # 4. Data Comparison Table
    st.header("📋 All Indicators Summary")
    
    summary_data = {
        'Indicator': [],
        'Latest Value': [],
        'Status': [],
        'Last Updated': []
    }
    
    # VIX
    try:
        query = text("SELECT value, status, date FROM vix_data WHERE index_name = 'vix' ORDER BY date DESC LIMIT 1")
        result = session.execute(query).fetchone()
        if result:
            summary_data['Indicator'].append('US VIX')
            summary_data['Latest Value'].append(f"{result[0]:.2f}")
            summary_data['Status'].append(result[1])
            summary_data['Last Updated'].append(str(result[2]))
    except:
        pass
    
    # TVIX
    try:
        query = text("SELECT value, status, date FROM vix_data WHERE index_name = 'tvix' ORDER BY date DESC LIMIT 1")
        result = session.execute(query).fetchone()
        if result:
            summary_data['Indicator'].append('Taiwan TVIX')
            summary_data['Latest Value'].append(f"{result[0]:.2f}")
            summary_data['Status'].append(result[1])
            summary_data['Last Updated'].append(str(result[2]))
    except:
        pass
    
    # Margin
    try:
        query = text("SELECT margin_maintenance_rate, status, date FROM margin_data WHERE market = 'taiwan' ORDER BY date DESC LIMIT 1")
        result = session.execute(query).fetchone()
        if result:
            summary_data['Indicator'].append('Taiwan Margin Rate')
            summary_data['Latest Value'].append(f"{result[0]:.2f}%")
            summary_data['Status'].append(result[1])
            summary_data['Last Updated'].append(str(result[2]))
    except:
        pass
    
    # Fear & Greed
    try:
        query = text("SELECT value, status, date FROM sentiment_data WHERE name = 'fear_and_greed' ORDER BY date DESC LIMIT 1")
        result = session.execute(query).fetchone()
        if result:
            summary_data['Indicator'].append('Fear & Greed')
            summary_data['Latest Value'].append(f"{result[0]:.0f}")
            summary_data['Status'].append(result[1])
            summary_data['Last Updated'].append(str(result[2]))
    except:
        pass
    
    if summary_data['Indicator']:
        df_summary = pd.DataFrame(summary_data)
        st.dataframe(df_summary, use_container_width=True, hide_index=True)
    else:
        st.info("No data available. Please run the ETL pipeline to populate the database.")
    
except Exception as e:
    st.error(f"Dashboard Error: {e}")
    st.info("Please ensure the database is properly configured and the ETL pipeline has been run.")
finally:
    session.close()

# Refresh info
st.info("💡 Tip: The dashboard updates whenever new data is fetched by the ETL pipeline. Run the ETL pipeline regularly to keep data fresh.")
