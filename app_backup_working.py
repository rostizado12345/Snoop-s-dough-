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

DEFAULT_COLUMNS = [
    "ticker",
    "shares",
    "cost_basis_per_share",
    "target_weight",
    "annual_income_per_share",
    "manual_price",
    "payout_frequency",
    "payout_months",
    "notes",
]

DEFAULT_ROWS = [
    ["GDXY", 2600.0, 13.25, 15.0, 2.40, 13.50, "monthly", "all", ""],
    ["CHPY", 1100.0, 24.90, 6.0, 1.68, 24.75, "monthly", "all", ""],
    ["FEPI", 650.0, 52.00, 7.0, 6.12, 51.75, "monthly", "all", ""],
    ["QQQI", 1100.0, 18.40, 10.0, 2.28, 18.70, "monthly", "all", ""],
    ["AIPI", 700.0, 38.00, 5.0, 4.20, 38.50, "monthly", "all", ""],
    ["SPYI", 1800.0, 19.80, 12.0, 2.16, 20.10, "monthly", "all", ""],
    ["DIVO", 700.0, 39.50, 10.0, 2.40, 39.90, "monthly", "all", ""],
    ["SVOL", 900.0, 23.00, 6.0, 1.92, 23.45, "monthly", "all", ""],
    ["TLTW", 1200.0, 17.20, 6.0, 1.92, 17.35, "monthly", "all", ""],
    ["IYRI", 500.0, 23.00, 4.0, 1.80, 22.90, "monthly", "all", ""],
    ["IWMI", 700.0, 15.80, 4.0, 1.56, 15.75, "monthly", "all", ""],
    ["IAU", 300.0, 55.00, 4.0, 0.00, 55.20, "none", "none", ""],
    ["MLPI", 700.0, 25.00, 4.0, 2.88, 25.10, "quarterly", "3,6,9,12", ""],
    ["FDRXX", 32000.0, 1.00, 7.0, 0.045, 1.00, "monthly", "all", "Cash / sweep"],
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

    if "invested_amount" not in st.session_state:
        st.session_state.invested_amount = float(DEFAULT_TOTAL_INVESTED)

    if "price_cache" not in st.session_state:
        st.session_state.price_cache = {}


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

    numeric_cols = ["shares", "cost_basis_per_share", "target_weight", "annual_income_per_share", "manual_price"]
    for col in numeric_cols:
        df[col] = clean_numeric(df[col], 0.0)

    df["ticker"] = df["ticker"].str.upper().str.strip()
    df = df[df["ticker"] != ""].reset_index(drop=True)
    return df


def fetch_live_prices(tickers: List[str]) -> Dict[str, float]:
    prices: Dict[str, float] = {}

    if not tickers:
        return prices

    if yf is None:
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


def get_price_for_row(row: pd.Series, live_prices: Dict[str, float]) -> float:
    ticker = str(row["ticker"]).upper().strip()
    manual_price = float(row["manual_price"]) if pd.notna(row["manual_price"]) else 0.0

    if ticker == "FDRXX":
        return 1.0

    live_price = live_prices.get(ticker)
    if live_price is not None and live_price > 0:
        return float(live_price)

    if manual_price > 0:
        return float(manual_price)

    cost_basis = float(row["cost_basis_per_share"]) if pd.notna(row["cost_basis_per_share"]) else 0.0
    return cost_basis


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
        annual_income = float(row["annual_income_per_share"]) * float(row["shares"])
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
st.caption("Live-price estimate with separate tracking for deposits vs. market gains.")

left_header, right_header = st.columns([2, 1])
with right_header:
    if st.button("Reset Portfolio Table to Default", use_container_width=True):
        st.session_state.portfolio_df = make_default_df()
        st.success("Portfolio table reset to default values.")
        st.rerun()

st.subheader("Add New Money")

button_cols = st.columns(4)
if button_cols[0].button("+ $1,000", use_container_width=True):
    st.session_state.invested_amount += 1000.0
    st.rerun()
if button_cols[1].button("+ $5,000", use_container_width=True):
    st.session_state.invested_amount += 5000.0
    st.rerun()
if button_cols[2].button("+ $10,000", use_container_width=True):
    st.session_state.invested_amount += 10000.0
    st.rerun()
if button_cols[3].button("+ $32,000", use_container_width=True):
    st.session_state.invested_amount += 32000.0
    st.rerun()

edit_cols = st.columns([1.2, 1, 1])
with edit_cols[0]:
    st.session_state.invested_amount = st.number_input(
        "Total Invested / Contributions",
        min_value=0.0,
        step=1000.0,
        value=float(st.session_state.invested_amount),
        help="This should only increase when you add your own money. It should not move with market gains.",
    )
with edit_cols[1]:
    custom_add = st.number_input("Custom deposit", min_value=0.0, step=500.0, value=0.0)
with edit_cols[2]:
    st.write("")
    st.write("")
    if st.button("Add Custom Deposit", use_container_width=True):
        if custom_add > 0:
            st.session_state.invested_amount += float(custom_add)
            st.rerun()

st.subheader("Portfolio Holdings")

working_df = normalize_dataframe(st.session_state.portfolio_df)

edited_df = st.data_editor(
    working_df,
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    column_config={
        "ticker": st.column_config.TextColumn("Ticker"),
        "shares": st.column_config.NumberColumn("Shares", format="%.4f"),
        "cost_basis_per_share": st.column_config.NumberColumn("Cost / Share", format="$%.2f"),
        "target_weight": st.column_config.NumberColumn("Target %", format="%.2f"),
        "annual_income_per_share": st.column_config.NumberColumn("Annual Income / Share", format="$%.4f"),
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

portfolio_df["current_price"] = portfolio_df.apply(lambda row: get_price_for_row(row, live_prices), axis=1)
portfolio_df["market_value"] = portfolio_df["shares"] * portfolio_df["current_price"]
portfolio_df["cost_basis_total"] = portfolio_df["shares"] * portfolio_df["cost_basis_per_share"]
portfolio_df["position_gain_loss"] = portfolio_df["market_value"] - portfolio_df["cost_basis_total"]
portfolio_df["annual_income"] = portfolio_df["shares"] * portfolio_df["annual_income_per_share"]
portfolio_df["monthly_income"] = portfolio_df["annual_income"] / 12.0

total_value = float(portfolio_df["market_value"].sum())
total_cost_basis = float(portfolio_df["cost_basis_total"].sum())
total_invested = float(st.session_state.invested_amount)
true_gain_loss = total_value - total_invested
holdings_gain_loss = total_value - total_cost_basis
annual_income_total = float(portfolio_df["annual_income"].sum())
monthly_income_total = annual_income_total / 12.0
goal_progress = 0.0 if GOAL_MONTHLY <= 0 else max(0.0, min(monthly_income_total / GOAL_MONTHLY, 1.0))
cash_value = float(portfolio_df.loc[portfolio_df["ticker"] == "FDRXX", "market_value"].sum())

metric_cols = st.columns(5)
metric_cols[0].metric("Current Portfolio Value", currency(total_value))
metric_cols[1].metric("Total Invested", currency(total_invested))
metric_cols[2].metric("True Gain / Loss", currency(true_gain_loss))
metric_cols[3].metric("Estimated Monthly Income", currency(monthly_income_total))
metric_cols[4].metric("Cash / Sweep", currency(cash_value))

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
            "cost_basis_total",
            "position_gain_loss",
            "monthly_income",
        ]
    ].copy()
    summary_table.columns = [
        "Ticker",
        "Shares",
        "Current Price",
        "Market Value",
        "Cost Basis Total",
        "Gain / Loss",
        "Monthly Income",
    ]
    st.dataframe(
        summary_table.style.format(
            {
                "Shares": "{:,.4f}",
                "Current Price": "${:,.2f}",
                "Market Value": "${:,.2f}",
                "Cost Basis Total": "${:,.2f}",
                "Gain / Loss": "${:,.2f}",
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
portfolio_df["actual_weight"] = portfolio_df["market_value"] / total_value * 100 if total_value > 0 else 0.0
portfolio_df["target_value"] = total_value * portfolio_df["target_weight"] / 100.0
portfolio_df["dollar_gap"] = portfolio_df["target_value"] - portfolio_df["market_value"]

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
- **Total Invested / Contributions** should only change when you add your own money.
- **Current Portfolio Value** moves with the market.
- **True Gain / Loss** = Current Portfolio Value minus Total Invested.
- **FDRXX** is treated like cash at $1.00 per share so it does not look like a fake gain.
- Live prices come from Yahoo Finance when available. If a live price fails, the app falls back to **Manual Price**.
        """
    )
