import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Retirement Paycheck Dashboard", layout="wide")

# =========================
# SETTINGS
# =========================
GOAL_MONTHLY = 8000.0

# =========================
# SESSION STATE
# =========================
if "extra_contributions" not in st.session_state:
    st.session_state.extra_contributions = 0.0

# =========================
# REAL PORTFOLIO (UPDATED)
# NOTE:
# These values appear to be ANNUAL income per share, not monthly.
# =========================
data = [
    ["AIPI", 668.196, 34.00, 4.2],
    ["CHPY", 434.433, 56.80, 3.3],
    ["DIVO", 857.354, 44.70, 1.8],
    ["GDXY", 2698.805, 13.10, 3.0],
    ["FEPI", 662.641, 40.30, 4.8],
    ["QQQI", 509.798, 50.30, 4.5],
    ["SPYI", 895.295, 49.40, 5.6],
    ["SVOL", 1338.302, 15.40, 1.9],
    ["TLTW", 927.268, 22.20, 2.5],
    ["IAU", 141.249, 83.50, 0.0],
    ["IWMI", 247.328, 47.70, 3.5],
    ["IYRI", 314.264, 46.90, 3.5],
    ["MLPI", 206.257, 57.20, 4.0],
    ["FDRXX", 50690.28, 1.00, 0.0],  # CASH
]

df = pd.DataFrame(
    data,
    columns=["ticker", "shares", "cost_basis", "annual_income_per_share"]
)

# Add contributed cash to FDRXX so it counts as invested money, not fake gain
df.loc[df["ticker"] == "FDRXX", "shares"] += st.session_state.extra_contributions

# =========================
# PRICE FETCH
# =========================
@st.cache_data(ttl=900)
def get_price(ticker: str):
    try:
        if ticker == "FDRXX":
            return 1.00
        hist = yf.Ticker(ticker).history(period="5d")
        if hist.empty:
            return None
        return float(hist["Close"].dropna().iloc[-1])
    except Exception:
        return None

prices = []
for _, row in df.iterrows():
    p = get_price(row["ticker"])
    if p is None:
        p = float(row["cost_basis"])
    prices.append(float(p))

df["price"] = prices

# =========================
# CALCULATIONS
# =========================
df["market_value"] = df["shares"] * df["price"]
df["cost_total"] = df["shares"] * df["cost_basis"]

# Treat income-per-share as ANNUAL, then convert to monthly
df["annual_income"] = df["shares"] * df["annual_income_per_share"]
df["monthly_income"] = df["annual_income"] / 12.0

portfolio_value = float(df["market_value"].sum())
total_invested = float(df["cost_total"].sum())
annual_income = float(df["annual_income"].sum())
monthly_income = float(df["monthly_income"].sum())

gain_loss = portfolio_value - total_invested
gain_pct = (gain_loss / total_invested * 100) if total_invested else 0.0

needed = GOAL_MONTHLY - monthly_income
progress = (monthly_income / GOAL_MONTHLY) if GOAL_MONTHLY > 0 else 0.0
progress = max(0.0, min(progress, 1.0))

# =========================
# UI
# =========================
st.title("💵 Retirement Paycheck Dashboard")

top1, top2, top3 = st.columns(3)
top1.metric("Portfolio Value", f"${portfolio_value:,.2f}")
top2.metric("Total Invested", f"${total_invested:,.2f}")
top3.metric("Monthly Income", f"${monthly_income:,.2f}")

mid1, mid2, mid3 = st.columns(3)
mid1.metric("Annual Income", f"${annual_income:,.2f}")
mid2.metric("Gain / Loss", f"${gain_loss:,.2f}", f"{gain_pct:.2f}%")

if needed > 0:
    mid3.metric("Still Needed", f"${needed:,.2f}")
else:
    mid3.metric("Goal Surplus", f"${abs(needed):,.2f}")

# =========================
# GOAL TRACKER
# =========================
st.subheader("Goal Tracker")
st.progress(progress)
st.write(f"**Goal: ${GOAL_MONTHLY:,.0f} / month**")
st.write(f"**You are at {progress * 100:.1f}% of your goal**")

# =========================
# QUICK ADD CASH
# =========================
st.subheader("Quick Add Cash")

add1, add2, add3, add4 = st.columns(4)

if add1.button("+ $1,000"):
    st.session_state.extra_contributions += 1000.0
    st.rerun()

if add2.button("+ $5,000"):
    st.session_state.extra_contributions += 5000.0
    st.rerun()

if add3.button("+ $10,000"):
    st.session_state.extra_contributions += 10000.0
    st.rerun()

if add4.button("Reset Added Cash"):
    st.session_state.extra_contributions = 0.0
    st.rerun()

st.caption(f"Added cash tracked in app: ${st.session_state.extra_contributions:,.2f}")

# =========================
# TABLE
# =========================
st.subheader("Positions")

display_df = df[[
    "ticker",
    "shares",
    "price",
    "market_value",
    "annual_income",
    "monthly_income"
]].copy()

display_df["shares"] = display_df["shares"].map(lambda x: f"{x:,.3f}")
display_df["price"] = display_df["price"].map(lambda x: f"${x:,.2f}")
display_df["market_value"] = display_df["market_value"].map(lambda x: f"${x:,.2f}")
display_df["annual_income"] = display_df["annual_income"].map(lambda x: f"${x:,.2f}")
display_df["monthly_income"] = display_df["monthly_income"].map(lambda x: f"${x:,.2f}")

st.dataframe(display_df, use_container_width=True, hide_index=True)

# =========================
# DEBUG VIEW
# =========================
with st.expander("Performance Breakdown"):
    st.write(f"Portfolio Value: ${portfolio_value:,.2f}")
    st.write(f"Total Invested: ${total_invested:,.2f}")
    st.write(f"Gain / Loss: ${gain_loss:,.2f} ({gain_pct:.2f}%)")
    st.write(f"Annual Income: ${annual_income:,.2f}")
    st.write(f"Monthly Income: ${monthly_income:,.2f}")
    if needed > 0:
        st.write(f"Still Needed: ${needed:,.2f}")
    else:
        st.write(f"Goal Surplus: ${abs(needed):,.2f}")
