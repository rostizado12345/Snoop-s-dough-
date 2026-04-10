import streamlit as st
import pandas as pd

st.set_page_config(page_title="Retirement Paycheck Dashboard", layout="wide")

GOAL_MONTHLY = 8000

# ==============================
# STATE
# ==============================
if "portfolio_value" not in st.session_state:
    st.session_state.portfolio_value = 371000.0

# ==============================
# HEADER
# ==============================
st.title("💵 Retirement Paycheck Dashboard")

# ==============================
# PORTFOLIO INPUT
# ==============================
st.subheader("Portfolio Value")

st.session_state.portfolio_value = st.number_input(
    "Total Portfolio Value",
    value=st.session_state.portfolio_value,
    step=1000.0
)

# ==============================
# DEFAULT PORTFOLIO (NO SHARES)
# ==============================
data = [
    ["GDXY", 15, 0.16],
    ["CHPY", 6, 0.05],
    ["FEPI", 7, 0.10],
    ["QQQI", 10, 0.06],
    ["AIPI", 5, 0.12],
    ["SPYI", 12, 0.11],
    ["DIVO", 10, 0.06],
    ["SVOL", 6, 0.05],
    ["TLTW", 6, 0.06],
    ["IYRI", 4, 0.03],
    ["IWMI", 4, 0.04],
    ["IAU", 4, 0.00],
    ["MLPI", 4, 0.07],
    ["FDRXX", 7, 0.04]
]

df = pd.DataFrame(data, columns=["Ticker", "Target %", "Yield"])

# ==============================
# CALCULATIONS
# ==============================
df["Value"] = df["Target %"] / 100 * st.session_state.portfolio_value
df["Monthly Income"] = df["Value"] * df["Yield"] / 12

total_income = df["Monthly Income"].sum()

# ==============================
# SUMMARY
# ==============================
st.subheader("Summary")

col1, col2 = st.columns(2)

col1.metric("Portfolio Value", f"${st.session_state.portfolio_value:,.0f}")
col2.metric("Monthly Income", f"${total_income:,.0f}")

# ==============================
# GOAL
# ==============================
progress = total_income / GOAL_MONTHLY
st.progress(min(progress,1.0))
st.write(f"{progress*100:.1f}% of $8,000/month goal")

# ==============================
# TABLE
# ==============================
st.subheader("Portfolio Breakdown")

st.dataframe(df.style.format({
    "Value": "${:,.0f}",
    "Monthly Income": "${:,.0f}"
}), use_container_width=True)
