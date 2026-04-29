import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import json
from datetime import datetime, timedelta
import os

# --- 1. PAGE SETUP (Must be the very first Streamlit command) ---
st.set_page_config(page_title="Master Whale Terminal", layout="wide", page_icon="🐋")
st.title("🐋 Master Institutional Trading Terminal")

# --- 2. CREATE THE MASTER TABS ---
main_tab_options, main_tab_gov = st.tabs(["🌊 Options Whale Flow", "🏛️ Gov Contract Catalysts"])

# ==========================================
# --- MASTER TAB 1: OPTIONS FLOW VIEWER ---
# ==========================================
with main_tab_options:
    @st.cache_data(ttl=60)
    def load_data():
        try:
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
            
            df['Expiration Date'] = pd.to_datetime(df['Expiration'], errors='coerce')
            today = pd.to_datetime('today')
            df['DTE'] = (df['Expiration Date'] - today).dt.days
            
            def categorize_term(dte):
                if pd.isna(dte): return "Unknown"
                if dte <= 7: return "0-7 Days (Immediate)"
                if dte <= 45: return "8-45 Days (Tactical)"
                return "45+ Days (Strategic)"
                
            df['DTE Bucket'] = df['DTE'].apply(categorize_term)
            return df
        except Exception:
            return pd.DataFrame()
st.sidebar.markdown(
            """
            <div style="text-align: center; margin-bottom: 20px;">
                <a href="https://buymeacoffee.com/deepchartlabs" target="_blank">
                    <img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" width="150" >
                </a>
            </div>
            """,
            unsafe_allow_html=True
        )
    df = load_data()

    if df.empty:
        st.warning("Waiting for data. Ensure flow_tracker.py is running and updating Google Sheets!")
    else:
        st.sidebar.header("Options Controls")
        
        filtered_df = df.copy()
        
        tickers = ["All"] + sorted(filtered_df['Ticker'].dropna().unique().tolist())
        selected_ticker = st.sidebar.selectbox("Filter by Ticker", tickers)
        
        if selected_ticker != "All":
            filtered_df = filtered_df[filtered_df['Ticker'] == selected_ticker]
        
        st.subheader("Total Premium by Ticker (Calls vs Puts)")
        
        # Sub-tabs for the options flow
        sub_tab1, sub_tab2, sub_tab3 = st.tabs(["0-7 Days (Immediate)", "8-45 Days (Tactical)", "45+ Days (Strategic)"])
        
        def draw_bucket_chart(bucket_name):
            bucket_data = filtered_df[filtered_df['DTE Bucket'] == bucket_name]
            if not bucket_data.empty:
                chart_data = bucket_data.groupby(["Ticker", "Type"])["Premium Value"].sum().reset_index()
                
                fig = px.bar(
                    chart_data, 
                    x="Premium Value", 
                    y="Ticker", 
                    color="Type", 
                    orientation='h', 
                    barmode='stack',
                    color_discrete_map={"Call": "#3182ce", "Put": "#e53e3e"} 
                )
                
                fig.update_layout(
                    yaxis={'categoryorder':'total ascending'},
                    xaxis_title="Premium Value ($)",
                    yaxis_title="",
                    margin=dict(l=0, r=0, t=20, b=0)
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(f"No whale trades found in the {bucket_name} timeframe.")
        
        with sub_tab1: draw_bucket_chart("0-7 Days (Immediate)")
        with sub_tab2: draw_bucket_chart("8-45 Days (Tactical)")
        with sub_tab3: draw_bucket_chart("45+ Days (Strategic)")
        
        st.divider()
        st.subheader("Filtered Whale Sweeps")
        display_cols = [c for c in ["Ticker", "Type", "Strike", "Expiration", "DTE Bucket", "Premium", "Volume", "Open Interest", "Time"] if c in filtered_df.columns]
        st.dataframe(filtered_df[display_cols].iloc[::-1], use_container_width=True, hide_index=True)


# ==========================================
# --- MASTER TAB 2: GOV FLOW ENGINE ---
# ==========================================
with main_tab_gov:
    st.header("Government Broad Market Discovery")
    
    # Gov Flow Configuration
    API_URL = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
    LOOKBACK_DAYS = 20
    MIN_AWARD = 50000000
    start_date = (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime('%Y-%m-%d')
    end_date = datetime.now().strftime('%Y-%m-%d')

    # Bulletproof local file loader
    @st.cache_data 
    def load_brain_file():
        try:
            # Force Python to look in the exact directory this script is sitting in
            current_folder = os.path.dirname(__file__)
            file_path = os.path.join(current_folder, "master_list.csv")
            return pd.read_csv(file_path)
        except FileNotFoundError:
            return None # Return None so the UI handles the error visibly

    def fetch_government_data():
        payload = {
            "filters": {
                "time_period": [{"start_date": start_date, "end_date": end_date, "date_type": "date_signed"}],
                "award_amounts": [{"lower_bound": MIN_AWARD}],
                "award_type_codes": ["A", "B", "C", "D"]
            },
            "fields": ["Award ID", "Recipient Name", "Award Amount", "Funding Agency", "Start Date"],
            "limit": 100
        }
        headers = {'Content-Type': 'application/json'}
        try:
            response = requests.post(API_URL, data=json.dumps(payload), headers=headers)
            response.raise_for_status()
            return response.json().get('results', [])
        except Exception as e:
            st.error(f"API Error: {e}")
            return []

    # Gov Flow UI Logic
    master_df = load_brain_file()

    # --- THE ERROR CATCHER ---
    if master_df is None:
        st.error("🚨 Could not find 'master_list.csv'.")
        st.info("Check your folder. Make sure the file isn't accidentally named 'master_list.csv.csv' or 'master_list.csv.txt'.")
    else:
        st.write(f"🧠 Brain loaded: Tracking {len(master_df)} tickers | ⏱️ {LOOKBACK_DAYS}-Day Lookback")
        
        if st.button("🚀 Run Broad Market Discovery Scan", type="primary"):
            with st.spinner("Pinging federal database and cross-referencing Master List..."):
                raw_awards = fetch_government_data()
                actionable_hits = []
                
                for award in raw_awards:
                    recipient = award.get('Recipient Name', '').upper()
                    amount = award.get('Award Amount', 0)
                    date = award.get('Start Date', 'Unknown')
                    agency = award.get('Funding Agency', 'Unknown')
                    
                    for index, row in master_df.iterrows():
                        keyword = str(row['Name']).upper()
                        ticker = str(row['Ticker']).upper()
                        
                        if keyword in recipient:
                            actionable_hits.append({
                                "Ticker": ticker,
                                "Date Signed": date,
                                "Amount": f"${amount:,.2f}",
                                "Government Entity": recipient,
                                "Funding Agency": agency
                            })
                            break 
                
                if actionable_hits:
                    st.success(f"Target Acquired: Found {len(actionable_hits)} massive catalysts.")
                    st.dataframe(pd.DataFrame(actionable_hits), use_container_width=True, hide_index=True)
                else:
                    st.info(f"Scan complete. No recent awards matched your Master List in the last {LOOKBACK_DAYS} days.")
