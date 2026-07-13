import streamlit as st
from mftool import Mftool
import pandas as pd

# Initialize mftool
mf = Mftool()

st.set_page_config(page_title="Mutual Fund Tracker", layout="wide")
st.title("📈 Indian Mutual Fund Portfolio Tracker")

# 1. Initialize session state for portfolio if it doesn't exist
if "portfolio" not in st.session_state:
    st.session_state.portfolio = []

# --- SIDEBAR: ADD NEW MUTUAL FUND ---
with st.sidebar:
    # Wrapping inputs inside an st.form stops Streamlit from rerunning on every keystroke/enter key press
    with st.form(key="add_fund_form", clear_on_submit=True):
        st.subheader("➕ Add New Investment")
        
        amfi_code = st.text_input("Enter AMFI Code:", placeholder="e.g., 119062")
        units = st.number_input("Units Purchased:", min_value=0.000, step=0.001, format="%.3f")
        avg_nav = st.number_input("Average Purchase NAV (Optional):", min_value=0.0, step=0.01)
        
        submit_button = st.form_submit_button(label="Fetch & Add to Portfolio")

    # Processing data ONLY after the form button is clicked
    if submit_button:
        clean_code = amfi_code.strip()
        if not clean_code:
            st.error("Please provide an AMFI code.")
        elif units <= 0:
            st.error("Units must be greater than zero.")
        else:
            with st.spinner("Fetching data from AMFI..."):
                try:
                    # Fetch live details using mftool
                    data = mf.get_scheme_quote(clean_code)
                    
                    if data and 'scheme_name' in data:
                        current_nav = float(data['nav'])
                        scheme_name = data['scheme_name']
                        
                        # Calculate investment metrics
                        invested_value = units * (avg_nav if avg_nav > 0 else current_nav)
                        current_value = units * current_nav
                        pnl = current_value - invested_value
                        
                        # Save tracking details into session state
                        new_fund = {
                            "AMFI Code": clean_code,
                            "Scheme Name": scheme_name,
                            "Units": units,
                            "Avg Purchase NAV": avg_nav if avg_nav > 0 else current_nav,
                            "Current NAV": current_nav,
                            "Invested Value": invested_value,
                            "Current Value": current_value,
                            "Profit/Loss": pnl
                        }
                        
                        st.session_state.portfolio.append(new_fund)
                        st.success(f"Successfully added:\n{scheme_name}")
                    else:
                        st.error("Invalid AMFI code or fund details not found.")
                except Exception as e:
                    st.error(f"Error connecting to AMFI database: {e}")

# --- MAIN DASHBOARD DISPLAY ---
if st.session_state.portfolio:
    # Convert portfolio list into a DataFrame for easy calculations and presentation
    df = pd.DataFrame(st.session_state.portfolio)
    
    # Summary Metrics Block
    st.subheader("Portfolio Summary")
    col1, col2, col3 = st.columns(3)
    
    total_invested = df["Invested Value"].sum()
    total_current = df["Current Value"].sum()
    total_pnl = total_current - total_invested
    pnl_percentage = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0

    col1.metric("Total Invested Value", f"₹{total_invested:,.2f}")
    col2.metric("Total Current Value", f"₹{total_current:,.2f}")
    col3.metric("Total Absolute Returns", f"₹{total_pnl:,.2f}", f"{pnl_percentage:+.2f}%")
    
    st.markdown("---")
    
    # Portfolio Table View
    st.subheader("Your Holdings")
    
    # Format the columns nicely before displaying
    df_styled = df.copy()
    df_styled["Units"] = df_styled["Units"].map("{:,.3f}".format)
    df_styled["Avg Purchase NAV"] = df_styled["Avg Purchase NAV"].map("₹{:,.2f}".format)
    df_styled["Current NAV"] = df_styled["Current NAV"].map("₹{:,.2f}".format)
    df_styled["Invested Value"] = df_styled["Invested Value"].map("₹{:,.2f}".format)
    df_styled["Current Value"] = df_styled["Current Value"].map("₹{:,.2f}".format)
    df_styled["Profit/Loss"] = df_styled["Profit/Loss"].map("₹{:,.2f}".format)
    
    st.dataframe(df_styled, use_container_width=True)
    
    # Option to clear portfolio data
    if st.button("Clear Portfolio Data"):
        st.session_state.portfolio = []
        st.rerun()

else:
    # Empty dashboard state
    st.info("💡 Your portfolio tracker is empty. Use the sidebar menu to add mutual funds using their AMFI code.")
    st.markdown("""
    **Quick Guide on How to Use:**
    1. Look up your mutual fund's AMFI code (e.g., `119062` is *ICICI Prudential Bluechip Fund - Direct Plan - Growth*).
    2. Enter it into the sidebar input field.
    3. Input your total held units and your average buying price.
    4. Click the submit button to live-track your investments.
    """)
