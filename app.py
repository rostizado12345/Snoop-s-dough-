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
DEFAULT_TOTAL_CONTRIBUTIONS = 327000.0

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
    ["FDRXX", 50690.280, 1.00, 1.00, 7.0, 0.045, "monthly", "all", "Cash / sweep"],
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

INCOME_EXCLUDED_TICKERS = {"FDRXX"}

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


def currency(value: float) -> str:
    return f"${value:,.2f}"


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


def ensure_fdrxx_row(df: pd.DataFrame) -> pd.DataFrame:
    df = normalize_dataframe(df)
    mask = df["ticker"].str.upper() == "FDRXX"
    if not mask.any():
        new_row = pd.DataFrame(
            [["FDRXX", 0.0, 1.00, 1.00, 7.0, 0.045, "monthly", "all", "Cash / sweep"]],
            columns=DEFAULT_COLUMNS,
        )
        df = pd.concat([df, new_row], ignore_index=True)
    else:
        idx = df.index[mask][0]
        if float(df.loc[idx, "manual_price"]) <= 0:
            df.loc[idx, "manual_price"] = 1.00
        if float(df.loc[idx, "avg_cost"]) <= 0:
            df.loc[idx, "avg_cost"] = 1.00
        if str(df.loc[idx, "payout_frequency"]).strip() == "":
            df.loc[idx, "payout_frequency"] = "monthly"
        if str(df.loc[idx, "payout_months"]).strip() == "":
            df.loc[idx, "payout_months"] = "all"
    return normalize_dataframe(df)


def ensure_state() -> None:
    if "portfolio_df" not in st.session_state:
        st.session_state.portfolio_df = ensure_fdrxx_row(make_default_df())
    else:
        st.session_state.portfolio_df = ensure_fdrxx_row(st.session_state.portfolio_df)

    if "total_contributions" not in st.session_state:
        st.session_state.total_contributions = float(DEFAULT_TOTAL_CONTRIBUTIONS)

    if "deploy_amount" not in st.session_state:
        st.session_state.deploy_amount = 0.0

    if "deploy_ticker" not in st.session_state:
        st.session_state.deploy_ticker = "SPYI"


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


def get_safe_multiplier(ticker: str) -> float:
    return SAFE_MULTIPLIERS.get(str(ticker).upper(), 0.80)


def get_realistic_multiplier(ticker: str) -> float:
    return REALISTIC_MULTIPLIERS.get(str(ticker).upper(), 0.90)


def is_income_position(ticker: str) -> bool:
    return str(ticker).upper() not in INCOME_EXCLUDED_TICKERS


def get_live_or_manual_price(df: pd.DataFrame, ticker: str, live_prices: Dict[str, float]) -> float:
    ticker = str(ticker).upper()
    if ticker == "FDRXX":
        return 1.0

    row_match = df[df["ticker"].str.upper() == ticker]
    manual_price = 0.0
    if not row_match.empty:
        manual_price = float(row_match.iloc[0]["manual_price"])

    live_price = float(live_prices.get(ticker, 0.0))
    if live_price > 0:
        return live_price
    if manual_price > 0:
        return manual_price
    return 1.0


def add_cash_to_fdrxx(amount: float) -> None:
    amount = float(amount)
    if amount <= 0:
        return

    df = ensure_fdrxx_row(st.session_state.portfolio_df.copy())
    mask = df["ticker"].str.upper() == "FDRXX"
    df.loc[mask, "qty"] = clean_numeric(df.loc[mask, "qty"], 0.0) + amount
    st.session_state.portfolio_df = ensure_fdrxx_row(df)
    st.session_state.total_contributions = float(st.session_state.total_contributions) + amount


def deploy_cash_to_ticker(target_ticker: str, amount: float, live_prices: Dict[str, float]) -> str:
    target_ticker = str(target_ticker).upper().strip()
    amount = float(amount)

    if amount <= 0:
        return "Enter a deploy amount greater than zero."
    if target_ticker in {"", "FDRXX"}:
        return "Pick an investment ticker, not FDRXX cash."

    df = ensure_fdrxx_row(st.session_state.portfolio_df.copy())
    fdrxx_mask = df["ticker"].str.upper() == "FDRXX"
    available_cash = float(df.loc[fdrxx_mask, "qty"].sum())

    if amount > available_cash + 1e-9:
        return f"Not enough cash in FDRXX. Available cash is {currency(available_cash)}."

    price = get_live_or_manual_price(df, target_ticker, live_prices)
    if price <= 0:
        return f"Could not determine a valid price for {target_ticker}."

    shares_to_buy = amount / price

    target_mask = df["ticker"].str.upper() == target_ticker
    if not target_mask.any():
        return f"{target_ticker} is not in the holdings table yet. Add it there first, then deploy cash."

    idx = df.index[target_mask][0]
    old_qty = float(df.loc[idx, "qty"])
    old_avg_cost = float(df.loc[idx, "avg_cost"])

    new_qty = old_qty + shares_to_buy
    if new_qty <= 0:
        return "Deploy would result in an invalid share quantity."

    if old_qty > 0:
        new_avg_cost = ((old_qty * old_avg_cost) + amount) / new_qty
    else:
        new_avg_cost = price

    fdrxx_idx = df.index[fdrxx_mask][0]
    df.loc[fdrxx_idx, "qty"] = max(0.0, float(df.loc[fdrxx_idx, "qty"]) - amount)
    df.loc[idx, "qty"] = new_qty
    df.loc[idx, "avg_cost"] = new_avg_cost

    st.session_state.portfolio_df = ensure_fdrxx_row(df)
    return f"Deployed {currency(amount)} from FDRXX into {target_ticker} at about {currency(price)} per share."


ensure_state()

st.title("💵 Retirement Paycheck Dashboard")
st.caption("Full dashboard locked to real position quantities, basis, cash, position gain/loss logic, income tiers, and cash deployment workflow.")

header_cols = st.columns([3, 1])
with header_cols[1]:
    if st.button("Reset Table to Default", use_container_width=True):
        st.session_state.portfolio_df = ensure_fdrxx_row(make_default_df())
        st.session_state.total_contributions = float(DEFAULT_TOTAL_CONTRIBUTIONS)
        st.session_state.deploy_amount = 0.0
        st.session_state.deploy_ticker = "SPYI"
        st.rerun()

st.subheader("Add New Money")
button_cols = st.columns(4)
if button_cols[0].button("+ $1,000", use_container_width=True):
    add_cash_to_fdrxx(1000.0)
    st.rerun()
if button_cols[1].button("+ $5,000", use_container_width=True):
    add_cash_to_fdrxx(5000.0)
    st.rerun()
if button_cols[2].button("+ $10,000", use_container_width=True):
    add_cash_to_fdrxx(10000.0)
    st.rerun()
if button_cols[3].button("+ $32,000", use_container_width=True):
    add_cash_to_fdrxx(32000.0)
    st.rerun()

edit_cols = st.columns([1, 1])
with edit_cols[0]:
    st.session_state.total_contributions = st.number_input(
        "Total Contributions / Deposits",
        min_value=0.0,
        step=1000.0,
        value=float(st.session_state.total_contributions),
        help="Money you moved into this account setup. This is separate from position gain/loss.",
    )
with edit_cols[1]:
    custom_add = st.number_input(
        "Custom cash deposit to FDRXX",
        min_value=0.0,
        step=500.0,
        value=0.0,
        help="Adds fresh cash to FDRXX and increases contributions by the same amount.",
    )
    if st.button("Add Custom Deposit", use_container_width=True):
        if custom_add > 0:
            add_cash_to_fdrxx(float(custom_add))
            st.rerun()

st.subheader("Portfolio Holdings")

working_df = ensure_fdrxx_row(normalize_dataframe(st.session_state.portfolio_df))

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

portfolio_df = ensure_fdrxx_row(normalize_dataframe(pd.DataFrame(edited_df)))
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

portfolio_df["market_value"] = portfolio_df["qty"] * portfolio_df["current_price"]
portfolio_df["cost_basis_total"] = portfolio_df["qty"] * portfolio_df["avg_cost"]
portfolio_df["position_gain_loss"] = portfolio_df.apply(
    lambda row: 0.0 if str(row["ticker"]).upper() == "FDRXX" else float(row["market_value"] - row["cost_basis_total"]),
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

tracked_position_gl = float(portfolio_df["position_gain_loss"].sum())
cash_sweep = float(portfolio_df.loc[portfolio_df["ticker"].str.upper() == "FDRXX", "market_value"].sum())
total_contributions = float(st.session_state.total_contributions)
net_vs_contributions = total_value - total_contributions
annual_income_actual_total = float(portfolio_df["annual_income_actual"].sum())
annual_income_realistic_total = float(portfolio_df["annual_income_realistic"].sum())
annual_income_safe_total = float(portfolio_df["annual_income_safe"].sum())
monthly_income_actual_total = annual_income_actual_total / 12.0
monthly_income_realistic_total = annual_income_realistic_total / 12.0
monthly_income_safe_total = annual_income_safe_total / 12.0
goal_progress = 0.0 if GOAL_MONTHLY <= 0 else max(0.0, min(monthly_income_realistic_total / GOAL_MONTHLY, 1.0))

portfolio_df["target_value"] = total_value * portfolio_df["target_weight"] / 100.0
portfolio_df["dollar_gap"] = portfolio_df["target_value"] - portfolio_df["market_value"]

st.subheader("Deploy Cash Into a Position")
deployable_tickers = [t for t in portfolio_df["ticker"].tolist() if str(t).upper() != "FDRXX"]
deploy_cols = st.columns([1.2, 1, 0.9, 0.9])

with deploy_cols[0]:
    default_index = 0
    if st.session_state.deploy_ticker in deployable_tickers:
        default_index = deployable_tickers.index(st.session_state.deploy_ticker)
    st.session_state.deploy_ticker = st.selectbox(
        "Choose ticker to buy",
        options=deployable_tickers,
        index=default_index if deployable_tickers else 0,
        key="deploy_ticker_select",
    )

with deploy_cols[1]:
    st.session_state.deploy_amount = st.number_input(
        "Amount to deploy from FDRXX",
        min_value=0.0,
        step=500.0,
        value=float(st.session_state.deploy_amount),
        key="deploy_amount_input",
    )

with deploy_cols[2]:
    st.metric("Available Cash", currency(cash_sweep))

with deploy_cols[3]:
    st.write("")
    st.write("")
    if st.button("Deploy Cash", use_container_width=True):
        message = deploy_cash_to_ticker(st.session_state.deploy_ticker, st.session_state.deploy_amount, live_prices)
        if message.startswith("Deployed "):
            st.session_state.deploy_amount = 0.0
            st.success(message)
            st.rerun()
        else:
            st.error(message)

metric_cols = st.columns(5)
metric_cols[0].metric("Current Portfolio Value", currency(total_value))
metric_cols[1].metric("Cash / Sweep", currency(cash_sweep))
metric_cols[2].metric("Position Gain / Loss", currency(tracked_position_gl))
metric_cols[3].metric("Total Contributions", currency(total_contributions))
metric_cols[4].metric("Net vs Contributions", currency(net_vs_contributions))

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
        ["ticker", "annual_income_safe", "annual_income_realistic", "annual_income_actual", "monthly_income_safe", "monthly_income_realistic", "monthly_income_actual"]
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
- **Add New Money** now sends new deposits into **FDRXX cash first**.
- **Deploy Cash** moves money out of FDRXX and into a chosen ETF, which then increases shares and income.
- **Position Gain / Loss** is calculated from each holding's own basis, much closer to Fidelity's logic.
- **Cash / Sweep** in FDRXX is treated as cash, not profit.
- **FDRXX is excluded from Safe / Realistic / Actual income calculations** so cash does not dilute the portfolio income view.
- **Total Contributions** tracks money you added to the account.
- **Net vs Contributions** is separate from **Position Gain / Loss** so deposits do not get mislabeled as market gains.
- **Safe / Realistic / Actual** income tiers are shown separately so the app does not default to one optimistic number.
- **Goal Progress** now uses **Realistic Monthly Income**.
- Live prices come from Yahoo Finance when available. If a live price fails, the app uses **Manual Price**.
- If you update any quantity, avg cost, price, or yield to match Fidelity, the income and gain/loss math will update automatically.
        """
    )
