import streamlit as st
import pandas as pd

st.set_page_config(page_title="Retirement Paycheck Dashboard", layout="wide")

# ==============================
# DEFAULT SETTINGS
# ==============================
GOAL_MONTHLY = 8000

# Session state setup
if "invested_amount" not in st.session_state:
    st.session_state.invested_amount = 295000.0

if "extra_cash" not in st.session_state:
    st.session_state.extra_cash = 0.0

# ==============================
# HEADER
# ==============================
st.title("💵 Retirement Paycheck Dashboard")

# ==============================
# ADD MONEY BUTTONS
# ==============================
st.subheader("Add New Money")

col1, col2, col3 = st.columns(3)

if col1.button("+ $1,000"):
    st.session_state.invested_amount += 1000

if col2.button("+ $5,000"):
    st.session_state.invested_amount += 5000

if col3.button("+ $10,000"):
    st.session_state.invested_amount += 10000

# Manual adjust
st.session_state.invested_amount = st.number_input(
    "Total Invested Amount",
    value=st.session_state.invested_amount,
    step=1000.0
)

# ==============================
# PORTFOLIO TABLE
# ==============================
st.subheader("Portfolio")

data = [
    ["SPYI", 1000, 50, 6.0],
    ["QQQI", 800, 45, 7.5],
    ["DIVO", 600, 40, 5.0],
    ["SVOL", 500, 25, 10.0],
]

df = pd.DataFrame(data, columns=["Ticker", "Shares", "Price", "Yield %"])

# Editable table
df = st.data_editor(df, use_container_width=True)

# ==============================
# CALCULATIONS
# ==============================
df["Value"] = df["Shares"] * df["Price"]
df["Annual Income"] = df["Value"] * (df["Yield %"] / 100)

total_value = df["Value"].sum()
annual_income = df["Annual Income"].sum()
monthly_income = annual_income / 12

gain_loss = total_value - st.session_state.invested_amount

# ==============================
# SUMMARY
# ==============================
st.subheader("Summary")

col1, col2, col3 = st.columns(3)

col1.metric("Portfolio Value", f"${total_value:,.0f}")
col2.metric("Monthly Income", f"${monthly_income:,.0f}")
col3.metric("Gain / Loss", f"${gain_loss:,.0f}")

# ==============================
# GOAL TRACKER
# ==============================
st.subheader("Income Goal Progress")

progress = min(monthly_income / GOAL_MONTHLY, 1.0)
st.progress(progress)

st.write(f"Goal: ${GOAL_MONTHLY:,} / month")

# ==============================
# BREAKDOWN
# ==============================
st.subheader("Income Breakdown")

st.dataframe(df[["Ticker", "Value", "Annual Income"]], use_container_width=True)

# ==============================
# NOTES
# ==============================
st.info("Use buttons to simulate adding money. Edit shares, price, and yield to match real data.")
