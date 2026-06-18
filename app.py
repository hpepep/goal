import streamlit as st
import json
import os
import yfinance as yf
from mftool import Mftool
import pandas as pd
from datetime import datetime, date
import re

# Initialize APIs
mf_api = Mftool()
DB_FILE = "portfolio_db.json"

# --- PERSISTENCE LAYER ---
def load_data():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_data(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

if "portfolio_data" not in st.session_state:
    st.session_state.portfolio_data = load_data()

def trigger_save():
    save_data(st.session_state.portfolio_data)

# --- FINANCIAL ENGINE ---
@st.cache_data(ttl=60)
def fetch_stock_details(ticker):
    """Fetches real-time stock price and dynamic name metadata from yfinance with zero hardcoded prices."""
    
    # Cross-reference map to convert fragile BSE numeric codes to resilient NSE tickers
    EQUITY_IDENTIFIER_MAP = {
        "500325.BO": {"nse": "RELIANCE.NS", "default_name": "Reliance Industries Ltd"},
        "RELIANCE.BO": {"nse": "RELIANCE.NS", "default_name": "Reliance Industries Ltd"},
        "500209.BO": {"nse": "INFY.NS", "default_name": "Infosys Ltd"},
        "INFY.BO": {"nse": "INFY.NS", "default_name": "Infosys Ltd"},
        "532540.BO": {"nse": "TCS.NS", "default_name": "Tata Consultancy Services (TCS)"},
        "TCS.BO": {"nse": "TCS.NS", "default_name": "Tata Consultancy Services (TCS)"},
        "500180.BO": {"nse": "HDFCBANK.NS", "default_name": "HDFC Bank Ltd"},
        "HDFCBANK.BO": {"nse": "HDFCBANK.NS", "default_name": "HDFC Bank Ltd"},
        "532174.BO": {"nse": "ICICIBANK.NS", "default_name": "ICICI Bank Ltd"},
        "ICICIBANK.BO": {"nse": "ICICIBANK.NS", "default_name": "ICICI Bank Ltd"},
        "500696.BO": {"nse": "HINDUNILVR.NS", "default_name": "Hindustan Unilever Ltd (HUL)"},
        "HINDUNILVR.BO": {"nse": "HINDUNILVR.NS", "default_name": "Hindustan Unilever Ltd (HUL)"},
        "500112.BO": {"nse": "SBIN.NS", "default_name": "State Bank of India (SBI)"},
        "SBIN.BO": {"nse": "SBIN.NS", "default_name": "State Bank of India (SBI)"},
        "532215.BO": {"nse": "AXISBANK.NS", "default_name": "Axis Bank Ltd"},
        "AXISBANK.BO": {"nse": "AXISBANK.NS", "default_name": "Axis Bank Ltd"},
        "500510.BO": {"nse": "LT.NS", "default_name": "Larsen & Toubro Ltd (L&T)"},
        "LT.BO": {"nse": "LT.NS", "default_name": "Larsen & Toubro Ltd (L&T)"},
        "532454.BO": {"nse": "BHARTIALRTT.NS", "default_name": "Bharti Airtel Ltd"},
        "BHARTIALRTT.BO": {"nse": "BHARTIALRTT.NS", "default_name": "Bharti Airtel Ltd"},
        "500820.BO": {"nse": "ASIANPAINT.NS", "default_name": "Asian Paints Ltd"},
        "ASIANPAINT.BO": {"nse": "ASIANPAINT.NS", "default_name": "Asian Paints Ltd"},
        "500875.BO": {"nse": "ITC.NS", "default_name": "ITC Ltd"},
        "ITC.BO": {"nse": "ITC.NS", "default_name": "ITC Ltd"}
    }

    # Format incoming query
    formatted_ticker = ticker.strip().upper()
    if not (formatted_ticker.endswith(".BO") or formatted_ticker.endswith(".NS")):
        formatted_ticker += ".BO"
    
    # Step 1: Assign default display name if known
    map_entry = EQUITY_IDENTIFIER_MAP.get(formatted_ticker, None)
    name = map_entry["default_name"] if map_entry else None
    
    # Internal helper function to hit the live API target directly
    def get_live_quote(symbol):
        try:
            stock = yf.Ticker(symbol)
            # Try 1-day historical period tracking row
            hist = stock.history(period="1d")
            if hist.empty:
                hist = stock.history(period="5d")
                
            if not hist.empty:
                return round(float(hist['Close'].iloc[-1]), 2), stock
            
            # Fast raw metadata extraction if tables are blocked
            try:
                return round(float(stock.fast_info['lastPrice']), 2), stock
            except:
                try:
                    return round(float(stock.info.get('regularMarketPrice', 0.0)), 2), stock
                except:
                    return 0.0, stock
        except:
            return 0.0, None

    # Step 2: Query Yahoo Finance using the primary entered ticker identifier
    price, stock_obj = get_live_quote(formatted_ticker)
    
    # Step 3: Dual-Routing Bridge. If primary query yields a zero price, use the alternate exchange identifier
    if price == 0.0 and map_entry:
        alternate_ticker = map_entry["nse"]
        price, stock_obj = get_live_quote(alternate_ticker)
        
    # Step 4: Dynamic name parsing if it's an unmapped custom stock entry
    if not name and stock_obj:
        try:
            name = stock_obj.fast_info['name']
        except:
            pass
        if not name or name == formatted_ticker:
            try:
                name = stock_obj.info.get('longName', stock_obj.info.get('shortName', None))
            except:
                pass
                
    if not name:
        clean_code = formatted_ticker.replace(".BO", "").replace(".NS", "")
        name = f"Equity Instrument: {clean_code}"

    return price, name

@st.cache_data(ttl=3600)
def fetch_mf_details(scheme_code):
    """Fetches live NAV and scheme name from AMFI code."""
    try:
        quote = mf_api.get_scheme_quote(scheme_code.strip())
        if quote and 'nav' in quote:
            return float(quote['nav']), quote.get('scheme_name', f"MF {scheme_code}")
        return 0.0, f"MF {scheme_code}"
    except Exception:
        return 0.0, scheme_code

def calculate_days_between(start_date_str):
    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        return (date.today() - start_date).days
    except:
        return 0

def calculate_future_value(current_val, annual_rate, target_date_str):
    try:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").date()
        years = (target_date - date.today()).days / 365.25
        if years <= 0:
            return current_val
        return current_val * ((1 + (annual_rate / 100)) ** years)
    except:
        return current_val

def format_indian_currency(val):
    """Formats numeric floats into the traditional Indian system (Lakhs, Crores) format securely."""
    try:
        s = f"{round(val, 2):.2f}"
        parts = s.split('.')
        num = parts[0]
        decimal = parts[1]
        
        # Regex execution grouping hundreds differently from remaining pairs
        if len(num) > 3:
            last_three = num[-3:]
            remaining = num[:-3]
            remaining_grouped = re.sub(r'(?<=.)(?=(..)+$)', ',', remaining)
            return f"₹ {remaining_grouped},{last_three}.{decimal}"
        else:
            return f"₹ {num}.{decimal}"
    except:
        return f"₹ {round(val, 2):,}"

# --- CUSTOM THEME STYLING ---
st.set_page_config(page_title="Goal Portfolio Dashboard", layout="wide")

st.markdown("""
    <style>
    .stApp {
        background-color: #0E1117;
    }
    
    .metric-card {
        background-color: #1A1F2C;
        border: 1px solid #2D3748;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.2);
        margin-bottom: 15px;
    }
    .metric-title {
        color: #A0AEC0;
        font-size: 13px;
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
    }
    .metric-value {
        color: #4FD1C5;
        font-size: 24px;
        font-weight: 700;
    }
    .metric-value-total {
        color: #38A169;
        font-size: 28px;
        font-weight: 800;
    }
    
    div[data-testid="stForm"] {
        border: 1px solid #2D3748 !important;
        background-color: #161B22;
        border-radius: 8px;
    }
    
    button[data-baseweb="tab"] p {
        font-size: 16px !important;
        font-weight: 600 !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- APP UI ---
st.title("📊 Financial Goal Simulation Dashboard")
st.caption("A premium tracking matrix mapping current investments to target lifecycle milestones.")
st.markdown("---")

# --- SIDEBAR GOAL CONTROLLER ---
with st.sidebar:
    st.markdown("### 🎯 Add New Milestone")
    new_goal_name = st.text_input("Milestone Goal Name", placeholder="e.g., Early Retirement")
    new_goal_date = st.date_input("Target Date for Goal", min_value=date.today(), max_value=date(2076, 12, 31))
    
    if st.button("➕ Instantiate Goal", use_container_width=True):
        if new_goal_name and new_goal_name not in st.session_state.portfolio_data:
            st.session_state.portfolio_data[new_goal_name] = {
                "target_date": str(new_goal_date),
                "expected_returns": {"mf": 12.0, "eq": 12.0, "debt": 7.0},
                "mutual_funds": {},
                "equities": {},
                "debt": {}
            }
            trigger_save()
            st.success(f"Goal created!")
            st.rerun()
            
    st.markdown("---")
    st.markdown("### ⚙️ Systems Check")
    if st.session_state.portfolio_data:
        goal_to_delete = st.selectbox("Select Goal to Tear Down", list(st.session_state.portfolio_data.keys()))
        if st.button("🗑️ Delete Selected Goal", use_container_width=True, type="primary"):
            del st.session_state.portfolio_data[goal_to_delete]
            trigger_save()
            st.rerun()

# --- MAIN DASHBOARD IMPLEMENTATION ---
goals = list(st.session_state.portfolio_data.keys())

if not goals:
    st.info("💡 No active goals configured. Please use the sidebar controller to instantiate your tracking profile.")
else:
    tabs = st.tabs([f"🎯 {g}" for g in goals])
    
    for idx, goal_name in enumerate(goals):
        with tabs[idx]:
            goal_dict = st.session_state.portfolio_data[goal_name]
            target_date_str = goal_dict["target_date"]
            
            # --- TOP SECTION: RE-CALCULATE BALANCES ---
            total_mf_current = sum(fetch_mf_details(c)[0] * d["units"] for c, d in goal_dict["mutual_funds"].items())
            total_eq_current = sum(fetch_stock_details(t)[0] * d["qty"] for t, d in goal_dict["equities"].items())
            
            total_debt_current = 0.0
            for d_lbl, d_det in goal_dict["debt"].items():
                days_el = calculate_days_between(d_det["start_date"])
                total_debt_current += d_det["principal"] * ((1 + (d_det["roi"] / 100)) ** (days_el / 365.25))

            current_assets_sum = total_mf_current + total_eq_current + total_debt_current
            
            f_mf = calculate_future_value(total_mf_current, goal_dict["expected_returns"]["mf"], target_date_str)
            f_eq = calculate_future_value(total_eq_current, goal_dict["expected_returns"]["eq"], target_date_str)
            f_db = calculate_future_value(total_debt_current, goal_dict["expected_returns"]["debt"], target_date_str)
            cumulated_future_corpus = f_mf + f_eq + f_db
            
            # Draw premium summary card row
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(f'<div class="metric-card"><div class="metric-title">Asset Portfolio Today</div><div class="metric-value">{format_indian_currency(current_assets_sum)}</div></div>', unsafe_allow_html=True)
            with c2:
                time_rem = round((datetime.strptime(target_date_str, '%Y-%m-%d').date() - date.today()).days / 365.25, 1)
                st.markdown(f'<div class="metric-card"><div class="metric-title">Milestone Countdown</div><div class="metric-value">{time_rem} Years</div></div>', unsafe_allow_html=True)
            with c3:
                st.markdown(f'<div class="metric-card"><div class="metric-title">Target Deadline</div><div class="metric-value">{target_date_str}</div></div>', unsafe_allow_html=True)
            with c4:
                st.markdown(f'<div class="metric-card" style="border-color: #38A169;"><div class="metric-title" style="color: #68D391;">Projected End Corpus</div><div class="metric-value-total">{format_indian_currency(cumulated_future_corpus)}</div></div>', unsafe_allow_html=True)

            # --- TARGET RETURN OPTIMIZATIONS ---
            with st.expander("🛠️ Modify Asset Return Models (% Compound Assumptions)", expanded=True):
                r_col1, r_col2, r_col3 = st.columns(3)
                with r_col1:
                    goal_dict["expected_returns"]["mf"] = st.number_input(f"Mutual Funds ROI (%)", min_value=0.0, max_value=40.0, value=float(goal_dict["expected_returns"].get("mf", 12.0)), key=f"ui_mf_{goal_name}", on_change=trigger_save)
                with r_col2:
                    goal_dict["expected_returns"]["eq"] = st.number_input(f"Equities ROI (%)", min_value=0.0, max_value=40.0, value=float(goal_dict["expected_returns"].get("eq", 12.0)), key=f"ui_eq_{goal_name}", on_change=trigger_save)
                with r_col3:
                    goal_dict["expected_returns"]["debt"] = st.number_input(f"Debt/FD ROI (%)", min_value=0.0, max_value=40.0, value=float(goal_dict["expected_returns"].get("debt", 7.0)), key=f"ui_db_{goal_name}", on_change=trigger_save)

            st.markdown("###")

            # --- SUB SECTION 1: MUTUAL FUNDS ---
            st.subheader("🧬 1. Mutual Fund Asset Allocations")
            sub_col_mf1, sub_col_mf2 = st.columns([1, 2])
            with sub_col_mf1:
                with st.form(key=f"form_mf_{goal_name}"):
                    st.markdown("**Manage Core Assets**")
                    f_mf_code = st.text_input("AMFI Code", placeholder="e.g. 119597")
                    f_mf_units = st.number_input("Units Held", min_value=0.0, step=0.001)
                    mode_mf = st.selectbox("Action", ["Add/Update Asset", "Delete Asset"])
                    if st.form_submit_button("Execute", use_container_width=True):
                        if mode_mf == "Add/Update Asset" and f_mf_code and f_mf_units > 0:
                            goal_dict["mutual_funds"][f_mf_code] = {"units": f_mf_units}
                            trigger_save()
                            st.rerun()
                        elif mode_mf == "Delete Asset" and f_mf_code in goal_dict["mutual_funds"]:
                            del goal_dict["mutual_funds"][f_mf_code]
                            trigger_save()
                            st.rerun()
            with sub_col_mf2:
                mf_records = []
                for code, details in goal_dict["mutual_funds"].items():
                    nav, scheme_name = fetch_mf_details(code)
                    curr_val = nav * details["units"]
                    mf_records.append({
                        "AMFI Code": code, 
                        "Fund Description": scheme_name, 
                        "Units Owned": details["units"], 
                        "Live NAV": format_indian_currency(nav), 
                        "Current Value": format_indian_currency(curr_val)
                    })
                if mf_records:
                    st.dataframe(pd.DataFrame(mf_records), use_container_width=True, hide_index=True)
                else:
                    st.caption("No allocations initialized.")

            # --- SUB SECTION 2: EQUITIES ---
            st.subheader("📈 2. Equity Instruments (BSE Native Engine)")
            sub_col_eq1, sub_col_eq2 = st.columns([1, 2])
            with sub_col_eq1:
                with st.form(key=f"form_eq_{goal_name}"):
                    st.markdown("**Manage Equity Positions**")
                    f_eq_tick = st.text_input("BSE Code / Ticker", placeholder="e.g. 500325")
                    f_eq_qty = st.number_input("Shares Volume", min_value=0.0, step=1.0)
                    f_eq_prc = st.number_input("Avg Price (₹)", min_value=0.0, step=0.1)
                    mode_eq = st.selectbox("Action", ["Add/Update Asset", "Delete Asset"])
                    if st.form_submit_button("Execute", use_container_width=True):
                        t_key = f_eq_tick.strip().upper()
                        if not (t_key.endswith(".BO") or t_key.endswith(".NS")):
                            t_key += ".BO"
                        if mode_eq == "Add/Update Asset" and f_eq_tick and f_eq_qty > 0:
                            goal_dict["equities"][t_key] = {"qty": f_eq_qty, "buy_price": f_eq_prc}
                            trigger_save()
                            st.rerun()
                        elif mode_eq == "Delete Asset" and t_key in goal_dict["equities"]:
                            del goal_dict["equities"][t_key]
                            trigger_save()
                            st.rerun()
            with sub_col_eq2:
                eq_records = []
                for ticker, details in goal_dict["equities"].items():
                    live_price, comp_name = fetch_stock_details(ticker)
                    curr_val = live_price * details["qty"]
                    eq_records.append({
                        "Ticker": ticker, 
                        "Company Name": comp_name, 
                        "Shares": details["qty"], 
                        "Avg Cost": format_indian_currency(details["buy_price"]), 
                        "Live Spot": format_indian_currency(live_price), 
                        "Total Value": format_indian_currency(curr_val)
                    })
                if eq_records:
                    st.dataframe(pd.DataFrame(eq_records), use_container_width=True, hide_index=True)
                else:
                    st.caption("No allocations initialized.")

            # --- SUB SECTION 3: FIXED INCOME ---
            st.subheader("🏦 3. Fixed Income, FDs & Liquid Capital")
            sub_col_db1, sub_col_db2 = st.columns([1, 2])
            with sub_col_db1:
                with st.form(key=f"form_db_{goal_name}"):
                    st.markdown("**Manage Debt Instruments**")
                    f_db_lbl = st.text_input("Instrument Name", placeholder="e.g. SBI Fixed Deposit")
                    f_db_inv = st.number_input("Principal Invested (₹)", min_value=0.0, step=500.0)
                    f_db_dat = st.date_input("Issuance Date", max_value=date.today())
                    f_db_roi = st.number_input("Contracted Yield (% p.a.)", min_value=0.0, max_value=25.0, step=0.1)
                    mode_db = st.selectbox("Action", ["Add/Update Asset", "Delete Asset"])
                    if st.form_submit_button("Execute", use_container_width=True):
                        if mode_db == "Add/Update Asset" and f_db_lbl and f_db_inv > 0:
                            goal_dict["debt"][f_db_lbl] = {"principal": f_db_inv, "start_date": str(f_db_dat), "roi": f_db_roi}
                            trigger_save()
                            st.rerun()
                        elif mode_db == "Delete Asset" and f_db_lbl in goal_dict["debt"]:
                            del goal_dict["debt"][f_db_lbl]
                            trigger_save()
                            st.rerun()
            with sub_col_db2:
                debt_records = []
                for label, details in goal_dict["debt"].items():
                    days = calculate_days_between(details["start_date"])
                    val_today = details["principal"] * ((1 + (details["roi"] / 100)) ** (days / 365.25))
                    debt_records.append({
                        "Asset Description": label, 
                        "Principal": format_indian_currency(details["principal"]), 
                        "Yield (%)": details["roi"], 
                        "Days Held": days, 
                        "Value Today": format_indian_currency(val_today)
                    })
                if debt_records:
                    st.dataframe(pd.DataFrame(debt_records), use_container_width=True, hide_index=True)
                else:
                    st.caption("No allocations initialized.")

            # --- CUMULATIVE FORECAST BREAKDOWN SECTION ---
            st.markdown("###")
            st.markdown("### 📊 Compound Projection Profile")
            
            proj_data = {
                "Asset Structure": ["Mutual Funds Group", "Equities Portfolio", "Fixed Income / Cash Assets", "AGGREGATED PORTFOLIO"],
                "Current Baseline Value": [format_indian_currency(total_mf_current), format_indian_currency(total_eq_current), format_indian_currency(total_debt_current), format_indian_currency(current_assets_sum)],
                "Modeled Return Factor": [f"{goal_dict['expected_returns']['mf']}%", f"{goal_dict['expected_returns']['eq']}%", f"{goal_dict['expected_returns']['debt']}%", "—"],
                "Terminal Forecast Value": [format_indian_currency(f_mf), format_indian_currency(f_eq), format_indian_currency(f_db), format_indian_currency(cumulated_future_corpus)]
            }
            st.table(pd.DataFrame(proj_data))
