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

DEFAULT_COLUMNS = [
    "ticker",
    "qty",
    "avg_cost",
    "manual_price",
    "target_weight",
    "annual_yield",
    "payout_frequency",
    "payout_months",
    "notes",
]

DEFAULT_ROWS = [
    ["AIPI", 668.196, 34.05, 33.79, 5.0, 0.124, "monthly", "all", ""],
    ["CHPY", 436.770, 60.2043356916, 61.01, 6.0, 0.050, "monthly", "all", "Basis inferred from value and G/L"],
    ["DIVO", 857.354, 44.73, 45.53, 10.0, 0.053, "monthly", "all", ""],
    ["FDRXX", 18690.50, 1.00, 1.00, 7.0, 0.045, "monthly", "all", "Cash / sweep"],
    ["FEPI", 662.641, 40.37, 41.11, 7.0, 0.118, "monthly", "all", ""],
    ["GDXY", 2698.805, 13.12, 14.58, 15.0, 0.165, "monthly", "all", ""],
    ["IAU", 141.249, 83.54, 89.56, 4.0, 0.000, "none", "none", ""],
    ["IWMI", 247.328, 47.71, 49.51, 4.0, 0.080, "monthly", "all", ""],
    ["IYRI", 314.264, 46.93, 48.84, 4.0, 0.037, "quarterly", "3,6,9,12", ""],
    ["MLPI", 206.257, 57.21, 56.13, 4.0, 0.086, "quarterly", "3,6,9,12", ""],
    ["QQQI", 509.798, 50.31, 51.94, 10.0, 0.053, "monthly", "all", ""],
    ["SPYI", 895.295, 49.43, 51.11, 12.0, 0.085, "monthly", "all", ""],
    ["SVOL", 1338.302, 15.43, 15.75, 6.0, 0.122, "monthly", "all", ""],
    ["TLTW", 927.268, 22.27, 22.48, 6.0, 0.089, "monthly", "all", ""],
]

MONTH_NAME_MAP = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
}

SAFETY_MIN_NON_CASH_ROWS = 5


def make_default_df() -> pd.DataFrame:
    return pd.DataFrame(DEFAULT_ROWS, columns=DEFAULT_COLUMNS)


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

    numeric_cols = ["qty", "avg_cost", "manual_price", "target_weight", "annual_yield"]
    for col in numeric_cols:
        df[col] = clean_numeric(df[col], 0.0)

    df["ticker"] = df["ticker"].str.upper().str.strip()
    df = df[df["ticker"] != ""].reset_index(drop=True)

    return df


def holdings_cost_basis(df: pd.DataFrame) -> float:
    return float((df["qty"] * df["avg_cost"]).sum())


def non_cash_row_count(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    return int((df["ticker"].str.upper() != "FDRXX").sum())


def protect_against_table_collapse(previous_df: pd.DataFrame, candidate_df: pd.DataFrame) -> pd.DataFrame:
    prev_non_cash = non_cash_row_count(previous_df)
    new_non_cash = non_cash_row_count(candidate_df)

    if prev_non_cash >= SAFETY_MIN_NON_CASH_ROWS and new_non_cash == 0:
        st.warning("Table edit looked like it wiped out the holdings and left only cash, so I kept the last good portfolio instead.")
        return previous_df

    if prev_non_cash >= SAFETY_MIN_NON_CASH_ROWS and new_non_cash < max(1, math.ceil(prev_non_cash * 0.4)):
        st.warning("Table edit looked incomplete, so I kept the last good portfolio instead of replacing it with a partial table.")
        return previous_df

    return candidate_df


def ensure_state() -> None:
    if "portfolio_df" not in st.session_state:
        st.session_state.portfolio_df = normalize_dataframe(make_default_df())

    if "last_good_portfolio_df" not in st.session_state:
        st.session_state.last_good_portfolio_df = st.session_state.portfolio_df.copy()

    if "total_contributions" not in st.session_state:
        st.session_state.total_contributions = float(holdings_cost_basis(st.session_state.portfolio_df))


@st.cache_data(ttl=900)
def fetch_live_prices(tickers: tuple[str, ...]) -> Dict[str, float]:
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

        if annual_income <= 0 or frequency == "none":
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
st.caption("Math fixed so cash is cash, cost basis is cost basis, and gains/losses are not mixed with deposits.")

top_cols = st.columns([3, 1, 1])
with top_cols[1]:
    if st.button("Reset Table to Default", use_container_width=True):
        default_df = normalize_dataframe(make_default_df())
        st.session_state.portfolio_df = default_df
        st.session_state.last_good_portfolio_df = default_df.copy()
        st.session_state.total_contributions = float(holdings_cost_basis(default_df))
        st.rerun()
with top_cols[2]:
    if st.button("Restore Last Good Table", use_container_width=True):
        st.session_state.portfolio_df = st.session_state.last_good_portfolio_df.copy()
        st.rerun()

st.subheader("Add New Money")
button_cols = st.columns(4)


def add_cash(amount: float) -> None:
    mask = st.session_state.portfolio_df["ticker"].str.upper() == "FDRXX"
    if mask.any():
        st.session_state.portfolio_df.loc[mask, "qty"] += float(amount)
    else:
        new_row = pd.DataFrame(
            [["FDRXX", float(amount), 1.0, 1.0, 0.0, 0.045, "monthly", "all", "Cash / sweep"]],
            columns=DEFAULT_COLUMNS,
        )
        st.session_state.portfolio_df = pd.concat([st.session_state.portfolio_df, new_row], ignore_index=True)

    st.session_state.total_contributions += float(amount)


if button_cols[0].button("+ $1,000", use_container_width=True):
    add_cash(1000.0)
    st.rerun()

if button_cols[1].button("+ $5,000", use_container_width=True):
    add_cash(5000.0)
    st.rerun()

if button_cols[2].button("+ $10,000", use_container_width=True):
    add_cash(10000.0)
    st.rerun()

if button_cols[3].button("+ $32,000", use_container_width=True):
    add_cash(32000.0)
    st.rerun()

edit_cols = st.columns([1, 1])

with edit_cols[0]:
    st.session_state.total_contributions = st.number_input(
        "Total Contributions / Deposits",
        min_value=0.0,
        step=1000.0,
        value=float(st.session_state.total_contributions),
        help="Tracks fresh money added. This is separate from invested cost basis.",
    )

with edit_cols[1]:
    custom_add = st.number_input(
        "Custom cash deposit to FDRXX",
        min_value=0.0,
        step=500.0,
        value=0.0,
        help="Adds fresh cash to FDRXX and increases total contributions by the same amount.",
    )
    if st.button("Add Custom Deposit", use_container_width=True):
        if custom_add > 0:
            add_cash(float(custom_add))
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
        "qty": st.column_config.NumberColumn("Qty / Shares", format="%.3f"),
        "avg_cost": st.column_config.NumberColumn("Avg Cost", format="$%.2f"),
        "manual_price": st.column_config.NumberColumn("Manual Price", format="$%.2f"),
        "target_weight": st.column_config.NumberColumn("Target %", format="%.2f"),
        "annual_yield": st.column_config.NumberColumn("Annual Yield", format="%.4f"),
        "payout_frequency": st.column_config.SelectboxColumn(
            "Payout Frequency",
            options=["monthly", "quarterly", "semiannual", "annual", "none"],
        ),
        "payout_months": st.column_config.TextColumn("Payout Months"),
        "notes": st.column_config.TextColumn("Notes"),
    },
    key="portfolio_editor",
)

candidate_df = normalize_dataframe(pd.DataFrame(edited_df))
portfolio_df = protect_against_table_collapse(st.session_state.last_good_portfolio_df, candidate_df)
st.session_state.portfolio_df = portfolio_df.copy()

if non_cash_row_count(portfolio_df) >= SAFETY_MIN_NON_CASH_ROWS:
    st.session_state.last_good_portfolio_df = portfolio_df.copy()

tickers = portfolio_df["ticker"].tolist()
live_prices = fetch_live_prices(tuple(tickers))

portfolio_df["current_price"] = portfolio_df["ticker"].apply(
    lambda t: 1.0 if str(t).upper() == "FDRXX" else float(live_prices.get(str(t).upper(), 0.0))
)
portfolio_df["current_price"] = portfolio_df.apply(
    lambda row: float(row["manual_price"]) if float(row["current_price"]) <= 0 else float(row["current_price"]),
    axis=1,
)
portfolio_df["current_price"] = portfolio_df["current_price"].replace(0.0, 1.0)

portfolio_df["market_value"] = portfolio_df["qty"] * portfolio_df["current_price"]
portfolio_df["cost_basis_total"] = portfolio_df["qty"] * portfolio_df["avg_cost"]
portfolio_df["position_gain_loss"] = portfolio_df["market_value"] - portfolio_df["cost_basis_total"]
portfolio_df["actual_weight"] = 0.0
portfolio_df["annual_income"] = portfolio_df["market_value"] * portfolio_df["annual_yield"]
portfolio_df["monthly_income"] = portfolio_df["annual_income"] / 12.0

total_value = float(portfolio_df["market_value"].sum())
invested_cost_basis = float(portfolio_df["cost_basis_total"].sum())
holdings_cost_basis_ex_cash = float(
    portfolio_df.loc[portfolio_df["ticker"].str.upper() != "FDRXX", "cost_basis_total"].sum()
)
available_cash = float(portfolio_df.loc[portfolio_df["ticker"].str.upper() == "FDRXX", "market_value"].sum())
gain_loss_vs_basis = total_value - invested_cost_basis
tracked_position_gl_ex_cash = float(
    portfolio_df.loc[portfolio_df["ticker"].str.upper() != "FDRXX", "position_gain_loss"].sum()
)
total_contributions = float(st.session_state.total_contributions)
net_vs_contributions = total_value - total_contributions
annual_income_total = float(portfolio_df["annual_income"].sum())
monthly_income_total = annual_income_total / 12.0
goal_progress = 0.0 if GOAL_MONTHLY <= 0 else max(0.0, min(monthly_income_total / GOAL_MONTHLY, 1.0))

if total_value > 0:
    portfolio_df["actual_weight"] = portfolio_df["market_value"] / total_value * 100.0

portfolio_df["target_value"] = total_value * portfolio_df["target_weight"] / 100.0
portfolio_df["dollar_gap"] = portfolio_df["target_value"] - portfolio_df["market_value"]

metric_cols = st.columns(4)
metric_cols[0].metric("Portfolio Value", currency(total_value))
metric_cols[1].metric("Invested Cost Basis", currency(invested_cost_basis))
metric_cols[2].metric("Gain / Loss vs Basis", currency(gain_loss_vs_basis))
metric_cols[3].metric("Available Cash (FDRXX)", currency(available_cash))

metric_cols_2 = st.columns(4)
metric_cols_2[0].metric("Estimated Monthly Income", currency(monthly_income_total))
metric_cols_2[1].metric("Estimated Annual Income", currency(annual_income_total))
metric_cols_2[2].metric("Holdings Cost Basis", currency(holdings_cost_basis_ex_cash))
metric_cols_2[3].metric("Income Goal Progress", f"{goal_progress * 100:.1f}%")

with st.expander("Contribution Tracking"):
    tracking_cols = st.columns(3)
    tracking_cols[0].metric("Total Contributions / Deposits", currency(total_contributions))
    tracking_cols[1].metric("Net vs Contributions", currency(net_vs_contributions))
    tracking_cols[2].metric("Position Gain / Loss (ex cash)", currency(tracked_position_gl_ex_cash))

st.subheader("Goal Progress")
st.progress(goal_progress, text=f"{goal_progress * 100:.1f}% of ${GOAL_MONTHLY:,.0f}/month goal")

summary_cols = st.columns(2)

with summary_cols[0]:
    st.markdown("### Portfolio Summary")
    summary_table = portfolio_df[
        [
            "ticker",
            "qty",
            "avg_cost",
            "current_price",
            "market_value",
            "cost_basis_total",
            "position_gain_loss",
            "actual_weight",
        ]
    ].copy()
    summary_table.columns = [
        "Ticker",
        "Qty / Shares",
        "Avg Cost",
        "Current Price",
        "Market Value",
        "Cost Basis",
        "Position G/L",
        "Actual %",
    ]
    st.dataframe(
        summary_table.style.format(
            {
                "Qty / Shares": "{:,.3f}",
                "Avg Cost": "${:,.2f}",
                "Current Price": "${:,.2f}",
                "Market Value": "${:,.2f}",
                "Cost Basis": "${:,.2f}",
                "Position G/L": "${:,.2f}",
                "Actual %": "{:,.2f}%",
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
- Portfolio Value now uses every row in the table, not just FDRXX cash.
- Invested Cost Basis now comes from the table's actual cost basis totals, not from Total Contributions / Deposits.
- Gain / Loss vs Basis is now Portfolio Value minus Invested Cost Basis.
- Available Cash (FDRXX) is shown separately so cash does not get mislabeled as a loss.
- Holdings Cost Basis excludes FDRXX cash and shows only the non-cash positions.
- Total Contributions / Deposits is still tracked, but it no longer overwrites basis math.
- If the editor tries to collapse the portfolio into a partial table on mobile, the app keeps the last good table instead.
- Live prices come from Yahoo Finance when available. If a live price fails, the app uses Manual Price.
        """
    )
