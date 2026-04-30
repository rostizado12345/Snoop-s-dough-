import json
import os
from datetime import datetime
from typing import Dict, List

import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except Exception:
    yf = None


# ============================================================
# RETIREMENT PAYCHECK DASHBOARD
# UI upgraded version
# - Dark card-style dashboard
# - Bigger section headers
# - Different background cards
# - Cash stays separate
# - Invested Cost Basis label
# - Total Contributions auto-syncs from Holdings Cost Basis
# - Save + backup tools
# - Deploy cash safely
# ============================================================

st.set_page_config(
    page_title="Retirement Paycheck Dashboard",
    page_icon="💵",
    layout="wide",
)

APP_VERSION = "2026-04-30-ui-upgraded-full-v1"

GOAL_MONTHLY = 8000.0
REALISTIC_INCOME_FACTOR = 0.843
CONSERVATIVE_INCOME_FACTOR = 0.632

STATE_FILE = "retirement_dashboard_state.json"
BACKUP_FILE = "retirement_dashboard_state_backup.json"

DEFAULT_CASH_FDRXX = 18690.50

DEFAULT_COLUMNS = [
    "ticker",
    "qty",
    "avg_cost",
    "manual_price",
    "target_weight",
    "annual_yield",
    "payout_frequency",
    "payout_months",
    "notes",
]


DEFAULT_HOLDINGS = [
    ["SPYI", 0.0, 0.0, 0.0, 18.0, 11.5, "monthly", "all", "Primary add"],
    ["DIVO", 0.0, 0.0, 0.0, 16.0, 4.8, "monthly", "all", "Primary add"],
    ["FEPI", 0.0, 0.0, 0.0, 12.0, 24.0, "monthly", "all", "Secondary add"],
    ["QQQI", 0.0, 0.0, 0.0, 12.0, 13.5, "monthly", "all", "Secondary add"],
    ["SVOL", 0.0, 0.0, 0.0, 8.0, 16.0, "monthly", "all", "Secondary add"],
    ["GDXY", 0.0, 0.0, 0.0, 7.0, 30.0, "monthly", "all", "Do not add unless needed"],
    ["CHPY", 0.0, 0.0, 0.0, 5.0, 25.0, "monthly", "all", ""],
    ["AIPI", 0.0, 0.0, 0.0, 5.0, 35.0, "monthly", "all", ""],
    ["TLTW", 0.0, 0.0, 0.0, 5.0, 15.0, "monthly", "all", ""],
    ["IAU", 0.0, 0.0, 0.0, 5.0, 0.0, "none", "", "Gold / stabilizer"],
    ["MLPI", 0.0, 0.0, 0.0, 4.0, 7.0, "quarterly", "3,6,9,12", "Real assets"],
    ["IWMI", 0.0, 0.0, 0.0, 3.0, 13.0, "monthly", "all", ""],
]


# ============================================================
# STYLE
# ============================================================

st.markdown(
    """
<style>
    .stApp {
        background: linear-gradient(180deg, #0f172a 0%, #111827 45%, #0b1120 100%);
        color: #f8fafc;
    }

    h1, h2, h3 {
        color: #f8fafc !important;
        font-weight: 800 !important;
    }

    .main-title {
        font-size: 2.35rem;
        font-weight: 900;
        color: #ffffff;
        margin-bottom: 0.15rem;
    }

    .sub-title {
        font-size: 1.05rem;
        color: #cbd5e1;
        margin-bottom: 1.25rem;
    }

    .section-header {
        font-size: 1.35rem;
        font-weight: 850;
        color: #ffffff;
        padding: 0.65rem 0.95rem;
        border-radius: 14px;
        background: linear-gradient(90deg, #1e293b, #334155);
        border: 1px solid rgba(255,255,255,0.09);
        margin-top: 1.2rem;
        margin-bottom: 0.8rem;
    }

    .metric-card {
        padding: 1rem;
        border-radius: 18px;
        border: 1px solid rgba(255,255,255,0.10);
        box-shadow: 0 8px 22px rgba(0,0,0,0.25);
        min-height: 115px;
    }

    .card-blue {
        background: linear-gradient(135deg, #172554, #1e3a8a);
    }

    .card-green {
        background: linear-gradient(135deg, #064e3b, #047857);
    }

    .card-purple {
        background: linear-gradient(135deg, #3b0764, #6d28d9);
    }

    .card-orange {
        background: linear-gradient(135deg, #7c2d12, #c2410c);
    }

    .card-gray {
        background: linear-gradient(135deg, #1f2937, #374151);
    }

    .card-red {
        background: linear-gradient(135deg, #7f1d1d, #b91c1c);
    }

    .metric-label {
        font-size: 0.9rem;
        color: #dbeafe;
        font-weight: 700;
        margin-bottom: 0.35rem;
    }

    .metric-value {
        font-size: 1.75rem;
        color: #ffffff;
        font-weight: 900;
        line-height: 1.1;
    }

    .metric-small {
        font-size: 0.85rem;
        color: #e2e8f0;
        margin-top: 0.4rem;
    }

    div[data-testid="stDataFrame"] {
        background-color: #111827 !important;
    }

    .stDataEditor {
        color: #111827 !important;
    }

    input, textarea {
        color: #111827 !important;
    }

    div[data-baseweb="input"] input {
        color: #111827 !important;
    }

    .stButton > button {
        border-radius: 12px;
        font-weight: 800;
        border: 1px solid rgba(255,255,255,0.16);
        background: #1e293b;
        color: white;
    }

    .stButton > button:hover {
        background: #334155;
        color: white;
        border-color: rgba(255,255,255,0.30);
    }

    .small-note {
        color: #cbd5e1;
        font-size: 0.9rem;
    }
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# HELPERS
# ============================================================

def money(x: float) -> str:
    try:
        return f"${x:,.2f}"
    except Exception:
        return "$0.00"


def pct(x: float) -> str:
    try:
        return f"{x:.2f}%"
    except Exception:
        return "0.00%"


def default_holdings_df() -> pd.DataFrame:
    return pd.DataFrame(DEFAULT_HOLDINGS, columns=DEFAULT_COLUMNS)


def clean_holdings_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in DEFAULT_COLUMNS:
        if col not in df.columns:
            df[col] = "" if col in ["ticker", "payout_frequency", "payout_months", "notes"] else 0.0

    df = df[DEFAULT_COLUMNS]

    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()

    numeric_cols = ["qty", "avg_cost", "manual_price", "target_weight", "annual_yield"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df["payout_frequency"] = df["payout_frequency"].astype(str).str.lower().str.strip()
    df["payout_months"] = df["payout_months"].astype(str).str.strip()
    df["notes"] = df["notes"].astype(str)

    return df


def load_state() -> Dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
            return state
        except Exception:
            pass

    return {
        "app_version": APP_VERSION,
        "cash_fdrxx": DEFAULT_CASH_FDRXX,
        "holdings": default_holdings_df().to_dict("records"),
        "last_saved": None,
    }


def save_state(state: Dict) -> None:
    state["app_version"] = APP_VERSION
    state["last_saved"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    temp_file = STATE_FILE + ".tmp"

    with open(temp_file, "w") as f:
        json.dump(state, f, indent=2)

    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as old:
                previous = json.load(old)
            with open(BACKUP_FILE, "w") as backup:
                json.dump(previous, backup, indent=2)
        except Exception:
            pass

    os.replace(temp_file, STATE_FILE)


def get_live_price(ticker: str) -> float:
    if not ticker or ticker == "FDRXX":
        return 1.0

    if yf is None:
        return 0.0

    try:
        data = yf.Ticker(ticker).history(period="5d")
        if len(data) > 0:
            return float(data["Close"].dropna().iloc[-1])
    except Exception:
        return 0.0

    return 0.0


def add_prices(df: pd.DataFrame) -> pd.DataFrame:
    df = clean_holdings_df(df)
    prices = []

    for _, row in df.iterrows():
        manual = float(row["manual_price"])
        if manual > 0:
            prices.append(manual)
        else:
            prices.append(get_live_price(row["ticker"]))

    df["price"] = prices
    df["market_value"] = df["qty"] * df["price"]
    df["cost_basis"] = df["qty"] * df["avg_cost"]
    df["gain_loss"] = df["market_value"] - df["cost_basis"]
    df["current_weight"] = 0.0

    total_market = df["market_value"].sum()
    if total_market > 0:
        df["current_weight"] = df["market_value"] / total_market * 100.0

    df["target_value"] = total_market * df["target_weight"] / 100.0
    df["drift_value"] = df["target_value"] - df["market_value"]
    df["annual_income_current"] = df["market_value"] * df["annual_yield"] / 100.0
    df["monthly_income_current"] = df["annual_income_current"] / 12.0
    df["monthly_income_realistic"] = df["monthly_income_current"] * REALISTIC_INCOME_FACTOR
    df["monthly_income_conservative"] = df["monthly_income_current"] * CONSERVATIVE_INCOME_FACTOR

    return df


def parse_payout_months(value: str) -> List[int]:
    value = str(value).strip().lower()

    if value == "all":
        return list(range(1, 13))

    months = []
    for part in value.split(","):
        try:
            m = int(part.strip())
            if 1 <= m <= 12:
                months.append(m)
        except Exception:
            pass

    return months


def income_calendar(df: pd.DataFrame) -> pd.DataFrame:
    month_names = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
    ]

    rows = []

    for month_num, month_name in enumerate(month_names, start=1):
        current_total = 0.0
        realistic_total = 0.0
        conservative_total = 0.0

        for _, row in df.iterrows():
            months = parse_payout_months(row["payout_months"])
            if month_num in months:
                current_total += row["monthly_income_current"]
                realistic_total += row["monthly_income_realistic"]
                conservative_total += row["monthly_income_conservative"]

        rows.append(
            {
                "Month": month_name,
                "Current Estimate": current_total,
                "Realistic Estimate": realistic_total,
                "Conservative Estimate": conservative_total,
            }
        )

    return pd.DataFrame(rows)


def render_metric_card(label, value, small, css_class):
    st.markdown(
        f"""
        <div class="metric-card {css_class}">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-small">{small}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# INIT STATE
# ============================================================

if "state_loaded" not in st.session_state:
    loaded = load_state()
    st.session_state.cash_fdrxx = float(loaded.get("cash_fdrxx", DEFAULT_CASH_FDRXX))
    st.session_state.holdings_df = clean_holdings_df(
        pd.DataFrame(loaded.get("holdings", default_holdings_df().to_dict("records")))
    )
    st.session_state.last_saved = loaded.get("last_saved")
    st.session_state.state_loaded = True


# ============================================================
# HEADER
# ============================================================

st.markdown('<div class="main-title">💵 Retirement Paycheck Dashboard</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="sub-title">UI upgraded version · {APP_VERSION}</div>',
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.header("Controls")

    st.session_state.cash_fdrxx = st.number_input(
        "FDRXX Available Cash",
        min_value=0.0,
        value=float(st.session_state.cash_fdrxx),
        step=100.0,
        format="%.2f",
    )

    st.caption("Cash is separate from invested holdings and does not count as market gain.")

    st.divider()

    add_amount = st.number_input(
        "Add New Cash",
        min_value=0.0,
        value=0.0,
        step=1000.0,
        format="%.2f",
    )

    if st.button("Add Cash to FDRXX"):
        st.session_state.cash_fdrxx += add_amount
        st.success(f"Added {money(add_amount)} to FDRXX cash.")

    st.divider()

    if st.button("Save Current App State"):
        state = {
            "cash_fdrxx": st.session_state.cash_fdrxx,
            "holdings": clean_holdings_df(st.session_state.holdings_df).to_dict("records"),
        }
        save_state(state)
        st.session_state.last_saved = state.get("last_saved")
        st.success("Saved.")

    if st.session_state.last_saved:
        st.caption(f"Last saved: {st.session_state.last_saved}")

    st.divider()

    snapshot = {
        "cash_fdrxx": st.session_state.cash_fdrxx,
        "holdings": clean_holdings_df(st.session_state.holdings_df).to_dict("records"),
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "app_version": APP_VERSION,
    }

    st.download_button(
        "Download Snapshot Backup",
        data=json.dumps(snapshot, indent=2),
        file_name="retirement_dashboard_snapshot.json",
        mime="application/json",
    )

    uploaded = st.file_uploader("Restore Snapshot", type=["json"])

    if uploaded is not None:
        try:
            restored = json.load(uploaded)
            st.session_state.cash_fdrxx = float(restored.get("cash_fdrxx", DEFAULT_CASH_FDRXX))
            st.session_state.holdings_df = clean_holdings_df(pd.DataFrame(restored.get("holdings", [])))
            st.success("Snapshot restored. Press Save Current App State to make it permanent.")
        except Exception as e:
            st.error(f"Could not restore snapshot: {e}")


# ============================================================
# MAIN CALCULATIONS
# ============================================================

priced_df = add_prices(st.session_state.holdings_df)

invested_cost_basis = priced_df["cost_basis"].sum()
total_market_value = priced_df["market_value"].sum()
total_account_value = total_market_value + st.session_state.cash_fdrxx
gain_loss = total_market_value - invested_cost_basis

monthly_current = priced_df["monthly_income_current"].sum()
monthly_realistic = priced_df["monthly_income_realistic"].sum()
monthly_conservative = priced_df["monthly_income_conservative"].sum()

progress_realistic = monthly_realistic / GOAL_MONTHLY * 100.0 if GOAL_MONTHLY else 0.0
capital_needed_realistic = max(0.0, GOAL_MONTHLY - monthly_realistic)

realistic_yield_monthly = monthly_realistic / total_market_value if total_market_value > 0 else 0.0
capital_needed_at_current_yield = (
    capital_needed_realistic / realistic_yield_monthly
    if realistic_yield_monthly > 0
    else 0.0
)


# ============================================================
# SUMMARY CARDS
# ============================================================

st.markdown('<div class="section-header">Main Dashboard</div>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)

with c1:
    render_metric_card(
        "Total Account Value",
        money(total_account_value),
        f"Holdings + FDRXX cash",
        "card-blue",
    )

with c2:
    render_metric_card(
        "Invested Cost Basis",
        money(invested_cost_basis),
        "Auto-synced from holdings cost basis",
        "card-green",
    )

with c3:
    render_metric_card(
        "FDRXX Available Cash",
        money(st.session_state.cash_fdrxx),
        "Cash available to deploy",
        "card-purple",
    )

with c4:
    render_metric_card(
        "Gain / Loss",
        money(gain_loss),
        "Market value minus invested cost basis",
        "card-orange" if gain_loss >= 0 else "card-red",
    )


st.markdown('<div class="section-header">Retirement Paycheck Income</div>', unsafe_allow_html=True)

i1, i2, i3, i4 = st.columns(4)

with i1:
    render_metric_card(
        "Current Income",
        money(monthly_current),
        "Raw estimate before haircut",
        "card-gray",
    )

with i2:
    render_metric_card(
        "Realistic Income",
        money(monthly_realistic),
        f"{REALISTIC_INCOME_FACTOR:.1%} haircut model",
        "card-green",
    )

with i3:
    render_metric_card(
        "Conservative Income",
        money(monthly_conservative),
        f"{CONSERVATIVE_INCOME_FACTOR:.1%} haircut model",
        "card-blue",
    )

with i4:
    render_metric_card(
        "Goal Progress",
        pct(progress_realistic),
        f"Goal: {money(GOAL_MONTHLY)} / month",
        "card-purple",
    )


st.markdown('<div class="section-header">Capital Needed to Reach $8,000 Monthly</div>', unsafe_allow_html=True)

n1, n2 = st.columns(2)

with n1:
    render_metric_card(
        "Monthly Income Gap",
        money(capital_needed_realistic),
        "Based on realistic income estimate",
        "card-orange",
    )

with n2:
    render_metric_card(
        "Estimated Extra Capital Needed",
        money(capital_needed_at_current_yield),
        "Based on current realistic portfolio yield",
        "card-red" if capital_needed_at_current_yield > 0 else "card-green",
    )


# ============================================================
# EDITOR
# ============================================================

st.markdown('<div class="section-header">Holdings Editor</div>', unsafe_allow_html=True)

st.markdown(
    '<div class="small-note">Edit shares, cost basis, manual price, target weight, yield, payout schedule, and notes here. Then press Save Current App State.</div>',
    unsafe_allow_html=True,
)

edited_df = st.data_editor(
    st.session_state.holdings_df,
    use_container_width=True,
    num_rows="dynamic",
    key="holdings_editor",
)

st.session_state.holdings_df = clean_holdings_df(edited_df)


# ============================================================
# DEPLOY CASH
# ============================================================

st.markdown('<div class="section-header">Deploy Cash</div>', unsafe_allow_html=True)

st.markdown(
    '<div class="small-note">This adds shares using dollar amounts and reduces FDRXX cash. Fidelity can buy fractional shares, so dollar amounts are okay.</div>',
    unsafe_allow_html=True,
)

deploy_df = priced_df[["ticker", "price", "current_weight", "target_weight", "drift_value", "notes"]].copy()
deploy_df["deploy_amount"] = 0.0

deploy_input = st.data_editor(
    deploy_df,
    use_container_width=True,
    key="deploy_editor",
    column_config={
        "deploy_amount": st.column_config.NumberColumn(
            "Deploy Amount",
            min_value=0.0,
            step=100.0,
            format="$%.2f",
        ),
        "price": st.column_config.NumberColumn("Price", format="$%.2f"),
        "current_weight": st.column_config.NumberColumn("Current Weight", format="%.2f%%"),
        "target_weight": st.column_config.NumberColumn("Target Weight", format="%.2f%%"),
        "drift_value": st.column_config.NumberColumn("Under / Over Target", format="$%.2f"),
    },
)

total_deploy = float(pd.to_numeric(deploy_input["deploy_amount"], errors="coerce").fillna(0).sum())

st.write(f"Planned deployment: **{money(total_deploy)}**")
st.write(f"Available FDRXX cash: **{money(st.session_state.cash_fdrxx)}**")

if st.button("Deploy Cash Now"):
    if total_deploy <= 0:
        st.warning("Enter at least one deploy amount.")
    elif total_deploy > st.session_state.cash_fdrxx + 0.01:
        st.error("Deployment is larger than available FDRXX cash.")
    else:
        current_df = clean_holdings_df(st.session_state.holdings_df)

        for _, row in deploy_input.iterrows():
            amount = float(row.get("deploy_amount", 0.0) or 0.0)
            ticker = str(row.get("ticker", "")).upper().strip()
            price = float(row.get("price", 0.0) or 0.0)

            if amount <= 0 or not ticker or price <= 0:
                continue

            shares_added = amount / price

            match = current_df["ticker"] == ticker

            if match.any():
                idx = current_df.index[match][0]

                old_qty = float(current_df.at[idx, "qty"])
                old_avg = float(current_df.at[idx, "avg_cost"])

                old_cost = old_qty * old_avg
                new_qty = old_qty + shares_added
                new_cost = old_cost + amount

                current_df.at[idx, "qty"] = new_qty
                current_df.at[idx, "avg_cost"] = new_cost / new_qty if new_qty > 0 else 0.0
            else:
                new_row = {
                    "ticker": ticker,
                    "qty": shares_added,
                    "avg_cost": price,
                    "manual_price": 0.0,
                    "target_weight": 0.0,
                    "annual_yield": 0.0,
                    "payout_frequency": "monthly",
                    "payout_months": "all",
                    "notes": "",
                }
                current_df = pd.concat([current_df, pd.DataFrame([new_row])], ignore_index=True)

        st.session_state.cash_fdrxx -= total_deploy
        st.session_state.holdings_df = clean_holdings_df(current_df)

        state = {
            "cash_fdrxx": st.session_state.cash_fdrxx,
            "holdings": st.session_state.holdings_df.to_dict("records"),
        }
        save_state(state)
        st.session_state.last_saved = state.get("last_saved")

        st.success(f"Deployed {money(total_deploy)} and saved the app state.")
        st.rerun()


# ============================================================
# TABLES
# ============================================================

priced_df = add_prices(st.session_state.holdings_df)

display_df = priced_df[
    [
        "ticker",
        "qty",
        "avg_cost",
        "price",
        "market_value",
        "cost_basis",
        "gain_loss",
        "current_weight",
        "target_weight",
        "drift_value",
        "annual_yield",
        "monthly_income_current",
        "monthly_income_realistic",
        "monthly_income_conservative",
        "notes",
    ]
].copy()

st.markdown('<div class="section-header">Portfolio Detail</div>', unsafe_allow_html=True)

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "ticker": "Ticker",
        "qty": st.column_config.NumberColumn("Shares", format="%.4f"),
        "avg_cost": st.column_config.NumberColumn("Avg Cost", format="$%.2f"),
        "price": st.column_config.NumberColumn("Price", format="$%.2f"),
        "market_value": st.column_config.NumberColumn("Market Value", format="$%.2f"),
        "cost_basis": st.column_config.NumberColumn("Cost Basis", format="$%.2f"),
        "gain_loss": st.column_config.NumberColumn("Gain / Loss", format="$%.2f"),
        "current_weight": st.column_config.NumberColumn("Current Weight", format="%.2f%%"),
        "target_weight": st.column_config.NumberColumn("Target Weight", format="%.2f%%"),
        "drift_value": st.column_config.NumberColumn("Target Drift", format="$%.2f"),
        "annual_yield": st.column_config.NumberColumn("Yield", format="%.2f%%"),
        "monthly_income_current": st.column_config.NumberColumn("Current Monthly", format="$%.2f"),
        "monthly_income_realistic": st.column_config.NumberColumn("Realistic Monthly", format="$%.2f"),
        "monthly_income_conservative": st.column_config.NumberColumn("Conservative Monthly", format="$%.2f"),
        "notes": "Notes",
    },
)


st.markdown('<div class="section-header">Realistic Monthly Dividend Calendar</div>', unsafe_allow_html=True)

cal_df = income_calendar(priced_df)

st.dataframe(
    cal_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Month": "Month",
        "Current Estimate": st.column_config.NumberColumn("Current Estimate", format="$%.2f"),
        "Realistic Estimate": st.column_config.NumberColumn("Realistic Estimate", format="$%.2f"),
        "Conservative Estimate": st.column_config.NumberColumn("Conservative Estimate", format="$%.2f"),
    },
)


# ============================================================
# REBALANCE HELPER
# ============================================================

st.markdown('<div class="section-header">Rebalance Helper</div>', unsafe_allow_html=True)

rebalance_df = priced_df[
    ["ticker", "market_value", "current_weight", "target_weight", "drift_value", "notes"]
].copy()

rebalance_df = rebalance_df.sort_values("drift_value", ascending=False)

st.dataframe(
    rebalance_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "ticker": "Ticker",
        "market_value": st.column_config.NumberColumn("Market Value", format="$%.2f"),
        "current_weight": st.column_config.NumberColumn("Current Weight", format="%.2f%%"),
        "target_weight": st.column_config.NumberColumn("Target Weight", format="%.2f%%"),
        "drift_value": st.column_config.NumberColumn("Positive = Underweight", format="$%.2f"),
        "notes": "Notes",
    },
)

st.markdown(
    """
<div class="small-note">
Rule reminder: use new cash to add to underweight positions first. Avoid trimming unless a position is meaningfully overweight.
</div>
""",
    unsafe_allow_html=True,
)
