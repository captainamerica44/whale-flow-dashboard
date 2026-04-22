import streamlit as st
import pandas as pd
import plotly.express as px

# Set the page layout to wide
st.set_page_config(page_title="Whale Flow Dashboard", layout="wide")
st.title("🐋 Whale Flow Dashboard")

@st.cache_data(ttl=60)
def load_data():
    try:
        # Swap YOUR_SHEET_ID with the ID you copied in Phase 1
        SHEET_ID = "1goGTrEiqm7IYhD8mSZSBF2-kURu1MA55xYnvUH1sqhA" 
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
        df = pd.read_csv(url)
        
        def clean_number(val):
            if pd.isna(val): return 0
            val = str(val).replace('$', '').replace(',', '').strip().upper()
            if 'M' in val:
                return float(val.replace('M', '')) * 1000000
            elif 'K' in val:
                return float(val.replace('K', '')) * 1000
            try:
                return float(val)
            except ValueError:
                return 0
                
        df['Premium Value'] = df['Premium'].apply(clean_number)
        df['Volume Num'] = df['Volume'].apply(clean_number)
        df['OI Num'] = df['Open Interest'].apply(clean_number)
        
        # Calculate Days to Expiration (DTE)
        df['Expiration Date'] = pd.to_datetime(df['Expiration'], errors='coerce')
        today = pd.to_datetime('today')
        df['DTE'] = (df['Expiration Date'] - today).dt.days
        
        # EXACT BUCKETING AS REQUESTED
        def categorize_term(dte):
            if pd.isna(dte): return "Unknown"
            if dte <= 7: return "0-7 Days (Immediate)"
            if dte <= 45: return "8-45 Days (Tactical)"
            return "45+ Days (Strategic)"
            
        df['DTE Bucket'] = df['DTE'].apply(categorize_term)
        return df
    except FileNotFoundError:
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.warning("Waiting for data. Ensure flow_tracker.py is running!")
    st.stop()

st.sidebar.header("Controls")

# 1. Initialize filtered_df (Premium filter removed)
filtered_df = df.copy()

# 2. Ticker Filter
tickers = ["All"] + sorted(filtered_df['Ticker'].dropna().unique().tolist())
selected_ticker = st.sidebar.selectbox("Filter by Ticker", tickers)

# 2.5 Moneyness Filter (ITM/OTM)
if "ITM/OTM" in df.columns:
    moneyness_options = ["All", "ITM", "OTM"]
    selected_moneyness = st.sidebar.selectbox("Filter by Moneyness", moneyness_options)
    
    if selected_moneyness != "All":
        filtered_df = filtered_df[filtered_df['ITM/OTM'] == selected_moneyness]

if selected_ticker != "All":
    filtered_df = filtered_df[filtered_df['Ticker'] == selected_ticker]

# 3. Create Tabs for DTE Buckets
st.subheader("Total Premium by Ticker (Calls vs Puts)")
tab1, tab2, tab3 = st.tabs(["0-7 Days (Immediate)", "8-45 Days (Tactical)", "45+ Days (Strategic)"])

# Helper function to draw the Plotly horizontal bar chart
def draw_bucket_chart(bucket_name):
    bucket_data = filtered_df[filtered_df['DTE Bucket'] == bucket_name]
    if not bucket_data.empty:
        # Group by Ticker and Type to sum the premium
        chart_data = bucket_data.groupby(["Ticker", "Type"])["Premium Value"].sum().reset_index()
        
        # Create the Plotly figure
        fig = px.bar(
            chart_data, 
            x="Premium Value", 
            y="Ticker", 
            color="Type", 
            orientation='h', 
            barmode='stack',
            color_discrete_map={"Call": "#3182ce", "Put": "#e53e3e"} # Blue for Calls, Red for Puts
        )
        
        # Clean up the layout and sort so the biggest bars are at the top
        fig.update_layout(
            yaxis={'categoryorder':'total ascending'},
            xaxis_title="Premium Value ($)",
            yaxis_title="",
            margin=dict(l=0, r=0, t=20, b=0)
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(f"No whale trades found in the {bucket_name} timeframe.")

with tab1:
    draw_bucket_chart("0-7 Days (Immediate)")
with tab2:
    draw_bucket_chart("8-45 Days (Tactical)")
with tab3:
    draw_bucket_chart("45+ Days (Strategic)")

# 4. Data Table
st.divider()
st.subheader("Filtered Whale Sweeps")
display_cols = [c for c in ["Ticker", "Type", "Strike", "Expiration", "DTE Bucket", "Premium", "Volume", "Open Interest", "Time"] if c in filtered_df.columns]
st.dataframe(filtered_df[display_cols].iloc[::-1], use_container_width=True, hide_index=True)
