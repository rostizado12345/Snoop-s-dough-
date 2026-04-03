import streamlit as st
import pandas as pd
import altair as alt

st.set_page_config(
    page_title="Richard's Retirement Paycheck",
    page_icon="💵",
    layout="wide"
)

# -------------------------
# STYLE
# -------------------------
st.markdown("""
<style>
.block-container { max-width: 1250px; }
.hero { font-size: 2.8rem; font-weight: 800; }
.sub { color: #9ca3af; }
</style>
""", unsafe_allow_html=True)

def money(x):
    return f"${float(x):,.0f}"

GOAL = 8000

# -------------------------
# LOAD CSV
# -------------------------
df = pd.read_csv("portfolio.csv")

df["Shares"] = pd.to_numeric(df["Shares"])
df["Price"] = pd.to_numeric(df["Price"])
df["Yield"] = pd.to_numeric(df["Yield"])

# -------------------------
# CALCULATIONS
# -------------------------
df["Value"] = df["Shares"] * df["Price"]

# realistic scaling
df["Annual_Optimistic"] = df["Value"] * df["Yield"]
df["Annual_Expected"] = df["Annual_Optimistic"] * 0.90
df["Annual_Conservative"] = df["Annual_Optimistic"] * 0.75

df["Monthly_Optimistic"] = df["Annual_Optimistic"] / 12
df["Monthly_Expected"] = df["Annual_Expected"] / 12
df["Monthly_Conservative"] = df["Annual_Conservative"] / 12

opt = df["Monthly_Optimistic"].sum()
exp = df["Monthly_Expected"].sum()
con = df["Monthly_Conservative"].sum()

# -------------------------
# HEADER
# -------------------------
st.title("Richard’s Retirement Paycheck")

st.markdown(f"<div class='hero'>{money(exp)}</div>", unsafe_allow_html=True)
st.markdown("<div class='sub'>Expected Monthly Income (realistic)</div>", unsafe_allow_html=True)

# -------------------------
# THREE NUMBERS
# -------------------------
c1, c2, c3 = st.columns(3)

c1.metric("Conservative", money(con))
c2.metric("Expected", money(exp))
c3.metric("Optimistic", money(opt))

st.progress(exp / GOAL)

# -------------------------
# TABLE
# -------------------------
view = df[["Ticker","Value","Monthly_Conservative","Monthly_Expected","Monthly_Optimistic"]].copy()

view = view.sort_values("Monthly_Expected", ascending=False)

total = pd.DataFrame([{
    "Ticker":"TOTAL",
    "Value": df["Value"].sum(),
    "Monthly_Conservative": con,
    "Monthly_Expected": exp,
    "Monthly_Optimistic": opt
}])

view = pd.concat([view, total])

st.dataframe(
    view,
    use_container_width=True,
    column_config={
        "Ticker":"Holding",
        "Value": st.column_config.NumberColumn("Value", format="$%0.0f"),
        "Monthly_Conservative": st.column_config.NumberColumn("Conservative", format="$%0.0f"),
        "Monthly_Expected": st.column_config.NumberColumn("Expected", format="$%0.0f"),
        "Monthly_Optimistic": st.column_config.NumberColumn("Optimistic", format="$%0.0f"),
    }
)

# -------------------------
# CHART
# -------------------------
months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

chart_df = pd.DataFrame({
    "Month": months,
    "Expected Income": [exp]*12
})

chart = alt.Chart(chart_df).mark_bar().encode(
    x="Month",
    y="Expected Income"
)

st.altair_chart(chart, use_container_width=True)
