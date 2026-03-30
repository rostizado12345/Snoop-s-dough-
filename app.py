import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(layout="wide")

st.title("💰 Retirement Paycheck Dashboard")

# === YOUR PORTFOLIO ===
data = [
    ["AIPI", 433.25, 34.05, 0.08],
    ["CHPY", 315.648, 56.08, 0.09],
    ["DIVO", 853.93, 44.91, 0.045],
    ["FEPI", 369.674, 39.90, 0.12],
    ["GDXY", 2671.718, 13.25, 0.15],
    ["IAU", 141.249, 83.54, 0.0],
    ["IWMI", 247.328, 47.71, 0.10],
    ["IYRI", 314.264, 46.93, 0.04],
    ["MLPI", 206.257, 57.21, 0.08],
    ["QQQI", 413.413, 49.95, 0.12],
    ["SPYI", 895.295, 49.43, 0.10],
    ["SVOL", 1338.302, 15.43, 0.12],
    ["TLTW", 918.594, 22.48, 0.08],
]

df = pd.DataFrame(data, columns=["Ticker", "Shares", "Cost", "Yield"])

# === LIVE PRICES ===
prices = {}
for t in df["Ticker"]:
    try:
        prices[t] = yf.Ticker(t).history(period="1d")["Close"].iloc[-1]
    except:
        prices[t] = 0

df["Price"] = df["Ticker"].map(prices)
df["Value"] = df["Shares"] * df["Price"]

# === TOTAL VALUE ===
total_value = df["Value"].sum()

# === INCOME ===
df["Annual Income"] = df["Value"] * df["Yield"]
monthly_income = df["Annual Income"].sum() / 12

# === DISPLAY ===
st.subheader("💵 Monthly Paycheck")
st.metric("Estimated Monthly Income", f"${monthly_income:,.0f}")

progress = min(monthly_income / 8000, 1.0)
st.progress(progress)
st.write(f"{progress*100:.1f}% of $8,000 goal")

st.subheader("📊 Portfolio Value")
st.metric("Total Value", f"${total_value:,.0f}")

st.subheader("📋 Holdings")
st.dataframe(df)

# === REBALANCE HELPER ===
st.subheader("⚖️ Rebalance Helper")

new_cash = st.number_input("New Cash to Invest", value=0)

col1, col2, col3 = st.columns(3)

if col1.button("+10k"):
    new_cash = 10000
if col2.button("+25k"):
    new_cash = 25000
if col3.button("+50k"):
    new_cash = 50000

if new_cash > 0:
    df["Target"] = total_value * 0.1
    df["Diff"] = df["Target"] - df["Value"]
    df["Buy"] = df["Diff"].apply(lambda x: max(x, 0))

    st.write("💡 Suggested Buys:")
    st.dataframe(df[["Ticker", "Buy"]])
