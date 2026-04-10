import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Retirement Paycheck Dashboard", layout="wide")

# =========================
# SETTINGS
# =========================
GOAL_MONTHLY = 8000

# =========================
# REAL PORTFOLIO (UPDATED)
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

df = pd.DataFrame(data, columns=[
    "ticker", "shares", "cost_basis", "monthly_income_per_share"
])

# =========================
# PRICE FETCH
# =========================
def get_price(ticker):
    try:
        if ticker == "FDRXX":
            return 1.00
        return yf.Ticker(ticker).history(period="1d")["Close"].iloc[-1]
    except:
        return None

prices = []
for t in df["ticker"]:
    price = get_price(t)
    prices.append(price if price else df.loc[df["ticker"] == t, "cost_basis"].values[0])

df["price"] = prices

# =========================
# CALCULATIONS
# =========================
df["market_value"] = df["shares"] * df["price"]
df["monthly_income"] = df["shares"] * df["monthly_income_per_share"]

portfolio_value = df["market_value"].sum()
monthly_income = df["monthly_income"].sum()
annual_income = monthly_income * 12

# IMPORTANT: TRUE COST BASIS
df["cost_total"] = df["shares"] * df["cost_basis"]
total_invested = df["cost_total"].sum()

gain_loss = portfolio_value - total_invested
gain_pct = (gain_loss / total_invested) * 100 if total_invested else 0

# =========================
# UI
# =========================
st.title("💵 Retirement Paycheck Dashboard")

col1, col2, col3 = st.columns(3)

col1.metric("Portfolio Value", f"${portfolio_value:,.2f}")
col2.metric("Total Invested", f"${total_invested:,.2f}")
col3.metric("Monthly Income", f"${monthly_income:,.2f}")

col1, col2, col3 = st.columns(3)

col1.metric("Annual Income", f"${annual_income:,.2f}")
col2.metric("Gain / Loss", f"${gain_loss:,.2f}", f"{gain_pct:.2f}%")

needed = GOAL_MONTHLY - monthly_income
col3.metric("Still Needed", f"${needed:,.2f}")

# =========================
# GOAL TRACKER
# =========================
progress = monthly_income / GOAL_MONTHLY
st.progress(progress)
st.write(f"**Goal: ${GOAL_MONTHLY:,} / month**")
st.write(f"**You are at {progress*100:.1f}% of your goal**")

# =========================
# TABLE
# =========================
st.subheader("Positions")

st.dataframe(df[[
    "ticker",
    "shares",
    "price",
    "market_value",
    "monthly_income"
]])

# =========================
# QUICK ADD (WORKING)
# =========================
st.subheader("Quick Add Cash")

if st.button("+ $1,000"):
    df.loc[df["ticker"] == "FDRXX", "shares"] += 1000

if st.button("+ $5,000"):
    df.loc[df["ticker"] == "FDRXX", "shares"] += 5000

if st.button("+ $10,000"):
    df.loc[df["ticker"] == "FDRXX", "shares"] += 10000

# =========================
# DEBUG VIEW (OPTIONAL)
# =========================
with st.expander("Performance Breakdown"):
    st.write(f"Portfolio: ${portfolio_value:,.2f}")
    st.write(f"Invested: ${total_invested:,.2f}")
    st.write(f"Gain/Loss: ${gain_loss:,.2f} ({gain_pct:.2f}%)")
