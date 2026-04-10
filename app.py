import math
from typing import Tuple

import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except Exception:
    yf = None

st.set_page_config(page_title="Retirement Paycheck Dashboard", page_icon="💵", layout="wide")

GOAL_MONTHLY = 8000.0
DEFAULT_TOTAL_INVESTED = 295000.0

DEFAULT_ROWS = [
    {"Ticker": "SPYI", "Shares": 1000.0, "Price": 50.0, "Yield %": 12.0, "Use Live Price": True},
    {"Ticker": "QQQI", "Shares": 800.0, "Price": 45.0, "Yield %": 14.0, "Use Live Price": True},
    {"Ticker": "DIVO", "Shares": 600.0, "Price": 40.0, "Yield %": 5.0, "Use Live Price": True},
    {"Ticker": "SVOL", "Shares": 500.0, "Price": 25.0, "Yield %": 16.0, "Use Live Price": True},
]

TABLE_COLUMNS = ["Ticker", "Shares", "Price", "Yield %", "Use Live Price"]


def init_state() -> None:
    if "invested_amount" not in st.session_state:
        st.session_state.invested_amount = DEFAULT_TOTAL_INVESTED
    if "portfolio_df" not in st.session_state:
        st.session_state.portfolio_df = pd.DataFrame(DEFAULT_ROWS)[TABLE_COLUMNS]
    if "last_live_refresh" not in st.session_state:
        st.session_state.last_live_refresh = "Not refreshed yet"


def to_float(value, default: float = 0.0) -> float:
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def safe_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def clean_portfolio_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=TABLE_COLUMNS)

    working = df.copy()

    for col in TABLE_COLUMNS:
        if col not in working.columns:
            working[col] = False if col == "Use Live Price" else 0.0

    working["Ticker"] = working["Ticker"].fillna("").astype(str).str.upper().str.strip()
    working = working[working["Ticker"] != ""].copy()

    working["Shares"] = working["Shares"].apply(lambda x: max(to_float(x, 0.0), 0.0))
    working["Price"] = working["Price"].apply(lambda x: max(to_float(x, 0.0), 0.0))
    working["Yield %"] = working["Yield %"].apply(lambda x: max(to_float(x, 0.0), 0.0))
    working["Use Live Price"] = working["Use Live Price"].apply(safe_bool)

    return working[TABLE_COLUMNS].reset_index(drop=True)


def fetch_live_prices(tickers: list[str]) -> dict[str, float]:
    prices: dict[str, float] = {}
    if yf is None or not tickers:
        return prices

    unique_tickers = sorted({t for t in tickers if t})
    for ticker in unique_tickers:
        try:
            hist = yf.Ticker(ticker).history(period="5d", interval="1d", auto_adjust=False)
            if hist is not None and not hist.empty:
                close_series = hist["Close"].dropna()
                if not close_series.empty:
                    prices[ticker] = float(close_series.iloc[-1])
                    continue
        except Exception:
            pass

        try:
            info = yf.Ticker(ticker).fast_info
            last_price = getattr(info, "last_price", None)
            if last_price:
                prices[ticker] = float(last_price)
        except Exception:
            pass

    return prices


def build_calculation_df(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    calc = clean_portfolio_df(df)
    if calc.empty:
        calc["Current Price"] = []
        calc["Position Value"] = []
        calc["Annual Income"] = []
        calc["Monthly Income"] = []
        return calc, 0

    live_prices = fetch_live_prices(calc["Ticker"].tolist())
    live_count = 0
    current_prices = []

    for _, row in calc.iterrows():
        ticker = row["Ticker"]
        manual_price = to_float(row["Price"], 0.0)
        use_live = safe_bool(row["Use Live Price"])
        live_price = live_prices.get(ticker)

        if use_live and live_price and live_price > 0:
            current_prices.append(float(live_price))
            live_count += 1
        else:
            current_prices.append(manual_price)

    calc["Current Price"] = current_prices
    calc["Position Value"] = calc["Shares"] * calc["Current Price"]
    calc["Annual Income"] = calc["Position Value"] * (calc["Yield %"] / 100.0)
    calc["Monthly Income"] = calc["Annual Income"] / 12.0

    return calc, live_count


def fmt_money(value: float) -> str:
    return f"${value:,.2f}"


def fmt_pct(value: float) -> str:
    return f"{value:.1f}%"


init_state()

st.title("💵 Retirement Paycheck Dashboard")
st.caption("Working version with invested amount tracking, editable portfolio, income math, and optional live prices.")

st.subheader("Add New Money")
button_cols = st.columns(3)
if button_cols[0].button("+ $1,000", use_container_width=True):
    st.session_state.invested_amount += 1000.0
if button_cols[1].button("+ $5,000", use_container_width=True):
    st.session_state.invested_amount += 5000.0
if button_cols[2].button("+ $10,000", use_container_width=True):
    st.session_state.invested_amount += 10000.0

st.session_state.invested_amount = st.number_input(
    "Total Invested Amount",
    min_value=0.0,
    step=1000.0,
    value=float(st.session_state.invested_amount),
    format="%.2f",
)

st.subheader("Portfolio")
edited_df = st.data_editor(
    st.session_state.portfolio_df,
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    column_config={
        "Ticker": st.column_config.TextColumn("Ticker", help="ETF or stock symbol, like SPYI"),
        "Shares": st.column_config.NumberColumn("Shares", min_value=0.0, step=1.0, format="%.4f"),
        "Price": st.column_config.NumberColumn("Price", min_value=0.0, step=0.01, format="%.2f"),
        "Yield %": st.column_config.NumberColumn("Yield %", min_value=0.0, step=0.1, format="%.2f"),
        "Use Live Price": st.column_config.CheckboxColumn("Use Live Price"),
    },
)

st.session_state.portfolio_df = clean_portfolio_df(edited_df)

did_refresh = st.button("Refresh Live Prices", use_container_width=True)
if did_refresh:
    st.session_state.last_live_refresh = pd.Timestamp.now().strftime("%Y-%m-%d %I:%M:%S %p")
st.caption(f"Last refresh click: {st.session_state.last_live_refresh}")

calc_df, live_count = build_calculation_df(st.session_state.portfolio_df)

total_invested = float(st.session_state.invested_amount)
portfolio_value = float(calc_df["Position Value"].sum()) if not calc_df.empty else 0.0
annual_income = float(calc_df["Annual Income"].sum()) if not calc_df.empty else 0.0
monthly_income = annual_income / 12.0
gain_loss = portfolio_value - total_invested
goal_progress = (monthly_income / GOAL_MONTHLY * 100.0) if GOAL_MONTHLY > 0 else 0.0

st.subheader("Summary")
m1, m2 = st.columns(2)
m3, m4 = st.columns(2)
m1.metric("Total Invested", fmt_money(total_invested))
m2.metric("Portfolio Value", fmt_money(portfolio_value))
m3.metric("Monthly Income", fmt_money(monthly_income))
m4.metric("Annual Income", fmt_money(annual_income))

if gain_loss >= 0:
    st.success(f"Gain / Loss: {fmt_money(gain_loss)}")
else:
    st.error(f"Gain / Loss: {fmt_money(gain_loss)}")

st.subheader("Goal Progress")
st.progress(min(max(goal_progress / 100.0, 0.0), 1.0))
g1, g2, g3 = st.columns(3)
g1.metric("Income Goal", fmt_money(GOAL_MONTHLY) + "/mo")
g2.metric("Current Progress", fmt_pct(goal_progress))
g3.metric("Gap to Goal", fmt_money(max(GOAL_MONTHLY - monthly_income, 0.0)) + "/mo")

st.subheader("Income Breakdown")
if calc_df.empty:
    st.info("Add at least one holding in the portfolio table above.")
else:
    display_df = calc_df.copy()
    display_df["Current Price"] = display_df["Current Price"].map(fmt_money)
    display_df["Position Value"] = display_df["Position Value"].map(fmt_money)
    display_df["Annual Income"] = display_df["Annual Income"].map(fmt_money)
    display_df["Monthly Income"] = display_df["Monthly Income"].map(fmt_money)
    display_df["Yield %"] = display_df["Yield %"].map(lambda x: f"{x:.2f}%")
    st.dataframe(
        display_df[["Ticker", "Shares", "Current Price", "Position Value", "Yield %", "Monthly Income", "Annual Income"]],
        use_container_width=True,
        hide_index=True,
    )

with st.expander("Notes / How the math works"):
    st.write(
        """
- **Portfolio Value** = Shares × Current Price
- **Annual Income** = Position Value × Yield %
- **Monthly Income** = Annual Income ÷ 12
- **Gain/Loss** = Portfolio Value − Total Invested Amount

If live prices are available, checked rows use Yahoo Finance through `yfinance`.
If live prices are not available, the app falls back to the manual **Price** column.
"""
    )
    st.write(f"Rows currently using live price successfully: **{live_count}**")
    if yf is None:
        st.warning("`yfinance` is not installed in this environment, so manual prices are being used.")
