import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Retirement Paycheck Dashboard",
    page_icon="💵",
    layout="wide",
)

# ---------------------------
# DEFAULT SETTINGS
# ---------------------------
GOAL_MONTHLY = 8000

if "total_invested" not in st.session_state:
    st.session_state.total_invested = 295000.0

# ---------------------------
# HEADER
# ---------------------------
st.title("💵 Retirement Paycheck Dashboard")

# ---------------------------
# EDIT TOTAL INVESTED BUTTON
# ---------------------------
col1, col2 = st.columns([2,1])

with col1:
    st.metric("Total Invested", f"${st.session_state.total_invested:,.0f}")

with col2:
    if st.button("Edit Total Invested"):
        st.session_state.edit_mode = True

if st.session_state.get("edit_mode", False):
    new_val = st.number_input(
        "Enter Total Invested",
        value=st.session_state.total_invested,
        step=1000.0
    )
    if st.button("Save"):
        st.session_state.total_invested = new_val
        st.session_state.edit_mode = False
        st.rerun()

# ---------------------------
# PORTFOLIO DATA
# ---------------------------
data = [
    ["GDXY", 2600, 3.00],
    ["CHPY", 300, 3.30],
    ["FEPI", 370, 4.80],
    ["QQQI", 410, 4.50],
    ["AIPI", 430, 4.20],
    ["SPYI", 900, 5.60],
    ["SVOL", 1300, 1.90],
    ["DIVO", 850, 1.80],
]

df = pd.DataFrame(data, columns=["Ticker", "Shares", "Annual Income/Share"])

# ---------------------------
# CALCULATIONS
# ---------------------------
df["Annual Income"] = df["Shares"] * df["Annual Income/Share"]
total_annual = df["Annual Income"].sum()
monthly_income = total_annual / 12

# ---------------------------
# DISPLAY TABLE
# ---------------------------
st.subheader("Portfolio")
st.dataframe(df, use_container_width=True)

# ---------------------------
# INCOME SECTION
# ---------------------------
col1, col2 = st.columns(2)

with col1:
    st.metric("Monthly Income", f"${monthly_income:,.0f}")

with col2:
    st.metric("Annual Income", f"${total_annual:,.0f}")

# ---------------------------
# GOAL TRACKING
# ---------------------------
progress = min(monthly_income / GOAL_MONTHLY, 1.0)

st.progress(progress)

st.write(f"Goal: ${GOAL_MONTHLY:,.0f} / month")

if monthly_income >= GOAL_MONTHLY:
    st.success("✅ Goal reached!")
else:
    st.warning(f"⚠️ You are at {progress*100:.1f}% of your goal")
