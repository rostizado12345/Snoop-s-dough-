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
CASH_TICKERS = {"FDRXX", "SPAXX"}

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

# Uses the real position quantities / basis values surfaced from Fidelity,
# with CHPY avg cost derived from its shown value and total gain/loss.
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

INCOME_EXCLUDED_TICKERS = {"FDRXX", "SPAXX"}

SAFE_MULTIPLIERS = {
    "AIPI": 0.75,
    "CHPY": 0.80,
    "DIVO": 0.95,
    "FDRXX": 1.00,
    "FEPI": 0.75,
    "GDXY": 0.60,
    "IAU": 1.00,
    "IWMI": 0.75,
    "IYRI": 0.85,
    "MLPI": 0.80,
    "QQQI": 0.80,
    "SPYI": 0.85,
    "SVOL": 0.80,
    "TLTW": 0.85,
}

REALISTIC_MULTIPLIERS = {
    "AIPI": 0.88,
    "CHPY": 0.90,
    "DIVO": 0.98,
    "FDRXX": 1.00,
    "FEPI": 0.88,
    "GDXY": 0.78,
    "IAU": 1.00,
    "IWMI": 0.88,
    "IYRI": 0.92,
    "MLPI": 0.90,
    "QQQI": 0.90,
    "SPYI": 0.92,
    "SVOL": 0.90,
    "TLTW": 0.92,
}


def make_default_df() -> pd.DataFrame:
    return pd.DataFrame(DEFAULT_ROWS, columns=DEFAULT_COLUMNS)


def ensure_state() -> None:
    if "portfolio_df" not in st.session_state:
        st.session_state.portfolio_df = make_default_df()


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


def fetch_live_prices(tickers: List[str]) -> Dict[str, float]:
    prices: Dict[str, float] = {}

    if not tickers or yf is None:
        return prices

    symbols = [t for t in tickers if t and t.upper() not in CASH_TICKERS]
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


def monthly_income_schedule(df: pd.DataFrame, annual_income_column: str) -> pd.DataFrame:
    month_totals = {month: 0.0 for month in range(1, 13)}

    for _, row in df.iterrows():
        annual_income = float(row[annual_income_column])
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

    ordered_months = list(range(1, 13))
    return pd.DataFrame(
        {
            "Month": [MONTH_NAME_MAP[m] for m in ordered_months],
            "Estimated Income": [month_totals[m] for m in ordered_months],
        }
    )


def currency(value: float) -> str:
    return f"${value:,.2f}"


def get_safe_multiplier(ticker: str) -> float:
    return SAFE_MULTIPLIERS.get(str(ticker).upper(), 0.80)


def get_realistic_multiplier(ticker: str) -> float:
    return REALISTIC_MULTIPLIERS.get(str(ticker).upper(), 0.90)


def is_income_position(ticker: str) -> bool:
    return str(ticker).upper() not in INCOME_EXCLUDED_TICKERS


def is_cash_ticker(ticker: str) -> bool:
    return str(ticker).upper() in CASH_TICKERS


def add_cash_to_sweep(amount: float) -> None:
    if amount <= 0:
        return

    df = normalize_dataframe(st.session_state.portfolio_df)
    mask = df["ticker"].str.upper().isin(CASH_TICKERS)

    if mask.any():
        first_cash_index = df.index[mask][0]
        df.loc[first_cash_index, "qty"] += float(amount)
        df.loc[first_cash_index, "avg_cost"] = 1.0
        df.loc[first_cash_index, "manual_price"] = 1.0
    else:
        new_row = pd.DataFrame(
            [["FDRXX", float(amount), 1.0, 1.0, 0.0, 0.045, "monthly", "all", "Cash / sweep"]],
            columns=DEFAULT_COLUMNS,
        )
        df = pd.concat([df, new_row], ignore_index=True)

    st.session_state.portfolio_df = normalize_dataframe(df)


ensure_state()

st.title("💵 Retirement Paycheck Dashboard")
st.caption("Full dashboard locked to real position quantities, basis, cash, invested cost basis logic, and income tiers.")

header_cols = st.columns([3, 1])
with header_cols[1]:
    if st.button("Reset Table to Default", use_container_width=True):
        st.session_state.portfolio_df = make_default_df()
        st.rerun()

st.subheader("Add New Money")
button_cols = st.columns(4)
if button_cols[0].button("+ $1,000", use_container_width=True):
    add_cash_to_sweep(1000.0)
    st.rerun()
if button_cols[1].button("+ $5,000", use_container_width=True):
    add_cash_to_sweep(5000.0)
    st.rerun()
if button_cols[2].button("+ $10,000", use_container_width=True):
    add_cash_to_sweep(10000.0)
    st.rerun()
if button_cols[3].button("+ $32,000", use_container_width=True):
    add_cash_to_sweep(32000.0)
    st.rerun()

custom_add = st.number_input(
    "Custom cash deposit to FDRXX",
    min_value=0.0,
    step=500.0,
    value=0.0,
    help="Adds fresh cash to FDRXX. Cash stays separate from invested basis.",
)
if st.button("Add Custom Deposit", use_container_width=True):
    if custom_add > 0:
        add_cash_to_sweep(float(custom_add))
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

portfolio_df = normalize_dataframe(pd.DataFrame(edited_df))
st.session_state.portfolio_df = portfolio_df

tickers = portfolio_df["ticker"].tolist()
live_prices = fetch_live_prices(tickers)

portfolio_df["is_cash"] = portfolio_df["ticker"].apply(is_cash_ticker)
portfolio_df["current_price"] = portfolio_df["ticker"].apply(
    lambda t: 1.0 if is_cash_ticker(t) else float(live_prices.get(str(t).upper(), 0.0))
)
portfolio_df["current_price"] = portfolio_df.apply(
    lambda row: float(row["manual_price"]) if row["current_price"] <= 0 else float(row["current_price"]),
    axis=1,
)
portfolio_df.loc[portfolio_df["is_cash"], "current_price"] = 1.0
portfolio_df["current_price"] = portfolio_df["current_price"].replace(0.0, 1.0)

portfolio_df["market_value"] = portfolio_df["qty"] * portfolio_df["current_price"]
portfolio_df["cost_basis_total"] = portfolio_df["qty"] * portfolio_df["avg_cost"]
portfolio_df["position_gain_loss"] = portfolio_df.apply(
    lambda row: 0.0 if bool(row["is_cash"]) else float(row["market_value"] - row["cost_basis_total"]),
    axis=1,
)
portfolio_df["actual_weight"] = 0.0

portfolio_df["income_eligible"] = portfolio_df["ticker"].apply(is_income_position)
portfolio_df["annual_income_actual"] = portfolio_df.apply(
    lambda row: float(row["market_value"] * row["annual_yield"]) if bool(row["income_eligible"]) else 0.0,
    axis=1,
)
portfolio_df["annual_income_realistic"] = portfolio_df.apply(
    lambda row: float(row["annual_income_actual"]) * get_realistic_multiplier(str(row["ticker"])),
    axis=1,
)
portfolio_df["annual_income_safe"] = portfolio_df.apply(
    lambda row: float(row["annual_income_actual"]) * get_safe_multiplier(str(row["ticker"])),
    axis=1,
)
portfolio_df["monthly_income_actual"] = portfolio_df["annual_income_actual"] / 12.0
portfolio_df["monthly_income_realistic"] = portfolio_df["annual_income_realistic"] / 12.0
portfolio_df["monthly_income_safe"] = portfolio_df["annual_income_safe"] / 12.0

total_value = float(portfolio_df["market_value"].sum())
if total_value > 0:
    portfolio_df["actual_weight"] = portfolio_df["market_value"] / total_value * 100.0

cash_sweep = float(portfolio_df.loc[portfolio_df["is_cash"], "market_value"].sum())
cash_basis = float(portfolio_df.loc[portfolio_df["is_cash"], "cost_basis_total"].sum())
invested_cost_basis = float(portfolio_df.loc[~portfolio_df["is_cash"], "cost_basis_total"].sum())
invested_market_value = float(portfolio_df.loc[~portfolio_df["is_cash"], "market_value"].sum())
invested_gain_loss = float(portfolio_df.loc[~portfolio_df["is_cash"], "position_gain_loss"].sum())
holdings_cost_basis = float(portfolio_df["cost_basis_total"].sum())
holdings_basis_gap = holdings_cost_basis - invested_cost_basis
cash_not_yet_deployed = cash_sweep
portfolio_total_gain_loss = total_value - holdings_cost_basis

annual_income_actual_total = float(portfolio_df["annual_income_actual"].sum())
annual_income_realistic_total = float(portfolio_df["annual_income_realistic"].sum())
annual_income_safe_total = float(portfolio_df["annual_income_safe"].sum())
monthly_income_actual_total = annual_income_actual_total / 12.0
monthly_income_realistic_total = annual_income_realistic_total / 12.0
monthly_income_safe_total = annual_income_safe_total / 12.0
goal_progress = 0.0 if GOAL_MONTHLY <= 0 else max(0.0, min(monthly_income_realistic_total / GOAL_MONTHLY, 1.0))

portfolio_df["target_value"] = total_value * portfolio_df["target_weight"] / 100.0
portfolio_df["dollar_gap"] = portfolio_df["target_value"] - portfolio_df["market_value"]

metric_cols = st.columns(5)
metric_cols[0].metric("Current Portfolio Value", currency(total_value))
metric_cols[1].metric("Cash / Sweep", currency(cash_sweep))
metric_cols[2].metric("Invested Cost Basis", currency(invested_cost_basis))
metric_cols[3].metric("Invested Gain / Loss", currency(invested_gain_loss))
metric_cols[4].metric("Invested Market Value", currency(invested_market_value))

secondary_metric_cols = st.columns(4)
secondary_metric_cols[0].metric("Holdings Cost Basis", currency(holdings_cost_basis))
secondary_metric_cols[1].metric("Portfolio Total Gain/Loss", currency(portfolio_total_gain_loss))
secondary_metric_cols[2].metric("Holdings Basis Gap", currency(holdings_basis_gap))
secondary_metric_cols[3].metric("Cash Not Yet Deployed", currency(cash_not_yet_deployed))

income_metric_cols = st.columns(3)
income_metric_cols[0].metric("Safe Monthly Income", currency(monthly_income_safe_total))
income_metric_cols[1].metric("Realistic Monthly Income", currency(monthly_income_realistic_total))
income_metric_cols[2].metric("Actual Monthly Income", currency(monthly_income_actual_total))

st.subheader("Goal Progress")
st.progress(goal_progress, text=f"{goal_progress * 100:.1f}% of ${GOAL_MONTHLY:,.0f}/month goal (using Realistic income)")

summary_cols = st.columns(2)

with summary_cols[0]:
    st.markdown("### Portfolio Summary")
    summary_table = portfolio_df[
        [
            "ticker",
            "qty",
            "avg_cost",
            "current_price",
            "cost_basis_total",
            "market_value",
            "position_gain_loss",
            "actual_weight",
        ]
    ].copy()
    summary_table.columns = [
        "Ticker",
        "Qty / Shares",
        "Avg Cost",
        "Current Price",
        "Cost Basis",
        "Market Value",
        "Position G/L",
        "Actual %",
    ]
    st.dataframe(
        summary_table.style.format(
            {
                "Qty / Shares": "{:,.3f}",
                "Avg Cost": "${:,.2f}",
                "Current Price": "${:,.2f}",
                "Cost Basis": "${:,.2f}",
                "Market Value": "${:,.2f}",
                "Position G/L": "${:,.2f}",
                "Actual %": "{:,.2f}%",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

with summary_cols[1]:
    st.markdown("### Income Breakdown")
    income_table = portfolio_df[
        [
            "ticker",
            "annual_income_safe",
            "annual_income_realistic",
            "annual_income_actual",
            "monthly_income_safe",
            "monthly_income_realistic",
            "monthly_income_actual",
        ]
    ].copy()
    income_table.columns = [
        "Ticker",
        "Safe Annual",
        "Realistic Annual",
        "Actual Annual",
        "Safe Monthly",
        "Realistic Monthly",
        "Actual Monthly",
    ]
    st.dataframe(
        income_table.style.format(
            {
                "Safe Annual": "${:,.2f}",
                "Realistic Annual": "${:,.2f}",
                "Actual Annual": "${:,.2f}",
                "Safe Monthly": "${:,.2f}",
                "Realistic Monthly": "${:,.2f}",
                "Actual Monthly": "${:,.2f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

schedule_actual_df = monthly_income_schedule(portfolio_df, "annual_income_actual")
schedule_realistic_df = monthly_income_schedule(portfolio_df, "annual_income_realistic")
schedule_safe_df = monthly_income_schedule(portfolio_df, "annual_income_safe")

schedule_cols = st.columns([1.2, 0.8])
with schedule_cols[0]:
    st.markdown("### Realistic Monthly Dividend Calendar")
    st.bar_chart(schedule_realistic_df.set_index("Month"))
with schedule_cols[1]:
    st.markdown("### Monthly Income by Month")
    schedule_compare_df = pd.DataFrame(
        {
            "Month": schedule_realistic_df["Month"],
            "Safe": schedule_safe_df["Estimated Income"],
            "Realistic": schedule_realistic_df["Estimated Income"],
            "Actual": schedule_actual_df["Estimated Income"],
        }
    )
    st.dataframe(
        schedule_compare_df.style.format(
            {
                "Safe": "${:,.2f}",
                "Realistic": "${:,.2f}",
                "Actual": "${:,.2f}",
            }
        ),
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
- **Invested Cost Basis** now tracks invested positions only.
- **Cash / Sweep** in FDRXX or SPAXX stays separate and is not counted as invested basis.
- **Holdings Cost Basis** = invested cost basis + cash basis.
- **Invested Gain / Loss** is calculated only from non-cash positions, much closer to Fidelity's logic.
- **Portfolio Total Gain/Loss** includes the full account, including cash.
- **FDRXX / SPAXX are excluded from Safe / Realistic / Actual income calculations** so cash does not dilute the portfolio income view.
- **Safe / Realistic / Actual** income tiers are shown separately so the app does not default to one optimistic number.
- **Goal Progress** now uses **Realistic Monthly Income**.
- Live prices come from Yahoo Finance when available. If a live price fails, the app uses **Manual Price**.
- If you update any quantity, avg cost, price, or yield to match Fidelity, the income and gain/loss math will update automatically.
        """
    )
