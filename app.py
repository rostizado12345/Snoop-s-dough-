import streamlit as st
import pandas as pd
import json
from pathlib import Path

st.set_page_config(
    page_title="Richard's Retirement Paycheck",
    page_icon="💵",
    layout="wide"
)

TOTAL_INVESTED = 295090.00
DATA_FILE = Path("holdings_data.json")

DEFAULT_HOLDINGS = [
    {"Symbol": "AIPI",  "Shares": 433.250,   "FallbackPrice": 34.21, "ActualYield": 0.22, "SafeYield": 0.10, "Week": "Week 2", "Est_Day": 12},
    {"Symbol": "CHPY",  "Shares": 315.648,   "FallbackPrice": 55.93, "ActualYield": 0.18, "SafeYield": 0.10, "Week": "Week 2", "Est_Day": 13},
    {"Symbol": "DIVO",  "Shares": 857.354,   "FallbackPrice": 45.00, "ActualYield": 0.05, "SafeYield": 0.05, "Week": "Week 3", "Est_Day": 15},
    {"Symbol": "FDRXX", "Shares": 17790.140, "FallbackPrice": 1.00,  "ActualYield": 0.03, "SafeYield": 0.03, "Week": "Cash",   "Est_Day": "-"},
    {"Symbol": "FEPI",  "Shares": 369.674,   "FallbackPrice": 40.38, "ActualYield": 0.22, "SafeYield": 0.10, "Week": "Week 4", "Est_Day": 21},
    {"Symbol": "GDXY",  "Shares": 2671.718,  "FallbackPrice": 14.15, "ActualYield": 0.30, "SafeYield": 0.12, "Week": "Week 1", "Est_Day": 8},
    {"Symbol": "IAU",   "Shares": 141.249,   "FallbackPrice": 87.94, "ActualYield": 0.00, "SafeYield": 0.00, "Week": "-",      "Est_Day": "-"},
    {"Symbol": "IWMI",  "Shares": 247.328,   "FallbackPrice": 47.89, "ActualYield": 0.08, "SafeYield": 0.08, "Week": "Week 3", "Est_Day": 17},
    {"Symbol": "IYRI",  "Shares": 314.264,   "FallbackPrice": 48.08, "ActualYield": 0.06, "SafeYield": 0.06, "Week": "Week 3", "Est_Day": 16},
    {"Symbol": "MLPI",  "Shares": 206.257,   "FallbackPrice": 56.19, "ActualYield": 0.08, "SafeYield": 0.08, "Week": "Week 3", "Est_Day": 18},
    {"Symbol": "QQQI",  "Shares": 413.413,   "FallbackPrice": 50.26, "ActualYield": 0.20, "SafeYield": 0.10, "Week": "Week 4", "Est_Day": 24},
    {"Symbol": "SPYI",  "Shares": 895.295,   "FallbackPrice": 49.72, "ActualYield": 0.12, "SafeYield": 0.10, "Week": "Week 4", "Est_Day": 25},
    {"Symbol": "SVOL",  "Shares": 1338.302,  "FallbackPrice": 15.48, "ActualYield": 0.16, "SafeYield": 0.10, "Week": "Week 4", "Est_Day": 26},
    {"Symbol": "TLTW",  "Shares": 918.594,   "FallbackPrice": 22.52, "ActualYield": 0.15, "SafeYield": 0.10, "Week": "Week 4", "Est_Day": 22},
]

def load_holdings():
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r") as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass
    return DEFAULT_HOLDINGS.copy()

def save_holdings(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

@st.cache_data(ttl=900)
def get_live_prices(symbols):
    prices = {}
    try:
        import yfinance as yf
        for symbol in symbols:
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="5d", auto_adjust=False)
                if hist is not None and not hist.empty:
                    closes = hist["Close"].dropna()
                    last_close = float(closes.iloc[-1])
                    prev_close = float(closes.iloc[-2]) if len(closes) >= 2 else last_close
                    prices[symbol] = {
                        "last": last_close,
                        "prev_close": prev_close,
                        "source": "Yahoo"
                    }
                else:
                    prices[symbol] = None
            except Exception:
                prices[symbol] = None
    except Exception:
        for symbol in symbols:
            prices[symbol] = None
    return prices

if "holdings_data" not in st.session_state:
    st.session_state.holdings_data = load_holdings()

st.title("Richard’s Retirement Paycheck")
st.caption("Auto prices from Yahoo Finance when available. Safe income is for planning. Actual income is bonus/upside.")

edit_mode = st.toggle("✏️ Edit Holdings", value=False)

if edit_mode:
    st.warning("Editing mode is ON. Change Shares only, then click Save Changes.")

    edit_df = pd.DataFrame(st.session_state.holdings_data)[["Symbol", "Shares"]]

    edited_df = st.data_editor(
        edit_df,
        hide_index=True,
        use_container_width=True,
        disabled=["Symbol"],
        column_config={
            "Symbol": st.column_config.TextColumn("Symbol"),
            "Shares": st.column_config.NumberColumn("Shares", format="%.3f", step=0.001),
        },
        key="holdings_editor",
    )

    col_save, col_cancel = st.columns(2)

    with col_save:
        if st.button("💾 Save Changes", use_container_width=True):
            updated = []
            existing = {item["Symbol"]: item for item in st.session_state.holdings_data}

            for _, row in edited_df.iterrows():
                symbol = row["Symbol"]
                item = existing[symbol].copy()
                item["Shares"] = float(row["Shares"])
                updated.append(item)

            st.session_state.holdings_data = updated
            save_holdings(updated)
            st.cache_data.clear()
            st.success("Holdings saved.")

    with col_cancel:
        if st.button("Cancel", use_container_width=True):
            st.session_state.holdings_data = load_holdings()
            st.rerun()

df = pd.DataFrame(st.session_state.holdings_data)
live_prices = get_live_prices(df["Symbol"].tolist())

last_prices = []
prev_closes = []
sources = []

for _, row in df.iterrows():
    symbol = row["Symbol"]
    fallback = float(row["FallbackPrice"])
    live = live_prices.get(symbol)

    if live and live.get("last") is not None:
        last = float(live["last"])
        prev = float(live["prev_close"])
        source = live.get("source", "Yahoo")
    else:
        last = fallback
        prev = fallback
        source = "Fallback"

    last_prices.append(last)
    prev_closes.append(prev)
    sources.append(source)

df["Last"] = last_prices
df["PrevClose"] = prev_closes
df["Price Source"] = sources

df["Value"] = df["Shares"] * df["Last"]
df["Day Change $"] = df["Shares"] * (df["Last"] - df["PrevClose"])
df["Day Change %"] = (((df["Last"] - df["PrevClose"]) / df["PrevClose"]).fillna(0)) * 100

current_value = df["Value"].sum()
total_gain = current_value - TOTAL_INVESTED
gain_pct = (total_gain / TOTAL_INVESTED) * 100 if TOTAL_INVESTED else 0

df["% of Acct"] = (df["Value"] / current_value) * 100 if current_value else 0

df["Safe Monthly Income"] = (df["Value"] * df["SafeYield"]) / 12.0
df["Actual Monthly Income"] = (df["Value"] * df["ActualYield"]) / 12.0

safe_income = df["Safe Monthly Income"].sum()
actual_income = df["Actual Monthly Income"].sum()

weekly_safe = safe_income / 4.0
weekly_actual = actual_income / 4.0

income_goal = 8000.0
safe_gap = income_goal - safe_income
safe_progress = min(safe_income / income_goal, 1.0) if income_goal else 0

df["Conservative"] = df["Safe Monthly Income"]
df["Expected"] = (df["Safe Monthly Income"] * 0.5) + (df["Actual Monthly Income"] * 0.5)
df["Aggressive"] = df["Actual Monthly Income"]

schedule = (
    df[df["Week"].isin(["Week 1", "Week 2", "Week 3", "Week 4"])]
    .groupby(["Week", "Est_Day"], as_index=False)["Safe Monthly Income"]
    .sum()
    .rename(columns={"Safe Monthly Income": "Estimated Deposit"})
)

week_order = {"Week 1": 1, "Week 2": 2, "Week 3": 3, "Week 4": 4}
schedule["sort"] = schedule["Week"].map(week_order)
schedule = schedule.sort_values(["sort", "Est_Day"]).drop(columns="sort")

price_source_note = "Yahoo live prices" if (df["Price Source"] == "Yahoo").any() else "Fallback prices from your Fidelity screenshots"
st.info(f"Price source right now: {price_source_note}")

st.markdown("## 📊 Portfolio Summary")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("💼 Invested", f"${TOTAL_INVESTED:,.0f}")
with col2:
    st.metric("📈 Current Value", f"${current_value:,.0f}")
with col3:
    st.metric("💰 Total Gain", f"${total_gain:,.0f}", f"{gain_pct:.2f}%")

st.markdown("## 💵 Income Snapshot")

inc1, inc2, inc3 = st.columns(3)
with inc1:
    st.metric("🛡️ Safe Income", f"${safe_income:,.0f}")
with inc2:
    st.metric("⚖️ Middle Income", f"${df['Expected'].sum():,.0f}")
with inc3:
    st.metric("🚀 Actual Income", f"${actual_income:,.0f}")

st.progress(safe_progress)
st.caption(f"Safe goal check: ${income_goal:,.0f} • Safe gap: ${safe_gap:,.0f}")

wk1, wk2 = st.columns(2)
with wk1:
    st.metric("Weekly Safe Estimate", f"${weekly_safe:,.0f}")
with wk2:
    st.metric("Weekly Actual Estimate", f"${weekly_actual:,.0f}")

st.markdown("## 🗓️ Monthly Pay View")
pay_view = df[["Symbol", "Value", "Conservative", "Expected", "Aggressive"]].copy()
pay_view["Value"] = pay_view["Value"].map(lambda x: f"${x:,.2f}")
pay_view["Conservative"] = pay_view["Conservative"].map(lambda x: f"${x:,.0f}")
pay_view["Expected"] = pay_view["Expected"].map(lambda x: f"${x:,.0f}")
pay_view["Aggressive"] = pay_view["Aggressive"].map(lambda x: f"${x:,.0f}")
st.dataframe(pay_view, use_container_width=True, hide_index=True)

st.markdown("## 📅 Weekly Pay Timing")
schedule_view = schedule.copy()
schedule_view["Estimated Deposit"] = schedule_view["Estimated Deposit"].map(lambda x: f"${x:,.0f}")
st.dataframe(schedule_view, use_container_width=True, hide_index=True)

st.markdown("## 📋 Holdings")
holdings_view = df[["Symbol", "Shares", "Last", "Value", "% of Acct", "Safe Monthly Income", "Actual Monthly Income", "Price Source"]].copy()
holdings_view["Shares"] = holdings_view["Shares"].map(lambda x: f"{x:,.3f}")
holdings_view["Last"] = holdings_view["Last"].map(lambda x: f"${x:,.2f}")
holdings_view["Value"] = holdings_view["Value"].map(lambda x: f"${x:,.2f}")
holdings_view["% of Acct"] = holdings_view["% of Acct"].map(lambda x: f"{x:.2f}%")
holdings_view["Safe Monthly Income"] = holdings_view["Safe Monthly Income"].map(lambda x: f"${x:,.0f}")
holdings_view["Actual Monthly Income"] = holdings_view["Actual Monthly Income"].map(lambda x: f"${x:,.0f}")
st.dataframe(holdings_view, use_container_width=True, hide_index=True)
