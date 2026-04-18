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
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
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
    return f"${float(value):,.2f}"


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
    df["payout_frequency"] = df["payout_frequency"].str.lower().str.strip()
    df["qty"] = df["qty"].clip(lower=0.0)
    df["avg_cost"] = df["avg_cost"].clip(lower=0.0)
    df["manual_price"] = df["manual_price"].clip(lower=0.0)
    df["target_weight"] = df["target_weight"].clip(lower=0.0)
    df["annual_yield"] = df["annual_yield"].clip(lower=0.0)

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
        df.loc[idx, "manual_price"] = 1.00
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

    if "custom_add" not in st.session_state:
        st.session_state.custom_add = 0.0


def fetch_live_prices(tickers: List[str]) -> Dict[str, float]:
    prices: Dict[str, float] = {}

    if not tickers or yf is None:
        return prices

    symbols = [str(t).upper().strip() for t in tickers if str(t).upper().strip() and str(t).upper().strip() != "FDRXX"]
    symbols = list(dict.fromkeys(symbols))
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
            try:
                close_series = history["Close"].dropna()
                if len(symbols) == 1 and not close_series.empty:
                    prices[symbols[0]] = float(close_series.iloc[-1])
            except Exception:
                pass
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
    ticker = str(ticker).upper().strip()
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

    target_mask = df["ticker"].str.upper() == target_ticker
    if not target_mask.any():
        return f"{target_ticker} is not in the holdings table yet. Add it there first, then deploy cash."

    price = get_live_or_manual_price(df, target_ticker, live_prices)
    if price <= 0:
        return f"Could not determine a valid price for {target_ticker}."

    shares_to_buy = amount / price
    if shares_to_buy <= 0:
        return "Deploy would result in an invalid share quantity."

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


def build_analytics(df: pd.DataFrame, live_prices: Dict[str, float]) -> pd.DataFrame:
    df = ensure_fdrxx_row(normalize_dataframe(df.copy()))

    df["current_price"] = df["ticker"].apply(lambda t: get_live_or_manual_price(df, str(t), live_prices))
    df["current_price"] = clean_numeric(df["current_price"], 1.0).replace(0.0, 1.0)

    df["market_value"] = df["qty"] * df["current_price"]
    df["cost_basis_total"] = df["qty"] * df["avg_cost"]

    df["position_gain_loss"] = df.apply(
        lambda row: 0.0 if str(row["ticker"]).upper() == "FDRXX" else float(row["market_value"] - row["cost_basis_total"]),
        axis=1,
    )

    total_value = float(df["market_value"].sum())
    if total_value > 0:
        df["actual_weight"] = df["market_value"] / total_value * 100.0
    else:
        df["actual_weight"] = 0.0

    df["income_eligible"] = df["ticker"].apply(is_income_position)

    df["annual_income_actual"] = df.apply(
        lambda row: float(row["market_value"] * row["annual_yield"]) if bool(row["income_eligible"]) else 0.0,
        axis=1,
    )
    df["annual_income_realistic"] = df.apply(
        lambda row: float(row["annual_income_actual"]) * get_realistic_multiplier(str(row["ticker"])),
        axis=1,
    )
    df["annual_income_safe"] = df.apply(
        lambda row: float(row["annual_income_actual"]) * get_safe_multiplier(str(row["ticker"])),
        axis=1,
    )
    df["monthly_income_actual"] = df["annual_income_actual"] / 12.0
    df["monthly_income_realistic"] = df["annual_income_realistic"] / 12.0
    df["monthly_income_safe"] = df["annual_income_safe"] / 12.0

    df["target_value"] = total_value * df["target_weight"] / 100.0
    df["dollar_gap"] = df["target_value"] - df["market_value"]

    return df


ensure_state()

st.title("💵 Retirement Paycheck Dashboard")
st.caption(
    "Full dashboard locked to real position quantities, basis, cash, position gain/loss logic, income tiers, cash deployment workflow, and tighter contribution tracking."
)

header_cols = st.columns([3, 1])
with header_cols[1]:
    if st.button("Reset Table to Default", use_container_width=True):
        st.session_state.portfolio_df = ensure_fdrxx_row(make_default_df())
        st.session_state.total_contributions = float(DEFAULT_TOTAL_CONTRIBUTIONS)
        st.session_state.deploy_amount = 0.0
        st.session_state.deploy_ticker = "SPYI"
        st.session_state.custom_add = 0.0
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
portfolio_df = build_analytics(portfolio_df, live_prices)

cash_mask = portfolio_df["ticker"].str.upper() == "FDRXX"
invested_mask = ~cash_mask

total_value = float(portfolio_df["market_value"].sum())
cash_sweep = float(portfolio_df.loc[cash_mask, "market_value"].sum())
invested_market_value = float(portfolio_df.loc[invested_mask, "market_value"].sum())
cash_invested_basis = float(portfolio_df.loc[invested_mask, "cost_basis_total"].sum())
total_cost_basis_all = float(portfolio_df["cost_basis_total"].sum())
tracked_position_gl = float(portfolio_df["position_gain_loss"].sum())
portfolio_total_gl = total_value - total_cost_basis_all

annual_income_actual_total = float(portfolio_df["annual_income_actual"].sum())
annual_income_realistic_total = float(portfolio_df["annual_income_realistic"].sum())
annual_income_safe_total = float(portfolio_df["annual_income_safe"].sum())

monthly_income_actual_total = annual_income_actual_total / 12.0
monthly_income_realistic_total = annual_income_realistic_total / 12.0
monthly_income_safe_total = annual_income_safe_total / 12.0

goal_progress = 0.0
if GOAL_MONTHLY > 0:
    goal_progress = max(0.0, min(monthly_income_realistic_total / GOAL_MONTHLY, 1.0))

st.subheader("Contribution & Cash Controls")

control_cols = st.columns([1.15, 1.05, 0.8, 0.8])
with control_cols[0]:
    manual_total_contributions = st.number_input(
        "Total Contributions / Deposits",
        min_value=0.0,
        step=1000.0,
        value=float(st.session_state.total_contributions),
        help="Manual total money added to this account setup. Use the sync button if you want it to match the table's total cost basis exactly.",
    )
    st.session_state.total_contributions = float(manual_total_contributions)

with control_cols[1]:
    custom_add = st.number_input(
        "Custom cash deposit to FDRXX",
        min_value=0.0,
        step=500.0,
        value=float(st.session_state.custom_add),
        help="Adds fresh cash to FDRXX and increases Total Contributions by the same amount.",
    )
    st.session_state.custom_add = float(custom_add)
    if st.button("Add Custom Deposit", use_container_width=True):
        if custom_add > 0:
            add_cash_to_fdrxx(float(custom_add))
            st.session_state.custom_add = 0.0
            st.rerun()

with control_cols[2]:
    st.metric("Holdings Cost Basis", currency(total_cost_basis_all))
    if st.button("Sync Contributions to Basis", use_container_width=True):
        st.session_state.total_contributions = float(total_cost_basis_all)
        st.rerun()

with control_cols[3]:
    st.metric("Invested Cost Basis", currency(cash_invested_basis))
    if st.button("Set Contributions = Cash + Invested", use_container_width=True):
        st.session_state.total_contributions = float(cash_sweep + cash_invested_basis)
        st.rerun()

total_contributions = float(st.session_state.total_contributions)
net_vs_contributions = total_value - total_contributions
basis_gap_vs_contributions = total_cost_basis_all - total_contributions

st.subheader("Deploy Cash Into a Position")
deployable_tickers = [t for t in portfolio_df["ticker"].tolist() if str(t).upper() != "FDRXX"]
deploy_cols = st.columns([1.25, 1.0, 0.85, 0.9])

with deploy_cols[0]:
    if deployable_tickers:
        default_index = 0
        if st.session_state.deploy_ticker in deployable_tickers:
            default_index = deployable_tickers.index(st.session_state.deploy_ticker)
        st.session_state.deploy_ticker = st.selectbox(
            "Choose ticker to buy",
            options=deployable_tickers,
            index=default_index,
            key="deploy_ticker_select",
        )
    else:
        st.warning("Add at least one investment ticker besides FDRXX.")
        st.session_state.deploy_ticker = ""

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

metric_cols = st.columns(6)
metric_cols[0].metric("Current Portfolio Value", currency(total_value))
metric_cols[1].metric("Cash / Sweep", currency(cash_sweep))
metric_cols[2].metric("Cash Invested", currency(cash_invested_basis))
metric_cols[3].metric("Position Gain / Loss", currency(tracked_position_gl))
metric_cols[4].metric("Total Contributions", currency(total_contributions))
metric_cols[5].metric("Net vs Contributions", currency(net_vs_contributions))

secondary_metric_cols = st.columns(4)
secondary_metric_cols[0].metric("Invested Market Value", currency(invested_market_value))
secondary_metric_cols[1].metric("Portfolio Total Gain/Loss", currency(portfolio_total_gl))
secondary_metric_cols[2].metric("Holdings Basis Gap", currency(basis_gap_vs_contributions))
secondary_metric_cols[3].metric("Cash Not Yet Deployed", currency(cash_sweep))

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
- **Add New Money** sends new deposits into **FDRXX cash first**.
- **Deploy Cash** moves money out of FDRXX and into a chosen ETF, which then increases shares and updates cost basis.
- **Cash Invested** = cost basis of all non-FDRXX positions. This fixes the old confusion between invested money and cash still sitting in sweep.
- **Position Gain / Loss** is the sum of non-cash position gains/losses only, much closer to Fidelity's holding-level logic.
- **Portfolio Total Gain/Loss** = total portfolio value minus total holdings cost basis, including cash.
- **Holdings Cost Basis** is the table-implied basis. If your manual **Total Contributions** should match the holdings exactly, use **Sync Contributions to Basis**.
- **Cash / Sweep** in FDRXX is treated as cash, not profit.
- **FDRXX is excluded from Safe / Realistic / Actual income calculations** so cash does not dilute the portfolio income view.
- **Net vs Contributions** stays separate from **Position Gain / Loss** so deposits do not get mislabeled as market gains.
- **Goal Progress** uses **Realistic Monthly Income**.
- Live prices come from Yahoo Finance when available. If a live price fails, the app uses **Manual Price**.
- If you update any quantity, avg cost, price, target weight, or yield to match Fidelity, the dashboard will recalculate automatically.
        """
    )
