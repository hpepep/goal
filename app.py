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
                "expected_returns": {"mf": 12.0, "eq": 12.0, "debt": 7.0},
                "mutual_funds": {}, "equities": {}, "debt": {},
                "retirement_config": {"duration_years": 25, "initial_outflow": 1200000.0, "inflation_rate": 6.0, "post_ret_roi": 8.0}
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
            
            if "retirement_config" not in goal_dict:
                goal_dict["retirement_config"] = {"duration_years": 25, "initial_outflow": 1200000.0, "inflation_rate": 6.0, "post_ret_roi": 8.0}
            
            # --- TOP SECTION: COMPUTE CURRENT ASSETS ---
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
            
            # Summary Banner Metrics
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

            # --- TARGET MODEL CONFIGURATION ---
            with st.expander("🛠️ Modify Milestone Timeline & Asset Return Assumptions", expanded=False):
                r_col1, r_col2, r_col3, r_col4 = st.columns(4)
                with r_col1:
                    saved_date_obj = datetime.strptime(target_date_str, "%Y-%m-%d").date()
                    updated_date = st.date_input("Adjust Target Date", value=saved_date_obj, min_value=date.today(), max_value=date(2076, 12, 31), key=f"ui_date_{goal_name}")
                    if str(updated_date) != target_date_str:
                        goal_dict["target_date"] = str(updated_date)
                        trigger_save()
                        st.rerun()
                with r_col2:
                    goal_dict["expected_returns"]["mf"] = st.number_input(f"Mutual Funds ROI (%)", min_value=0.0, max_value=40.0, value=float(goal_dict["expected_returns"].get("mf", 12.0)), key=f"ui_mf_{goal_name}", on_change=trigger_save)
                with r_col3:
                    goal_dict["expected_returns"]["eq"] = st.number_input(f"Equities ROI (%)", min_value=0.0, max_value=40.0, value=float(goal_dict["expected_returns"].get("eq", 12.0)), key=f"ui_eq_{goal_name}", on_change=trigger_save)
                with r_col4:
                    goal_dict["expected_returns"]["debt"] = st.number_input(f"Debt/FD ROI (%)", min_value=0.0, max_value=40.0, value=float(goal_dict["expected_returns"].get("debt", 7.0)), key=f"ui_db_{goal_name}", on_change=trigger_save)

            st.markdown("###")

            # --- SUB-SECTION 1: MUTUAL FUNDS (INLINE DATA EDITOR) ---
            st.subheader("🧬 1. Mutual Fund Asset Allocations")
            st.caption("Double-click any field to modify allocations. Select the checkbox row-marker and hit the 'Delete' key to drop rows. Add new allocations in the clean row at the bottom.")
            
            mf_list = []
            for code, details in goal_dict["mutual_funds"].items():
                nav, name_mf = fetch_mf_details(code)
                mf_list.append({"AMFI Code": code, "Fund Description": name_mf, "Units Owned": float(details["units"]), "Live NAV (₹)": nav, "Current Value (₹)": round(nav * details["units"], 2)})
            
            df_mf = pd.DataFrame(mf_list) if mf_list else pd.DataFrame(columns=["AMFI Code", "Fund Description", "Units Owned", "Live NAV (₹)", "Current Value (₹)"])
            
            edited_df_mf = st.data_editor(
                df_mf,
                column_config={
                    "AMFI Code": st.column_config.TextColumn(label="AMFI Code", placeholder="e.g. 119597"),
                    "Fund Description": st.column_config.TextColumn(label="Fund Description", disabled=True),
                    "Units Owned": st.column_config.NumberColumn(label="Units Owned", min_value=0.0, step=0.001, format="%.3f"),
                    "Live NAV (₹)": st.column_config.NumberColumn(label="Live NAV (₹)", disabled=True, format="₹ %.2f"),
                    "Current Value (₹)": st.column_config.NumberColumn(label="Current Value (₹)", disabled=True, format="₹ %.2f")
                },
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                key=f"editor_mf_{goal_name}"
            )
            
            # Re-sync modified editor metrics to back-end architecture state
            if not edited_df_mf.equals(df_mf):
                new_mf_dict = {}
                for _, row in edited_df_mf.iterrows():
                    code = str(row["AMFI Code"]).strip()
                    if code and pd.notna(row["Units Owned"]):
                        new_mf_dict[code] = {"units": float(row["Units Owned"])}
                goal_dict["mutual_funds"] = new_mf_dict
                trigger_save()
                st.rerun()

            # --- SUB-SECTION 2: EQUITIES (INLINE DATA EDITOR) ---
            st.subheader("📈 2. Equity Instruments (BSE/NSE Platform)")
            eq_list = []
            for ticker, details in goal_dict["equities"].items():
                live_price, comp_name = fetch_stock_details(ticker)
                eq_list.append({"Ticker Symbol": ticker, "Company Name": comp_name, "Shares Volume": float(details["qty"]), "Avg Purchase Price (₹)": float(details["buy_price"]), "Live Spot Price (₹)": live_price, "Total Asset Value (₹)": round(live_price * details["qty"], 2)})
            
            df_eq = pd.DataFrame(eq_list) if eq_list else pd.DataFrame(columns=["Ticker Symbol", "Company Name", "Shares Volume", "Avg Purchase Price (₹)", "Live Spot Price (₹)", "Total Asset Value (₹)"])
            
            edited_df_eq = st.data_editor(
                df_eq,
                column_config={
                    "Ticker Symbol": st.column_config.TextColumn(label="Ticker Symbol", placeholder="e.g. RELIANCE.NS"),
                    "Company Name": st.column_config.TextColumn(label="Company Name", disabled=True),
                    "Shares Volume": st.column_config.NumberColumn(label="Shares Volume", min_value=0.0, step=1.0),
                    "Avg Purchase Price (₹)": st.column_config.NumberColumn(label="Avg Purchase Price (₹)", min_value=0.0, step=0.01, format="₹ %.2f"),
                    "Live Spot Price (₹)": st.column_config.NumberColumn(label="Live Spot Price (₹)", disabled=True, format="₹ %.2f"),
                    "Total Asset Value (₹)": st.column_config.NumberColumn(label="Total Asset Value (₹)", disabled=True, format="₹ %.2f")
                },
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                key=f"editor_eq_{goal_name}"
            )
            
            if not edited_df_eq.equals(df_eq):
                new_eq_dict = {}
                for _, row in edited_df_eq.iterrows():
                    ticker = str(row["Ticker Symbol"]).strip().upper()
                    if ticker and pd.notna(row["Shares Volume"]):
                        if not (ticker.endswith(".BO") or ticker.endswith(".NS")):
                            ticker += ".BO"
                        new_eq_dict[ticker] = {"qty": float(row["Shares Volume"]), "buy_price": float(row["Avg Purchase Price (₹)"]) if pd.notna(row["Avg Purchase Price (₹)"]) else 0.0}
                goal_dict["equities"] = new_eq_dict
                trigger_save()
                st.rerun()

            # --- SUB-SECTION 3: DEBT / FIXED INCOME (INLINE DATA EDITOR) ---
            st.subheader("🏦 3. Fixed Income, FDs & Liquid Capital")
            debt_list = []
            for label, details in goal_dict["debt"].items():
                days = calculate_days_between(details["start_date"])
                val_today = details["principal"] * ((1 + (details["roi"] / 100)) ** (days / 365.25))
                debt_list.append({"Asset Description": label, "Principal Invested (₹)": float(details["principal"]), "Issuance Date (YYYY-MM-DD)": details["start_date"], "Contracted Yield (% p.a.)": float(details["roi"]), "Days Held": days, "Current Value Today (₹)": round(val_today, 2)})
            
            df_debt = pd.DataFrame(debt_list) if debt_list else pd.DataFrame(columns=["Asset Description", "Principal Invested (₹)", "Issuance Date (YYYY-MM-DD)", "Contracted Yield (% p.a.)", "Days Held", "Current Value Today (₹)"])
            
            edited_df_debt = st.data_editor(
                df_debt,
                column_config={
                    "Asset Description": st.column_config.TextColumn(label="Asset Description", placeholder="e.g. SBI Fixed Deposit"),
                    "Principal Invested (₹)": st.column_config.NumberColumn(label="Principal Invested (₹)", min_value=0.0, step=100.0, format="₹ %.2f"),
                    "Issuance Date (YYYY-MM-DD)": st.column_config.TextColumn(label="Issuance Date (YYYY-MM-DD)", placeholder="e.g. 2024-01-15"),
                    "Contracted Yield (% p.a.)": st.column_config.NumberColumn(label="Contracted Yield (% p.a.)", min_value=0.0, max_value=25.0, step=0.05, format="%.2f %%"),
                    "Days Held": st.column_config.NumberColumn(label="Days Held", disabled=True),
                    "Current Value Today (₹)": st.column_config.NumberColumn(label="Current Value Today (₹)", disabled=True, format="₹ %.2f")
                },
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                key=f"editor_db_{goal_name}"
            )
            
            if not edited_df_debt.equals(df_debt):
                new_debt_dict = {}
                for _, row in edited_df_debt.iterrows():
                    lbl = str(row["Asset Description"]).strip()
                    date_str = str(row["Issuance Date (YYYY-MM-DD)"]).strip()
                    if lbl and date_str and pd.notna(row["Principal Invested (₹)"]):
                        try:
                            datetime.strptime(date_str, "%Y-%m-%d")
                        except:
                            date_str = str(date.today())
                        new_debt_dict[lbl] = {"principal": float(row["Principal Invested (₹)"]), "start_date": date_str, "roi": float(row["Contracted Yield (% p.a.)"]) if pd.notna(row["Contracted Yield (% p.a.)"]) else 0.0}
                goal_dict["debt"] = new_debt_dict
                trigger_save()
                st.rerun()

            # --- CUMULATIVE FORECAST MATRIX BREAKDOWN ---
            st.markdown("###")
            st.markdown("### 📊 Compound Projection Profile")
            proj_data = {
                "Asset Structure": ["Mutual Funds Group", "Equities Portfolio", "Fixed Income / Cash Assets", "AGGREGATED PORTFOLIO"],
                "Current Baseline Value": [format_indian_currency(total_mf_current), format_indian_currency(total_eq_current), format_indian_currency(total_debt_current), format_indian_currency(current_assets_sum)],
                "Modeled Return Factor": [f"{goal_dict['expected_returns']['mf']}%", f"{goal_dict['expected_returns']['eq']}%", f"{goal_dict['expected_returns']['debt']}%", "—"],
                "Terminal Forecast Value": [format_indian_currency(f_mf), format_indian_currency(f_eq), format_indian_currency(f_db), format_indian_currency(cumulated_future_corpus)]
            }
            st.table(pd.DataFrame(proj_data))

            # --- DRAWDOWN MODEL DISTRIBUTION MATRIX ---
            st.markdown("---")
            st.markdown("### 📉 Annualized Dynamic Real Cash Outflow Timeline")
            
            ret_conf = goal_dict["retirement_config"]
            c_p1, c_p2, c_p3, c_p4 = st.columns(4)
            with c_p1:
                ret_years = st.number_input("Retirement Length (Years)", min_value=1, max_value=60, value=int(ret_conf.get("duration_years", 25)), key=f"ret_yr_{goal_name}")
            with c_p2:
                init_outflow = st.number_input("Year 1 Target Outflow (₹)", min_value=0.0, value=float(ret_conf.get("initial_outflow", 1200000.0)), step=50000.0, key=f"ret_out_{goal_name}")
            with c_p3:
                inflation = st.number_input("Expected Inflation (% p.a.)", min_value=0.0, max_value=20.0, value=float(ret_conf.get("inflation_rate", 6.0)), step=0.5, key=f"ret_inf_{goal_name}")
            with c_p4:
                post_roi = st.number_input("Post-Retirement Portfolio ROI (%)", min_value=0.0, max_value=25.0, value=float(ret_conf.get("post_ret_roi", 8.0)), step=0.5, key=f"ret_roi_{goal_name}")

            if (ret_years != ret_conf["duration_years"] or init_outflow != ret_conf["initial_outflow"] or 
                inflation != ret_conf["inflation_rate"] or post_roi != ret_conf["post_ret_roi"]):
                goal_dict["retirement_config"] = {"duration_years": ret_years, "initial_outflow": init_outflow, "inflation_rate": inflation, "post_ret_roi": post_roi}
                trigger_save()

            sim_records = []
            running_portfolio = cumulated_future_corpus
            target_year_start = datetime.strptime(target_date_str, "%Y-%m-%d").year

            for y in range(1, ret_years + 1):
                current_calendar_year = target_year_start + (y - 1)
                yearly_outflow = init_outflow * ((1 + (inflation / 100)) ** (y - 1))
                
                opening_balance = running_portfolio
                if running_portfolio >= yearly_outflow:
                    portfolio_after_outflow = running_portfolio - yearly_outflow
                    growth = portfolio_after_outflow * (post_roi / 100)
                    closing_balance = portfolio_after_outflow + growth
                    running_portfolio = closing_balance
                else:
                    yearly_outflow = max(0.0, running_portfolio)
                    growth = 0.0
                    closing_balance = 0.0
                    running_portfolio = 0.0
                
                sim_records.append({
                    "Year": current_calendar_year,
                    "Timeline Index": f"Year {y}",
                    "Opening Portfolio Balance (₹)": round(opening_balance, 2),
                    "Annual Real Cash Outflow (₹)": round(yearly_outflow, 2),
                    "Portfolio Growth Yield (₹)": round(growth, 2),
                    "Closing Portfolio Balance (₹)": round(closing_balance, 2)
                })

            df_sim = pd.DataFrame(sim_records)

            chart_data = df_sim[["Timeline Index", "Annual Real Cash Outflow (₹)", "Closing Portfolio Balance (₹)"]].copy()
            chart_data = chart_data.rename(columns={"Annual Real Cash Outflow (₹)": "Annual Outflow", "Closing Portfolio Balance (₹)": "Remaining Portfolio Value"})
            
            ch_col1, ch_col2 = st.columns([3, 2])
            with ch_col1:
                st.markdown("**Visual Trajectory Overlay**")
                st.line_chart(chart_data.set_index("Timeline Index"), y=["Remaining Portfolio Value", "Annual Outflow"], color=["#4FD1C5", "#E53E3E"])
            with ch_col2:
                st.markdown("**Outflow Growth Scale**")
                st.bar_chart(chart_data.set_index("Timeline Index"), y="Annual Outflow", color="#E53E3E")

            st.markdown("#### Detailed Drawdown Ledger")
            df_display = df_sim.copy()
            for col in ["Opening Portfolio Balance (₹)", "Annual Real Cash Outflow (₹)", "Portfolio Growth Yield (₹)", "Closing Portfolio Balance (₹)"]:
                df_display[col] = df_display[col].apply(format_indian_currency)
            st.dataframe(df_display, use_container_width=True, hide_index=True)
