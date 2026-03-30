import streamlit as st
import pandas as pd
import yfinance as yf

st.set_page_config(page_title="Retirement Paycheck Dashboard", layout="wide")

st.title("💰 Retirement Paycheck Dashboard")

# =========================
# YOUR PORTFOLIO HOLDINGS
# Ticker, Shares, Cost Basis, Estimated Yield
# =========================
data = [
    ["AIPI", 433.25, 34.05, 0.08],
    ["CHPY", 315.648, 56.08, 0.09],
    ["DIVO", 853.93, 44.91, 0.045],
    ["FEPI", 369.674, 39.90, 0.12],
    ["GDXY", 2671.718, 13.25, 0.15],
    ["IAU", 141.249, 83.54, 0.00],
    ["IWMI", 247.328, 47.71, 0.10],
    ["IYRI", 314.264, 46.93, 0.04],
    ["MLPI", 206.257, 57.21, 0.08],
    ["QQQI", 413.413, 49.95, 0.12],
    ["SPYI", 895.295, 49.43, 0.10],
    ["SVOL", 1338.302, 15.43, 0.12],
    ["TLTW", 918.594, 22.48, 0.08],
    ["FDRXX", 17700.22, 1.00, 0.00],  # cash position
]

df = pd.DataFrame(data, columns=["Ticker", "Shares", "Cost Basis", "Yield"])

# =========================
# TARGET WEIGHTS
# =========================
target_weights = {
    "GDXY": 0.15,
    "CHPY": 0.06,
    "FEPI": 0.07,
    "QQQI": 0.10,
    "AIPI": 0.05,
    "SPYI": 0.12,
    "SVOL": 0.06,
    "DIVO": 0.10,
    "IYRI": 0.05,
    "IWMI": 0.04,
    "IAU": 0.04,
    "MLPI": 0.04,
    "TLTW": 0.07,
    "FDRXX": 0.05,
}

# =========================
# LIVE PRICE FUNCTION
# =========================
@st.cache_data(ttl=900)
def get_latest_price(ticker: str) -> float:
    if ticker == "FDRXX":
        return 1.00
    try:
        hist = yf.Ticker(ticker).history(period="5d")
        if not hist.empty:
            return float(hist["Close"].dropna().iloc[-1])
    except Exception:
        pass
    return 0.0

@st.cache_data(ttl=900)
def get_previous_close(ticker: str, latest_price: float) -> float:
    if ticker == "FDRXX":
        return 1.00
    try:
        hist = yf.Ticker(ticker).history(period="5d")
        closes = hist["Close"].dropna()
        if len(closes) >= 2:
            return float(closes.iloc[-2])
        elif len(closes) == 1:
            return float(closes.iloc[-1])
    except Exception:
        pass
    return latest_price

prices = []
prev_closes = []

for ticker in df["Ticker"]:
    latest = get_latest_price(ticker)
    prev = get_previous_close(ticker, latest)
    prices.append(latest)
    prev_closes.append(prev)

df["Price"] = prices
df["Prev Close"] = prev_closes

# =========================
# CALCULATIONS
# =========================
df["Value"] = df["Shares"] * df["Price"]
df["Cost Value"] = df["Shares"] * df["Cost Basis"]
df["Gain/Loss $"] = df["Value"] - df["Cost Value"]
df["Gain/Loss %"] = df["Gain/Loss $"] / df["Cost Value"]
df["Day Change $"] = (df["Price"] - df["Prev Close"]) * df["Shares"]
df["Annual Income"] = df["Value"] * df["Yield"]
df["Monthly Income"] = df["Annual Income"] / 12

total_value = df["Value"].sum()
total_cost = df["Cost Value"].sum()
total_gain = df["Gain/Loss $"].sum()
total_gain_pct = (total_gain / total_cost) if total_cost > 0 else 0
total_day_change = df["Day Change $"].sum()
monthly_income = df["Monthly Income"].sum()

df["Current Weight %"] = df["Value"] / total_value
df["Target Weight %"] = df["Ticker"].map(target_weights).fillna(0.0)
df["Target Value"] = df["Target Weight %"] * total_value
df["Rebalance $"] = df["Target Value"] - df["Value"]

# =========================
# TOP DASHBOARD
# =========================
st.header("💵 Monthly Paycheck")
st.metric("Estimated Monthly Income", f"${monthly_income:,.0f}")

progress = min(monthly_income / 8000, 1.0)
st.progress(progress)
st.write(f"{progress * 100:.1f}% of $8,000 goal")

c1, c2, c3 = st.columns(3)
c1.metric("Portfolio Value", f"${total_value:,.2f}", f"${total_day_change:,.2f} today")
c2.metric("Gain / Loss", f"${total_gain:,.2f}", f"{total_gain_pct:.2%}")
c3.metric("Cash Position (FDRXX)", f"${df.loc[df['Ticker']=='FDRXX', 'Value'].sum():,.2f}")

# =========================
# HOLDINGS TABLE
# =========================
st.header("📋 Holdings")

display_df = df.copy()

display_df["Price"] = display_df["Price"].map(lambda x: f"${x:,.2f}")
display_df["Prev Close"] = display_df["Prev Close"].map(lambda x: f"${x:,.2f}")
display_df["Value"] = display_df["Value"].map(lambda x: f"${x:,.2f}")
display_df["Cost Value"] = display_df["Cost Value"].map(lambda x: f"${x:,.2f}")
display_df["Gain/Loss $"] = display_df["Gain/Loss $"].map(lambda x: f"${x:,.2f}")
display_df["Gain/Loss %"] = display_df["Gain/Loss %"].map(lambda x: f"{x:.2%}")
display_df["Day Change $"] = display_df["Day Change $"].map(lambda x: f"${x:,.2f}")
display_df["Annual Income"] = display_df["Annual Income"].map(lambda x: f"${x:,.2f}")
display_df["Monthly Income"] = display_df["Monthly Income"].map(lambda x: f"${x:,.2f}")
display_df["Current Weight %"] = display_df["Current Weight %"].map(lambda x: f"{x:.2%}")
display_df["Target Weight %"] = display_df["Target Weight %"].map(lambda x: f"{x:.2%}")
display_df["Target Value"] = display_df["Target Value"].map(lambda x: f"${x:,.2f}")
display_df["Rebalance $"] = display_df["Rebalance $"].map(lambda x: f"${x:,.2f}")

st.dataframe(display_df, use_container_width=True)

# =========================
# QUICK ADD CASH TOOL
# =========================
st.header("➕ Add New Cash")

q1, q2, q3, q4 = st.columns(4)

if q1.button("+10k"):
    st.session_state["new_cash"] = 10000
if q2.button("+25k"):
    st.session_state["new_cash"] = 25000
if q3.button("+50k"):
    st.session_state["new_cash"] = 50000
if q4.button("Clear"):
    st.session_state["new_cash"] = 0

if "new_cash" not in st.session_state:
    st.session_state["new_cash"] = 0

new_cash = st.number_input("New Cash to Invest", min_value=0.0, value=float(st.session_state["new_cash"]), step=1000.0)

# =========================
# REBALANCE HELPER
# =========================
st.header("⚖️ Rebalance Helper")

rebalance_df = df[["Ticker", "Value", "Current Weight %", "Target Weight %", "Rebalance $"]].copy()

rebalance_df["Action"] = rebalance_df["Rebalance $"].apply(
    lambda x: "Buy" if x > 1 else ("Trim" if x < -1 else "Hold")
)

rebalance_show = rebalance_df.copy()
rebalance_show["Value"] = rebalance_show["Value"].map(lambda x: f"${x:,.2f}")
rebalance_show["Current Weight %"] = rebalance_show["Current Weight %"].map(lambda x: f"{x:.2%}")
rebalance_show["Target Weight %"] = rebalance_show["Target Weight %"].map(lambda x: f"{x:.2%}")
rebalance_show["Rebalance $"] = rebalance_show["Rebalance $"].map(lambda x: f"${x:,.2f}")

st.dataframe(rebalance_show, use_container_width=True)

# =========================
# ADD-CASH SUGGESTIONS
# =========================
if new_cash > 0:
    st.subheader("💡 Suggested Buys With New Cash")

    buy_df = df.copy()
    buy_df["Gap To Target"] = buy_df["Target Value"] - buy_df["Value"]
    buy_df = buy_df[buy_df["Gap To Target"] > 0].copy()
    buy_df = buy_df.sort_values("Gap To Target", ascending=False)

    total_gap = buy_df["Gap To Target"].sum()

    if total_gap > 0:
        buy_df["Suggested Buy $"] = buy_df["Gap To Target"] / total_gap * new_cash
        buy_df["Suggested Shares"] = buy_df["Suggested Buy $"] / buy_df["Price"]
    else:
        buy_df["Suggested Buy $"] = 0
        buy_df["Suggested Shares"] = 0

    show_buy_df = buy_df[["Ticker", "Price", "Gap To Target", "Suggested Buy $", "Suggested Shares"]].copy()
    show_buy_df["Price"] = show_buy_df["Price"].map(lambda x: f"${x:,.2f}")
    show_buy_df["Gap To Target"] = show_buy_df["Gap To Target"].map(lambda x: f"${x:,.2f}")
    show_buy_df["Suggested Buy $"] = show_buy_df["Suggested Buy $"].map(lambda x: f"${x:,.2f}")
    show_buy_df["Suggested Shares"] = show_buy_df["Suggested Shares"].map(lambda x: f"{x:,.3f}")

    st.dataframe(show_buy_df, use_container_width=True)

# =========================
# SIMPLE MONTHLY PAYCHECK VIEW
# =========================
st.header("📅 Estimated Monthly Paycheck by Holding")

income_view = df[["Ticker", "Monthly Income", "Annual Income"]].copy()
income_view = income_view.sort_values("Monthly Income", ascending=False)

income_show = income_view.copy()
income_show["Monthly Income"] = income_show["Monthly Income"].map(lambda x: f"${x:,.2f}")
income_show["Annual Income"] = income_show["Annual Income"].map(lambda x: f"${x:,.2f}")

st.dataframe(income_show, use_container_width=True)

st.caption("FDRXX is treated as cash at $1.00 per share so your total portfolio value includes your cash balance.")
