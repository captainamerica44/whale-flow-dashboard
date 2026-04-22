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
        
        # Calculate Days to Expiration (DTE) - FIXED WITH .normalize()
        df['Expiration'] = pd.to_datetime(df['Expiration'], errors='coerce')
        today = pd.to_datetime('today').normalize()
        df['DTE'] = (df['Expiration'] - today).dt.days
        
        # EXACT BUCKETING AS REQUESTED
        def categorize_term(dte):
            if pd.isna(dte): return "Unknown"
            if dte <= 7: return "0-7 Days (Immediate)"
            if dte <= 45: return "8-45 Days (Tactical)"
            return "45+ Days (Strategic)"
            
        df['DTE Bucket'] = df['DTE'].apply(categorize_term)
        
        # Format Expiration back to a clean string for the data table
        df['Expiration'] = df['Expiration'].dt.strftime('%m/%d/%Y')
        
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.warning("Waiting for data. Ensure flow_tracker.py is running and updating Google Sheets!")
    st.stop()

st.sidebar.header("Controls")

# 1. Initialize filtered_df
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

st.sidebar.divider()
st.sidebar.markdown("Enjoying the data? [☕ Buy me a coffee!](https://buymeacoffee.com/deepchartlabs)")

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
        
        # Clean up the layout
