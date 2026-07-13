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

    formatted_ticker = ticker.strip().upper()
    if not (formatted_ticker.endswith(".BO") or formatted_ticker.endswith(".NS")):
        formatted_ticker += ".BO"
    
    map_entry = EQUITY_IDENTIFIER_MAP.get(formatted_ticker, None)
    name = map_entry["default_name"] if map_entry else None
    
    def get_live_quote(symbol):
        try:
            stock = yf.Ticker(symbol)
            hist = stock.history(period="1d")
            if hist.empty:
                hist = stock.history(period="5d")
            if not hist.empty:
                return round(float(hist['Close'].iloc[-1]), 2), stock
            try:
                return round(float(stock.fast_info['lastPrice']), 2), stock
            except:
                return 0.0, stock
        except:
            return 0.0, None

    price, stock_obj = get_live_quote(formatted_ticker)
    
    if price == 0.0 and map_entry:
        price, stock_obj = get_live_quote(map_entry["nse"])
        
    if not name and stock_obj:
        try:
            name = stock_obj.fast_info['name']
        except:
            pass
    if not name:
        name = f"Equity Instrument: {formatted_ticker.replace('.BO','').replace('.NS','')}"

    return price, name

@st.cache_data(ttl=3600)
def fetch_mf_details(scheme_code):
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
    try:
        s = f"{round(val, 2):.2f}"
        parts = s.split('.')
        num = parts[0]
        decimal = parts[1]
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
    .stApp { background-color: #0E1117; }
    .metric-card {
        background-color: #1A1F2C; border: 1px solid #2D3748; padding: 20px;
        border-radius: 10px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.2); margin-bottom: 15px;
    }
    .metric-title { color: #A0AEC0; font-size: 13px; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px; margin-bottom: 8px; }
    .metric-value { color: #4FD1C5; font-size: 24px; font-weight: 700; }
    .metric-value-total { color: #38A169; font-size: 28px; font-weight: 800; }
    div[data-testid="stForm"] { border: 1px solid #2D3748 !important; background-color: #161B22; border-radius: 8px; }
    button[data-baseweb="tab"] p { font-size: 16px !important; font-weight: 600 !important; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 Financial Goal Simulation Dashboard")
st.caption("A premium tracking matrix mapping current investments to target lifecycle milestones.")
st.markdown("---")

# --- SIDEBAR CONTROLLER ---
with st.sidebar:
    st.markdown("### 💾 Data Backup & Restore")
    
    json_string = json.dumps(st.session_state.portfolio_data, indent=4)
    st.download_button(
        label="📥 Export Portfolio Data (JSON)",
        data=json_string,
        file_name="portfolio_db.json",
        mime="application/json",
        use_container_width=True
    )
    
    uploaded_file = st.file_uploader("📤 Import Portfolio Data (JSON)", type=["json"], label_visibility="collapsed")
    if uploaded_file is not None:
        try:
            uploaded_data = json.load(uploaded_file)
            st.session_state.portfolio_data = uploaded_data
            save_data(uploaded_data)
            st.success("Configuration loaded successfully!")
            st.rerun()
        except Exception as e:
            st.error(f"Malformed structure verified: {e}")
            
    st.markdown("---")

    st.markdown("### 🎯 Add New Milestone")
    new_goal_name = st.text_input("Milestone Goal Name", placeholder="e.g., Early Retirement")
    new_goal_date = st.date_input("Target Date for Goal", min_value=date.today(), max_value=date(2076, 12, 31))
    
    if st.button("➕ Instantiate Goal", use_container_width=True):
        if new_goal_name and new_goal_name not in st.session_state.portfolio_data:
            st.session_state.portfolio_data[new_goal_name] = {
                "target_date": str(new_goal_date),
                "accumulation_returns": {"mf": 12.0, "eq": 12.0, "debt": 7.0, "epf": 8.1, "other1": 7.0, "other2": 7.0},
                "withdrawal_returns": {"mf": 8.0, "eq": 8.0, "debt": 6.0, "epf": 7.0, "other1": 6.0, "other2": 6.0},
                "mutual_funds": {}, "equities": {}, "debt": {}, 
                "epf": {}, "other1": {}, "other2": {},
                "retirement_config": {"duration_years": 25, "initial_outflow": 1200000.0, "inflation_rate": 6.0}
            }
            trigger_save()
            st.success("Goal created!")
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
            
            # Backwards Compatibility Upgrades / Defensive Fallbacks
            if "retirement_config" not in goal_dict:
                goal_dict["retirement_config"] = {"duration_years": 25, "initial_outflow": 1200000.0, "inflation_rate": 6.0}
            goal_dict.setdefault("epf", {})
            goal_dict.setdefault("other1", {})
            goal_dict.setdefault("other2", {})
            
            # Legacy expected_returns migration path
            if "accumulation_returns" not in goal_dict:
                if "expected_returns" in goal_dict:
                    goal_dict["accumulation_returns"] = goal_dict["expected_returns"]
                else:
                    goal_dict["accumulation_returns"] = {"mf": 12.0, "eq": 12.0, "debt": 7.0, "epf": 8.1, "other1": 7.0, "other2": 7.0}
            if "withdrawal_returns" not in goal_dict:
                if "retirement_config" in goal_dict and "post_ret_roi" in goal_dict["retirement_config"]:
                    p_roi = goal_dict["retirement_config"]["post_ret_roi"]
                    goal_dict["withdrawal_returns"] = {"mf": p_roi, "eq": p_roi, "debt": p_roi, "epf": p_roi, "other1": p_roi, "other2": p_roi}
                else:
                    goal_dict["withdrawal_returns"] = {"mf": 8.0, "eq": 8.0, "debt": 6.0, "epf": 7.0, "other1": 6.0, "other2": 6.0}
            
            acc_ret = goal_dict["accumulation_returns"]
            wth_ret = goal_dict["withdrawal_returns"]
            
            # --- TOP SECTION: RE-CALCULATE BALANCES ---
            total_mf_current = sum(fetch_mf_details(c)[0] * d["units"] for c, d in goal_dict["mutual_funds"].items())
            total_eq_current = sum(fetch_stock_details(t)[0] * d["qty"] for t, d in goal_dict["equities"].items())
            
            # Current values calculated dynamically up to today using the targeted phase accumulation rate
            total_debt_current = 0.0
            for d_lbl, d_det in goal_dict["debt"].items():
                days_el = calculate_days_between(d_det["start_date"])
                total_debt_current += d_det["principal"] * ((1 + (acc_ret.get("debt", 7.0) / 100)) ** (days_el / 365.25))

            total_epf_current = 0.0
            for e_lbl, e_det in goal_dict["epf"].items():
                days_el = calculate_days_between(e_det["start_date"])
                total_epf_current += e_det["principal"] * ((1 + (acc_ret.get("epf", 8.1) / 100)) ** (days_el / 365.25))

            total_o1_current = 0.0
            for o1_lbl, o1_det in goal_dict["other1"].items():
                days_el = calculate_days_between(o1_det["start_date"])
                total_o1_current += o1_det["principal"] * ((1 + (acc_ret.get("other1", 7.0) / 100)) ** (days_el / 365.25))

            total_o2_current = 0.0
            for o2_lbl, o2_det in goal_dict["other2"].items():
                days_el = calculate_days_between(o2_det["start_date"])
                total_o2_current += o2_det["principal"] * ((1 + (acc_ret.get("other2", 7.0) / 100)) ** (days_el / 365.25))

            current_assets_sum = total_mf_current + total_eq_current + total_debt_current + total_epf_current + total_o1_current + total_o2_current
            
            f_mf = calculate_future_value(total_mf_current, acc_ret.get("mf", 12.0), target_date_str)
            f_eq = calculate_future_value(total_eq_current, acc_ret.get("eq", 12.0), target_date_str)
            f_db = calculate_future_value(total_debt_current, acc_ret.get("debt", 7.0), target_date_str)
            f_epf = calculate_future_value(total_epf_current, acc_ret.get("epf", 8.1), target_date_str)
            f_o1 = calculate_future_value(total_o1_current, acc_ret.get("other1", 7.0), target_date_str)
            f_o2 = calculate_future_value(total_o2_current, acc_ret.get("other2", 7.0), target_date_str)
            
            cumulated_future_corpus = f_mf + f_eq + f_db + f_epf + f_o1 + f_o2
            
            # Cards metrics UI
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown(f'<div class="metric-card"><div class="metric-title">Asset Portfolio Today</div><div class="metric-value">{format_indian_currency(current_assets_sum)}</div></div>', unsafe_allow_html=True)
            with c2:
                time_rem = round((datetime.strptime(target_date_str, '%Y-%m-%d').date() - date.today()).days / 365.25, 1)
                st.markdown(f'<div class="metric-card"><div class="metric-title">Milestone Countdown</div><div class="metric-value">{max(0.0, time_rem)} Years</div></div>', unsafe_allow_html=True)
            with c3:
                st.markdown(f'<div class="metric-card"><div class="metric-title">Target Deadline</div><div class="metric-value">{target_date_str}</div></div>', unsafe_allow_html=True)
            with c4:
                st.markdown(f'<div class="metric-card" style="border-color: #38A169;"><div class="metric-title" style="color: #68D391;">Projected End Corpus</div><div class="metric-value-total">{format_indian_currency(cumulated_future_corpus)}</div></div>', unsafe_allow_html=True)

            # --- TARGET MODEL OPTIMIZATIONS ---
            with st.expander("🛠️ Modify Milestone Timeline & Asset Return Assumptions", expanded=False):
                saved_date_obj = datetime.strptime(target_date_str, "%Y-%m-%d").date()
                updated_date = st.date_input("Adjust Target Date", value=saved_date_obj, min_value=date.today(), max_value=date(2076, 12, 31), key=f"ui_date_{goal_name}")
                if str(updated_date) != target_date_str:
                    goal_dict["target_date"] = str(updated_date)
                    trigger_save()
                    st.theme()
                    st.rerun()
                
                st.markdown("#### ⏳ Phase 1: Accumulation Returns (Until Goal is Achieved)")
                r_col1, r_col2, r_col3 = st.columns(3)
                with r_col1:
                    goal_dict["accumulation_returns"]["mf"] = st.number_input("Mutual Funds Growth (%)", min_value=0.0, max_value=40.0, value=float(acc_ret.get("mf", 12.0)), key=f"acc_mf_{goal_name}", on_change=trigger_save)
                    goal_dict["accumulation_returns"]["epf"] = st.number_input("EPF Growth (%)", min_value=0.0, max_value=40.0, value=float(acc_ret.get("epf", 8.1)), key=f"acc_epf_{goal_name}", on_change=trigger_save)
                with r_col2:
                    goal_dict["accumulation_returns"]["eq"] = st.number_input("Equities Growth (%)", min_value=0.0, max_value=40.0, value=float(acc_ret.get("eq", 12.0)), key=f"acc_eq_{goal_name}", on_change=trigger_save)
                    goal_dict["accumulation_returns"]["other1"] = st.number_input("Other 1 Growth (%)", min_value=0.0, max_value=40.0, value=float(acc_ret.get("other1", 7.0)), key=f"acc_o1_{goal_name}", on_change=trigger_save)
                with r_col3:
                    goal_dict["accumulation_returns"]["debt"] = st.number_input("Debt/FD Growth (%)", min_value=0.0, max_value=40.0, value=float(acc_ret.get("debt", 7.0)), key=f"acc_db_{goal_name}", on_change=trigger_save)
                    goal_dict["accumulation_returns"]["other2"] = st.number_input("Other 2 Growth (%)", min_value=0.0, max_value=40.0, value=float(acc_ret.get("other2", 7.0)), key=f"acc_o2_{goal_name}", on_change=trigger_save)
                
                st.markdown("#### 📉 Phase 2: Withdrawal Returns (During Period of Withdrawal)")
                w_col1, w_col2, w_col3 = st.columns(3)
                with w_col1:
                    goal_dict["withdrawal_returns"]["mf"] = st.number_input("Mutual Funds Return (%)", min_value=0.0, max_value=40.0, value=float(wth_ret.get("mf", 8.0)), key=f"wth_mf_{goal_name}", on_change=trigger_save)
                    goal_dict["withdrawal_returns"]["epf"] = st.number_input("EPF Return (%)", min_value=0.0, max_value=40.0, value=float(wth_ret.get("epf", 7.0)), key=f"wth_epf_{goal_name}", on_change=trigger_save)
                with w_col2:
                    goal_dict["withdrawal_returns"]["eq"] = st.number_input("Equities Return (%)", min_value=0.0, max_value=40.0, value=float(wth_ret.get("eq", 8.0)), key=f"wth_eq_{goal_name}", on_change=trigger_save)
                    goal_dict["withdrawal_returns"]["other1"] = st.number_input("Other 1 Return (%)", min_value=0.0, max_value=40.0, value=float(wth_ret.get("other1", 6.0)), key=f"wth_o1_{goal_name}", on_change=trigger_save)
                with w_col3:
                    goal_dict["withdrawal_returns"]["debt"] = st.number_input("Debt/FD Return (%)", min_value=0.0, max_value=40.0, value=float(wth_ret.get("debt", 6.0)), key=f"wth_db_{goal_name}", on_change=trigger_save)
                    goal_dict["withdrawal_returns"]["other2"] = st.number_input("Other 2 Return (%)", min_value=0.0, max_value=40.0, value=float(wth_ret.get("other2", 6.0)), key=f"wth_o2_{goal_name}", on_change=trigger_save)

            st.markdown("###")

            # --- ASSET SECTION MAPPINGS ---
            # 1. Mutual Funds
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
                    mf_records.append({"AMFI Code": code, "Fund Description": scheme_name, "Units Owned": details["units"], "Live NAV": format_indian_currency(nav), "Current Value": format_indian_currency(curr_val)})
                if mf_records: st.dataframe(pd.DataFrame(mf_records), use_container_width=True, hide_index=True)
                else: st.caption("No allocations initialized.")

            # 2. Equities
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
                        if not (t_key.endswith(".BO") or t_key.endswith(".NS")): t_key += ".BO"
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
                    eq_records.append({"Ticker": ticker, "Company Name": comp_name, "Shares": details["qty"], "Avg Cost": format_indian_currency(details["buy_price"]), "Live Spot": format_indian_currency(live_price), "Total Value": format_indian_currency(curr_val)})
                if eq_records: st.dataframe(pd.DataFrame(eq_records), use_container_width=True, hide_index=True)
                else: st.caption("No allocations initialized.")

            # 3. Fixed Income
            st.subheader("🏦 3. Fixed Income, FDs & Liquid Capital")
            sub_col_db1, sub_col_db2 = st.columns([1, 2])
            with sub_col_db1:
                with st.form(key=f"form_db_{goal_name}"):
                    st.markdown("**Manage Debt Instruments**")
                    f_db_lbl = st.text_input("Instrument Name", placeholder="e.g. SBI Fixed Deposit")
                    f_db_inv = st.number_input("Principal Invested (₹)", min_value=0.0, step=500.0)
                    f_db_dat = st.date_input("Issuance Date", max_value=date.today())
                    mode_db = st.selectbox("Action", ["Add/Update Asset", "Delete Asset"])
                    if st.form_submit_button("Execute", use_container_width=True):
                        if mode_db == "Add/Update Asset" and f_db_lbl and f_db_inv > 0:
                            goal_dict["debt"][f_db_lbl] = {"principal": f_db_inv, "start_date": str(f_db_dat)}
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
                    val_today = details["principal"] * ((1 + (acc_ret.get("debt", 7.0) / 100)) ** (days / 365.25))
                    debt_records.append({"Asset Description": label, "Principal": format_indian_currency(details["principal"]), "Days Held": days, "Value Today": format_indian_currency(val_today)})
                if debt_records: st.dataframe(pd.DataFrame(debt_records), use_container_width=True, hide_index=True)
                else: st.caption("No allocations initialized.")

            # 4. EPF Allocation
            st.subheader("💰 4. Employees' Provident Fund (EPF)")
            sub_col_epf1, sub_col_epf2 = st.columns([1, 2])
            with sub_col_epf1:
                with st.form(key=f"form_epf_{goal_name}"):
                    st.markdown("**Manage EPF Balances**")
                    f_epf_lbl = st.text_input("Account Identifier/Label", placeholder="e.g. Primary EPF")
                    f_epf_inv = st.number_input("Current Balance / Principal (₹)", min_value=0.0, step=500.0)
                    f_epf_dat = st.date_input("Balance Update/Start Date", max_value=date.today(), key=f"date_epf_{goal_name}")
                    mode_epf = st.selectbox("Action", ["Add/Update Asset", "Delete Asset"])
                    if st.form_submit_button("Execute", use_container_width=True):
                        if mode_epf == "Add/Update Asset" and f_epf_lbl and f_epf_inv > 0:
                            goal_dict["epf"][f_epf_lbl] = {"principal": f_epf_inv, "start_date": str(f_epf_dat)}
                            trigger_save()
                            st.rerun()
                        elif mode_epf == "Delete Asset" and f_epf_lbl in goal_dict["epf"]:
                            del goal_dict["epf"][f_epf_lbl]
                            trigger_save()
                            st.rerun()
            with sub_col_epf2:
                epf_records = []
                for label, details in goal_dict["epf"].items():
                    days = calculate_days_between(details["start_date"])
                    val_today = details["principal"] * ((1 + (acc_ret.get("epf", 8.1) / 100)) ** (days / 365.25))
                    epf_records.append({"EPF Profile": label, "Principal Base": format_indian_currency(details["principal"]), "Days Accruing": days, "Value Today": format_indian_currency(val_today)})
                if epf_records: st.dataframe(pd.DataFrame(epf_records), use_container_width=True, hide_index=True)
                else: st.caption("No EPF accounts configured.")

            # 5. Other1 Allocation
            st.subheader("🛡️ 5. Custom Asset Class - Other 1")
            sub_col_o1_1, sub_col_o1_2 = st.columns([1, 2])
            with sub_col_o1_1:
                with st.form(key=f"form_o1_{goal_name}"):
                    st.markdown("**Manage Other1 Assets**")
                    f_o1_lbl = st.text_input("Asset Name", placeholder="e.g. Gold / PPF / Real Estate")
                    f_o1_inv = st.number_input("Value / Principal (₹)", min_value=0.0, step=500.0)
                    f_o1_dat = st.date_input("Evaluation Date", max_value=date.today(), key=f"date_o1_{goal_name}")
                    mode_o1 = st.selectbox("Action", ["Add/Update Asset", "Delete Asset"])
                    if st.form_submit_button("Execute", use_container_width=True):
                        if mode_o1 == "Add/Update Asset" and f_o1_lbl and f_o1_inv > 0:
                            goal_dict["other1"][f_o1_lbl] = {"principal": f_o1_inv, "start_date": str(f_o1_dat)}
                            trigger_save()
                            st.rerun()
                        elif mode_o1 == "Delete Asset" and f_o1_lbl in goal_dict["other1"]:
                            del goal_dict["other1"][f_o1_lbl]
                            trigger_save()
                            st.rerun()
            with sub_col_o1_2:
                o1_records = []
                for label, details in goal_dict["other1"].items():
                    days = calculate_days_between(details["start_date"])
                    val_today = details["principal"] * ((1 + (acc_ret.get("other1", 7.0) / 100)) ** (days / 365.25))
                    o1_records.append({"Asset Label": label, "Principal/Base": format_indian_currency(details["principal"]), "Days Held": days, "Value Today": format_indian_currency(val_today)})
                if o1_records: st.dataframe(pd.DataFrame(o1_records), use_container_width=True, hide_index=True)
                else: st.caption("No custom allocations listed.")

            # 6. Other2 Allocation
            st.subheader("🧩 6. Custom Asset Class - Other 2")
            sub_col_o2_1, sub_col_o2_2 = st.columns([1, 2])
            with sub_col_o2_1:
                with st.form(key=f"form_o2_{goal_name}"):
                    st.markdown("**Manage Other2 Assets**")
                    f_o2_lbl = st.text_input("Asset Name", placeholder="e.g. Alternative Investments")
                    f_o2_inv = st.number_input("Value / Principal (₹)", min_value=0.0, step=500.0)
                    f_o2_dat = st.date_input("Evaluation Date", max_value=date.today(), key=f"date_o2_{goal_name}")
                    mode_o2 = st.selectbox("Action", ["Add/Update Asset", "Delete Asset"])
                    if st.form_submit_button("Execute", use_container_width=True):
                        if mode_o2 == "Add/Update Asset" and f_o2_lbl and f_o2_inv > 0:
                            goal_dict["other2"][f_o2_lbl] = {"principal": f_o2_inv, "start_date": str(f_o2_dat)}
                            trigger_save()
                            st.rerun()
                        elif mode_o2 == "Delete Asset" and f_o2_lbl in goal_dict["other2"]:
                            del goal_dict["other2"][f_o2_lbl]
                            trigger_save()
                            st.rerun()
            with sub_col_o2_2:
                o2_records = []
                for label, details in goal_dict["other2"].items():
                    days = calculate_days_between(details["start_date"])
                    val_today = details["principal"] * ((1 + (acc_ret.get("other2", 7.0) / 100)) ** (days / 365.25))
                    o2_records.append({"Asset Label": label, "Principal/Base": format_indian_currency(details["principal"]), "Days Held": days, "Value Today": format_indian_currency(val_today)})
                if o2_records: st.dataframe(pd.DataFrame(o2_records), use_container_width=True, hide_index=True)
                else: st.caption("No custom allocations listed.")

            # --- CUMULATIVE FORECAST BREAKDOWN ---
            st.markdown("###")
            st.markdown("### 📊 Compound Projection Profile (Accumulation Phase)")
            proj_data = {
                "Asset Structure": [
                    "Mutual Funds Group", 
                    "Equities Portfolio", 
                    "Fixed Income / Cash Assets", 
                    "EPF Balances",
                    "Other 1 Assets",
                    "Other 2 Assets",
                    "AGGREGATED PORTFOLIO"
                ],
                "Current Baseline Value": [
                    format_indian_currency(total_mf_current), 
                    format_indian_currency(total_eq_current), 
                    format_indian_currency(total_debt_current), 
                    format_indian_currency(total_epf_current),
                    format_indian_currency(total_o1_current),
                    format_indian_currency(total_o2_current),
                    format_indian_currency(current_assets_sum)
                ],
                "Accumulation Return Factor": [
                    f"{acc_ret.get('mf', 12.0)}%", 
                    f"{acc_ret.get('eq', 12.0)}%", 
                    f"{acc_ret.get('debt', 7.0)}%",  
                    f"{acc_ret.get('epf', 8.1)}%", 
                    f"{acc_ret.get('other1', 7.0)}%", 
                    f"{acc_ret.get('other2', 7.0)}%", 
                    "—"
                ],
                "Terminal Forecast Value": [
                    format_indian_currency(f_mf), 
                    format_indian_currency(f_eq), 
                    format_indian_currency(f_db), 
                    format_indian_currency(f_epf),
                    format_indian_currency(f_o1),
                    format_indian_currency(f_o2),
                    format_indian_currency(cumulated_future_corpus)
                ]
            }
            st.table(pd.DataFrame(proj_data))

            # --- ANNUALIZED DYNAMIC REAL CASH OUTFLOW TIMELINE ---
            st.markdown("---")
            st.markdown("### 📉 Annualized Dynamic Real Cash Outflow Timeline")
            st.caption("Simulate portfolio drawdowns during the distribution phase, tracking annual cash outflows alongside portfolio longevity.")

            ret_conf = goal_dict["retirement_config"]
            c_p1, c_p2, c_p3 = st.columns(3)
            with c_p1:
                ret_years = st.number_input("Retirement Length (Years)", min_value=1, max_value=60, value=int(ret_conf.get("duration_years", 25)), key=f"ret_yr_{goal_name}")
            with c_p2:
                init_outflow = st.number_input("Year 1 Target Outflow (₹)", min_value=0.0, value=float(ret_conf.get("initial_outflow", 1200000.0)), step=50000.0, key=f"ret_out_{goal_name}")
            with c_p3:
                inflation = st.number_input("Expected Inflation (% p.a.)", min_value=0.0, max_value=20.0, value=float(ret_conf.get("inflation_rate", 6.0)), step=0.5, key=f"ret_inf_{goal_name}")
            
            # Save configuration adjustments
            if (ret_years != ret_conf.get("duration_years") or 
                init_outflow != ret_conf.get("initial_outflow") or 
                inflation != ret_conf.get("inflation_rate")):
                goal_dict["retirement_config"]["duration_years"] = ret_years
                goal_dict["retirement_config"]["initial_outflow"] = init_outflow
                goal_dict["retirement_config"]["inflation_rate"] = inflation
                trigger_save()

            # Dynamic Simulation using Phase 2 Withdrawal Assumptions
            # Composite annualized return rate for withdrawal calculated proportionally or averaged
            w_weights = [f_mf, f_eq, f_db, f_epf, f_o1, f_o2]
            w_rates = [wth_ret.get("mf", 8.0), wth_ret.get("eq", 8.0), wth_ret.get("debt", 6.0), wth_ret.get("epf", 7.0), wth_ret.get("other1", 6.0), wth_ret.get("other2", 6.0)]
            
            if cumulated_future_corpus > 0:
                blended_withdrawal_roi = sum((w_weights[i] * w_rates[i]) for i in range(6)) / cumulated_future_corpus
            else:
                blended_withdrawal_roi = 7.0
                
            st.info(f"ℹ️ Blended Portfolio Yield during distribution phase dynamically calculated at: **{blended_withdrawal_roi:.2f}% p.a.** based on asset ratios.")

            sim_corpus = cumulated_future_corpus
            current_outflow = init_outflow
            timeline_records = []
            
            for y in range(1, ret_years + 1):
                if sim_corpus <= 0:
                    timeline_records.append({"Year": f"Year {y}", "Opening Corpus": format_indian_currency(0.0), "Annual Outflow Request": format_indian_currency(current_outflow), "Growth Accrued": format_indian_currency(0.0), "Status": "💥 Corpus Depleted"})
                else:
                    opening = sim_corpus
                    # Asset return application
                    growth = sim_corpus * (blended_withdrawal_roi / 100)
                    sim_corpus += growth
                    
                    # Outflow subtraction
                    outflow_applied = min(current_outflow, sim_corpus)
                    sim_corpus -= outflow_applied
                    
                    timeline_records.append({
                        "Year": f"Year {y}",
                        "Opening Corpus": format_indian_currency(opening),
                        "Annual Outflow Request": format_indian_currency(current_outflow),
                        "Growth Accrued": format_indian_currency(growth),
                        "Status": "✅ Active" if sim_corpus > 0 else "🚨 Final Year"
                    })
                current_outflow *= (1 + (inflation / 100))
                
            st.dataframe(pd.DataFrame(timeline_records), use_container_width=True, hide_index=True)
