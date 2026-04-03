import streamlit as st
import pandas as pd

# -----------------------------
# PAGE SETUP
# -----------------------------
st.set_page_config(
    page_title="Richard's Retirement Paycheck",
    page_icon="💵",
    layout="wide"
)

# -----------------------------
# YOUR FULL HOLDINGS (EDIT VALUES ONLY LATER IF NEEDED)
# -----------------------------
data = {
    "Symbol": [
        "AIPI","CHPY","DIVO","FEPI","GDXY",
        "IAU","IYRI","IWMI","MLPI",
        "QQQI","SPYI","SVOL","TLTW"
    ],
    "Value": [
        0,0,0,0,0,
        12201,15920,12948,12814,
        20778,44514,20716,20686
    ]
}

df = pd.DataFrame(data)

# -----------------------------
# CALCULATIONS (AUTO)
# -----------------------------
total_invested = 295090
current_value = 299240
total_gain = current_value - total_invested
gain_pct = (total_gain / total_invested) * 100

# -----------------------------
# HEADER
# -----------------------------
st.title("Richard’s Retirement Paycheck")
st.caption("Real paycheck calendar view with estimated weekly deposit timing.")

# -----------------------------
# PORTFOLIO SUMMARY (BIG)
# -----------------------------
st.markdown("## 📊 Portfolio Summary")

st.metric("💰 Total Gain", f"${total_gain:,.0f}", f"{gain_pct:.2f}%")

col1, col2 = st.columns(2)

with col1:
    st.metric("💼 Invested", f"${total_invested:,.0f}")

with col2:
    st.metric("📈 Current Value", f"${current_value:,.0f}")

# -----------------------------
# INCOME SNAPSHOT
# -----------------------------
st.markdown("## 💵 Income Snapshot")

expected_income = 2533
goal = 8000
gap = goal - expected_income
progress = expected_income / goal

st.metric("Expected Monthly Income", f"${expected_income:,.0f}")
st.progress(progress)
st.caption(f"Goal: ${goal:,} • Gap: ${gap:,}")

# -----------------------------
# HOLDINGS TABLE (FULL)
# -----------------------------
st.markdown("## 📋 Holdings")
st.dataframe(df, use_container_width=True)
