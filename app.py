import math
from typing import Dict, List

import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except Exception:
    yf = None

st.set_page_config(page_title="Retirement Paycheck Dashboard", page_icon="💵", layout="wide")

GOAL_MONTHLY = 8000.0
DEFAULT_TOTAL_INVESTED = 327000.0
DEFAULT_PORTFOLIO_VALUE = 371522.97
DEFAULT_CASH_SWEEP = 32000.0

DEFAULT_COLUMNS = [
    "ticker",
    "target_weight",
    "annual_yield",
    "manual_price",
    "payout_frequency",
    "payout_months",
    "notes",
]

DEFAULT_ROWS = [
    ["GDXY", 15.0, 0.165, 14.58, "monthly", "all", ""],
    ["CHPY", 6.0, 0.050, 61.01, "monthly", "all", ""],
    ["FEPI", 7.0, 0.118, 51.75, "monthly", "all", ""],
    ["QQQI", 10.0, 0.053, 51.94, "monthly", "all", ""],
    ["AIPI", 5.0, 0.124, 33.79, "monthly", "all", ""],
    ["SPYI", 12.0, 0.085, 51.11, "monthly", "all", ""],
    ["DIVO", 10.0, 0.053, 45.53, "monthly", "all", ""],
    ["SVOL", 6.0, 0.122, 15.75, "monthly", "all", ""],
    ["TLTW", 6.0, 0.089, 22.48, "monthly", "all", ""],
    ["IYRI", 4.0, 0.037, 48.84, "quarterly", "3,6,9,12", ""],
    ["IWMI", 4.0, 0.080, 15.75, "monthly", "all", ""],
    ["IAU", 4.0, 0.000, 55.20, "none", "none", ""],
    ["MLPI", 4.0, 0.086, 25.10, "quarterly", "3,6,9,12", ""],
    ["FDRXX", 7.0, 0.045, 1.00, "monthly", "all", "Cash / sweep"],
]

MONTH_NAME_MAP = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
}


def make_default_df() -> pd.DataFrame:
    return pd.DataFrame(DEFAULT_ROWS, columns=DEFAULT_COLUMNS)


def ensure_state() -> None:
    if "portfolio_df" not in st.session_state:
        st.session_state.portfolio_df = make_default_df()
    if "total_invested" not in st.session_state:
        st.session_state.total_invested = float(DEFAULT_TOTAL_INVESTED)
    if "portfolio_value" not in st.session_state:
        st.session_state.portfolio_value = float(DEFAULT_PORTFOLIO_VALUE)
    if "cash_sweep" not in st.session_state:
        st.session_state.cash_sweep = float(DEFAULT_CASH_SWEEP)


def clean_numeric(series: pd.Series, default: float = 0.0) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(default)


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in DEFAULT_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[DEFAULT_COLUMNS]

    text_cols = ["ticker", "payout_frequency", "payout_months", "notes"]
    for col in text_cols:
        df[col] = df[col].fillna("").astype(str)

    numeric_cols = ["target_weight", "annual_yield", "manual_price"]
    for col in numeric_cols:
        df[col] = clean_numeric(df[col], 0.0)

    df["ticker"] = df["ticker"].str.upper().str.strip()
    df = df[df["ticker"] != ""].reset_index(drop=True)
    return df


def fetch_live_prices(tickers: List[str]) -> Dict[str, float]:
    prices: Dict[str, float] = {}

    if not tickers or yf is None:
        return prices

    symbols = [t for t in tickers if t and t.upper() != "FDRXX"]

    if not symbols:
        return prices

    try:
        history = yf.download(
            tickers=symbols,
            period="5d",
            interval="1d",
            auto_adjust=False,
            progress=False,
            group_by="ticker",
            threads=False,
        )

        if history is None or getattr(history, "empty", True):
            return prices

        if isinstance(history.columns, pd.MultiIndex):
            for ticker in symbols:
                try:
                    close_series = history[(ticker, "Close")].dropna()
                    if not close_series.empty:
                        prices[ticker] = float(close_series.iloc[-1])
                except Exception:
                    continue
        else:
            close_series = history["Close"].dropna()
            if len(symbols) == 1 and not close_series.empty:
                prices[symbols[0]] = float(close_series.iloc[-1])

    except Exception:
        return prices

    return prices


def parse_months(text: str) -> List[int]:
    raw = str(text).strip().lower()

    if raw in {"", "none", "nan"}:
        return []

    if raw == "all":
        return list(range(1, 13))

    months: List[int] = []
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        try:
            month_num = int(piece)
            if 1 <= month_num <= 12:
                months.append(month_num)
        except Exception:
            continue

    return sorted(list(set(months)))


def monthly_income_schedule(df: pd.DataFrame) -> pd.DataFrame:
    month_totals = {month: 0.0 for month in range(1, 13)}

    for _, row in df.iterrows():
        annual_income = float(row["annual_income"])
        frequency = str(row["payout_frequency"]).strip().lower()
        months = parse_months(row["payout_months"])

        if annual_income <= 0:
            continue

        if frequency == "monthly":
            for month in range(1, 13):
                month_totals[month] += annual_income / 12.0
        elif frequency == "quarterly":
            payout_months = months if months else [3, 6, 9, 12]
            per_payment = annual_income / max(len(payout_months), 1)
            for month in payout_months:
                month_totals[month] += per_payment
        elif frequency == "semiannual":
            payout_months = months if months else [6, 12]
            per_payment = annual_income / max(len(payout_months), 1)
            for month in payout_months:
                month_totals[month] += per_payment
        elif frequency == "annual":
            payout_months = months if months else [12]
            per_payment = annual_income / max(len(payout_months), 1)
            for month in payout_months:
                month_totals[month] += per_payment

    return pd.DataFrame(
        {
            "Month": [MONTH_NAME_MAP[m] for m in range(1, 13)],
            "Estimated Income": [month_totals[m] for m in range(1, 13)],
        }
    )


def currency(value: float) -> str:
    return f"${value:,.2f}"


ensure_state()

st.title("💵 Retirement Paycheck Dashboard")
st.caption("Full dashboard with fixed sizing logic: based on total portfolio value instead of fake share counts.")

top_right = st.columns([3, 1])[1]
with top_right:
    if st.button("Reset Table to Default", use_container_width=True):
        st.session_state.portfolio_df = make_default_df()
        st.session_state.total_invested = float(DEFAULT_TOTAL_INVESTED)
        st.session_state.portfolio_value = float(DEFAULT_PORTFOLIO_VALUE)
        st.session_state.cash_sweep = float(DEFAULT_CASH_SWEEP)
        st.rerun()

st.subheader("Add New Money")

button_cols = st.columns(4)
if button_cols[0].button("+ $1,000", use_container_width=True):
    st.session_state.total_invested += 1000.0
    st.session_state.portfolio_value += 1000.0
    st.rerun()
if button_cols[1].button("+ $5,000", use_container_width=True):
    st.session_state.total_invested += 5000.0
    st.session_state.portfolio_value += 5000.0
    st.rerun()
if button_cols[2].button("+ $10,000", use_container_width=True):
    st.session_state.total_invested += 10000.0
    st.session_state.portfolio_value += 10000.0
    st.rerun()
if button_cols[3].button("+ $32,000", use_container_width=True):
    st.session_state.total_invested += 32000.0
    st.session_state.portfolio_value += 32000.0
    st.session_state.cash_sweep += 32000.0
    st.rerun()

edit_cols = st.columns(3)
with edit_cols[0]:
    st.session_state.total_invested = st.number_input(
        "Total Invested / Contributions",
        min_value=0.0,
        step=1000.0,
        value=float(st.session_state.total_invested),
        help="Only your deposits and transfers. This is not market growth.",
    )
with edit_cols[1]:
    st.session_state.portfolio_value = st.number_input(
        "Current Portfolio Value",
        min_value=0.0,
        step=1000.0,
        value=float(st.session_state.portfolio_value),
        help="Your real current value, like what Fidelity shows.",
    )
with edit_cols[2]:
    st.session_state.cash_sweep = st.number_input(
        "Cash / Sweep Value",
        min_value=0.0,
        step=500.0,
        value=float(st.session_state.cash_sweep),
        help="Current FDRXX / sweep cash value.",
    )

st.subheader("Portfolio Holdings")

working_df = normalize_dataframe(st.session_state.portfolio_df)

edited_df = st.data_editor(
    working_df,
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    column_config={
        "ticker": st.column_config.TextColumn("Ticker"),
        "target_weight": st.column_config.NumberColumn("Target %", format="%.2f"),
        "annual_yield": st.column_config.NumberColumn("Yield", format="%.4f"),
        "manual_price": st.column_config.NumberColumn("Manual Price", format="$%.2f"),
        "payout_frequency": st.column_config.SelectboxColumn(
            "Payout Frequency",
            options=["monthly", "quarterly", "semiannual", "annual", "none"],
        ),
        "payout_months": st.column_config.TextColumn("Payout Months"),
        "notes": st.column_config.TextColumn("Notes"),
    },
    key="portfolio_editor",
)

portfolio_df = normalize_dataframe(pd.DataFrame(edited_df))
st.session_state.portfolio_df = portfolio_df

tickers = portfolio_df["ticker"].tolist()
live_prices = fetch_live_prices(tickers)

portfolio_df["current_price"] = portfolio_df["ticker"].apply(
    lambda t: 1.0 if str(t).upper() == "FDRXX" else float(live_prices.get(str(t).upper(), 0.0))
)

portfolio_df["current_price"] = portfolio_df.apply(
    lambda row: float(row["manual_price"]) if row["current_price"] <= 0 else float(row["current_price"]),
    axis=1,
)

portfolio_df["current_price"] = portfolio_df["current_price"].replace(0.0, 1.0)

portfolio_value = float(st.session_state.portfolio_value)
cash_sweep = min(float(st.session_state.cash_sweep), portfolio_value)
investable_value = max(portfolio_value - cash_sweep, 0.0)

is_cash = portfolio_df["ticker"].str.upper() == "FDRXX"
non_cash_weight_total = float(portfolio_df.loc[~is_cash, "target_weight"].sum())

def calc_market_value(row):
    if str(row["ticker"]).upper() == "FDRXX":
        return cash_sweep
    if non_cash_weight_total <= 0:
        return 0.0
    return investable_value * float(row["target_weight"]) / non_cash_weight_total

portfolio_df["market_value"] = portfolio_df.apply(calc_market_value, axis=1)
portfolio_df["shares"] = portfolio_df["market_value"] / portfolio_df["current_price"]
portfolio_df["annual_income"] = portfolio_df["market_value"] * portfolio_df["annual_yield"]
portfolio_df["monthly_income"] = portfolio_df["annual_income"] / 12.0
portfolio_df["actual_weight"] = portfolio_df["market_value"] / max(portfolio_value, 1.0) * 100.0
portfolio_df["target_value"] = portfolio_value * portfolio_df["target_weight"] / 100.0
portfolio_df["dollar_gap"] = portfolio_df["target_value"] - portfolio_df["market_value"]

total_value = float(portfolio_df["market_value"].sum())
total_invested = float(st.session_state.total_invested)
true_gain_loss = total_value - total_invested
annual_income_total = float(portfolio_df["annual_income"].sum())
monthly_income_total = annual_income_total / 12.0
goal_progress = 0.0 if GOAL_MONTHLY <= 0 else max(0.0, min(monthly_income_total / GOAL_MONTHLY, 1.0))

metric_cols = st.columns(5)
metric_cols[0].metric("Current Portfolio Value", currency(total_value))
metric_cols[1].metric("Total Invested", currency(total_invested))
metric_cols[2].metric("True Gain / Loss", currency(true_gain_loss))
metric_cols[3].metric("Estimated Monthly Income", currency(monthly_income_total))
metric_cols[4].metric("Cash / Sweep", currency(cash_sweep))

st.subheader("Goal Progress")
st.progress(goal_progress, text=f"{goal_progress * 100:.1f}% of ${GOAL_MONTHLY:,.0f}/month goal")

summary_cols = st.columns(2)

with summary_cols[0]:
    st.markdown("### Portfolio Summary")
    summary_table = portfolio_df[
        [
            "ticker",
            "shares",
            "current_price",
            "market_value",
            "actual_weight",
            "monthly_income",
        ]
    ].copy()
    summary_table.columns = [
        "Ticker",
        "Est. Shares",
        "Current Price",
        "Market Value",
        "Actual %",
        "Monthly Income",
    ]
    st.dataframe(
        summary_table.style.format(
            {
                "Est. Shares": "{:,.4f}",
                "Current Price": "${:,.2f}",
                "Market Value": "${:,.2f}",
                "Actual %": "{:,.2f}%",
                "Monthly Income": "${:,.2f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

with summary_cols[1]:
    st.markdown("### Income Breakdown")
    income_table = portfolio_df[["ticker", "annual_income", "monthly_income"]].copy()
    income_table.columns = ["Ticker", "Annual Income", "Monthly Income"]
    st.dataframe(
        income_table.style.format(
            {
                "Annual Income": "${:,.2f}",
                "Monthly Income": "${:,.2f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

schedule_df = monthly_income_schedule(portfolio_df)

schedule_cols = st.columns([1.2, 0.8])
with schedule_cols[0]:
    st.markdown("### Estimated Monthly Dividend Calendar")
    st.bar_chart(schedule_df.set_index("Month"))

with schedule_cols[1]:
    st.markdown("### Monthly Income by Month")
    st.dataframe(
        schedule_df.style.format({"Estimated Income": "${:,.2f}"}),
        use_container_width=True,
        hide_index=True,
    )

st.markdown("### Rebalance Helper")
rebalance_table = portfolio_df[
    ["ticker", "market_value", "actual_weight", "target_weight", "target_value", "dollar_gap"]
].copy()
rebalance_table.columns = [
    "Ticker",
    "Current Value",
    "Actual %",
    "Target %",
    "Target Value",
    "Add / (Trim)",
]
st.dataframe(
    rebalance_table.style.format(
        {
            "Current Value": "${:,.2f}",
            "Actual %": "{:,.2f}%",
            "Target %": "{:,.2f}%",
            "Target Value": "${:,.2f}",
            "Add / (Trim)": "${:,.2f}",
        }
    ),
    use_container_width=True,
    hide_index=True,
)

with st.expander("Important Notes"):
    st.write(
        """
- This version keeps the full dashboard layout, but fixes the inflated math.
- Position sizing is based on **Current Portfolio Value** and your **Target %** weights.
- **Est. Shares** are calculated for display only, so fake hardcoded share counts do not blow up the total.
- **Cash / Sweep** is entered separately and held as FDRXX at $1.00.
- **Total Invested** should only change when you add your own money.
- Live prices come from Yahoo Finance when available. If live prices fail, the app uses **Manual Price**.
        """
    )
