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
STARTING_INVESTED_COST_BASIS = 359000.0

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

# Keep FDRXX as the cash/sweep row.
# Edit/add rows as needed, but do NOT remove FDRXX unless your sweep changes.
DEFAULT_ROWS = [
    ["FDRXX", 18690.50, 1.00, 1.00, 0.0, 0.048, "monthly", "all", "Cash sweep / available cash"],
    ["SPYI", 0.0, 0.00, 47.00, 12.0, 0.120, "monthly", "all", ""],
    ["DIVO", 0.0, 0.00, 40.00, 10.0, 0.050, "monthly", "all", ""],
    ["QQQI", 0.0, 0.00, 50.00, 10.0, 0.140, "monthly", "all", ""],
    ["SVOL", 0.0, 0.00, 22.00, 6.0, 0.160, "monthly", "all", ""],
    ["FEPI", 0.0, 0.00, 53.00, 7.0, 0.180, "monthly", "all", ""],
    ["AIPI", 0.0, 0.00, 34.00, 5.0, 0.124, "monthly", "all", ""],
    ["CHPY", 0.0, 0.00, 61.00, 6.0, 0.050, "monthly", "all", ""],
    ["GDXY", 0.0, 0.00, 25.00, 15.0, 0.220, "monthly", "all", ""],
    ["TLTW", 0.0, 0.00, 28.00, 7.0, 0.150, "monthly", "all", ""],
    ["IWMI", 0.0, 0.00, 31.00, 4.0, 0.120, "monthly", "all", ""],
    ["IYRI", 0.0, 0.00, 18.00, 5.0, 0.090, "monthly", "all", ""],
    ["MLPI", 0.0, 0.00, 49.00, 4.0, 0.080, "monthly", "all", ""],
    ["IAU", 0.0, 0.00, 58.00, 4.0, 0.000, "monthly", "all", "Gold hedge"],
]

PAYOUT_MONTH_MAP = {
    "monthly": list(range(1, 13)),
    "quarterly_jan": [1, 4, 7, 10],
    "quarterly_feb": [2, 5, 8, 11],
    "quarterly_mar": [3, 6, 9, 12],
    "semi_jan": [1, 7],
    "semi_feb": [2, 8],
    "semi_mar": [3, 9],
    "annual_dec": [12],
    "all": list(range(1, 13)),
}


def build_default_df() -> pd.DataFrame:
    df = pd.DataFrame(DEFAULT_ROWS, columns=DEFAULT_COLUMNS)
    numeric_cols = ["qty", "avg_cost", "manual_price", "target_weight", "annual_yield"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    for col in ["ticker", "payout_frequency", "payout_months", "notes"]:
        df[col] = df[col].astype(str)
    return df


def ensure_state() -> None:
    if "portfolio_df" not in st.session_state:
        st.session_state.portfolio_df = build_default_df()

    if "invested_cost_basis" not in st.session_state:
        st.session_state.invested_cost_basis = float(STARTING_INVESTED_COST_BASIS)

    if "external_cash_log" not in st.session_state:
        st.session_state.external_cash_log = [
            {"date": "Starting baseline", "amount": STARTING_INVESTED_COST_BASIS, "note": "Initial confirmed invested cost basis"}
        ]


def get_live_prices(tickers: List[str]) -> Dict[str, float]:
    prices: Dict[str, float] = {}
    if yf is None:
        return prices

    clean = [t for t in tickers if t and t.upper() != "FDRXX"]
    if not clean:
        return prices

    try:
        data = yf.download(
            tickers=clean,
            period="5d",
            interval="1d",
            auto_adjust=False,
            progress=False,
            group_by="ticker",
            threads=True,
        )
        if data is None or len(data) == 0:
            return prices

        if len(clean) == 1:
            ticker = clean[0]
            close_series = data["Close"] if "Close" in data else None
            if close_series is not None and len(close_series.dropna()) > 0:
                prices[ticker] = float(close_series.dropna().iloc[-1])
            return prices

        for ticker in clean:
            try:
                close_series = data[ticker]["Close"]
                if len(close_series.dropna()) > 0:
                    prices[ticker] = float(close_series.dropna().iloc[-1])
            except Exception:
                continue
    except Exception:
        return prices

    return prices


def apply_prices(df: pd.DataFrame, use_live_prices: bool) -> pd.DataFrame:
    out = df.copy()
    out["price_used"] = out["manual_price"]

    if use_live_prices:
        tickers = out["ticker"].astype(str).str.upper().tolist()
        live_prices = get_live_prices(tickers)
        for idx, row in out.iterrows():
            ticker = str(row["ticker"]).upper().strip()
            if ticker == "FDRXX":
                out.at[idx, "price_used"] = 1.00
            elif ticker in live_prices and live_prices[ticker] > 0:
                out.at[idx, "price_used"] = float(live_prices[ticker])

    out["market_value"] = out["qty"] * out["price_used"]
    out["cost_basis"] = out["qty"] * out["avg_cost"]
    out["annual_income"] = out["market_value"] * out["annual_yield"]
    out["monthly_income"] = out["annual_income"] / 12.0
    return out


def get_cash_row_index(df: pd.DataFrame) -> int:
    matches = df.index[df["ticker"].astype(str).str.upper() == "FDRXX"].tolist()
    if matches:
        return matches[0]

    # If missing, create it.
    new_row = {
        "ticker": "FDRXX",
        "qty": 0.0,
        "avg_cost": 1.0,
        "manual_price": 1.0,
        "target_weight": 0.0,
        "annual_yield": 0.048,
        "payout_frequency": "monthly",
        "payout_months": "all",
        "notes": "Cash sweep / available cash",
    }
    df.loc[len(df)] = new_row
    return int(df.index[-1])


def add_external_cash(amount: float, note: str) -> None:
    if amount <= 0:
        return

    df = st.session_state.portfolio_df.copy()
    cash_idx = get_cash_row_index(df)

    df.at[cash_idx, "qty"] = float(df.at[cash_idx, "qty"]) + float(amount)
    df.at[cash_idx, "avg_cost"] = 1.0
    df.at[cash_idx, "manual_price"] = 1.0

    st.session_state.portfolio_df = df
    st.session_state.invested_cost_basis = float(st.session_state.invested_cost_basis) + float(amount)
    st.session_state.external_cash_log.append(
        {"date": pd.Timestamp.today().strftime("%Y-%m-%d"), "amount": float(amount), "note": note}
    )


def format_dollars(x: float) -> str:
    return f"${x:,.2f}"


def calc_monthly_schedule(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for month_num in range(1, 13):
        month_income = 0.0
        month_label = pd.Timestamp(year=2026, month=month_num, day=1).strftime("%b")
        for _, row in df.iterrows():
            payout_key = str(row.get("payout_months", "all")).strip().lower()
            months = PAYOUT_MONTH_MAP.get(payout_key, list(range(1, 13)))
            if month_num in months:
                annual_income = float(row.get("annual_income", 0.0))
                payments_per_year = max(len(months), 1)
                month_income += annual_income / payments_per_year
        rows.append({"Month": month_label, "Estimated Income": month_income})
    return pd.DataFrame(rows)


ensure_state()

st.title("💵 Retirement Paycheck Dashboard")

with st.sidebar:
    st.subheader("Controls")
    use_live_prices = st.toggle("Use Yahoo live prices", value=False, help="If off, the app uses your manual prices.")
    st.caption("FDRXX stays at $1.00 by design.")

    st.divider()
    st.subheader("Add New Money")
    st.caption("Use this ONLY for external money coming into this account, like a new BrokerageLink transfer.")
    add_amount = st.number_input("External cash amount", min_value=0.0, value=10000.0, step=1000.0)
    add_note = st.text_input("Note", value="New BrokerageLink transfer")

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("+ $1,000", use_container_width=True):
            add_external_cash(1000.0, "Quick add")
            st.rerun()
    with c2:
        if st.button("+ $5,000", use_container_width=True):
            add_external_cash(5000.0, "Quick add")
            st.rerun()
    with c3:
        if st.button("+ $10,000", use_container_width=True):
            add_external_cash(10000.0, "Quick add")
            st.rerun()

    if st.button("Add Custom Amount", use_container_width=True):
        add_external_cash(float(add_amount), add_note.strip() or "Custom external cash add")
        st.rerun()

    st.divider()
    st.subheader("Important rule")
    st.info(
        "Only use Add New Money when money comes from OUTSIDE this account.\n\n"
        "Normal buys and sells inside the account should NOT change Invested Cost Basis."
    )

left, right = st.columns([1.8, 1.2])

with left:
    st.subheader("Portfolio Holdings")

    working_df = st.session_state.portfolio_df.copy()
    edited_df = st.data_editor(
        working_df,
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        column_config={
            "ticker": st.column_config.TextColumn("Ticker"),
            "qty": st.column_config.NumberColumn("Qty", format="%.6f"),
            "avg_cost": st.column_config.NumberColumn("Avg Cost", format="$%.4f"),
            "manual_price": st.column_config.NumberColumn("Manual Price", format="$%.4f"),
            "target_weight": st.column_config.NumberColumn("Target %", format="%.2f"),
            "annual_yield": st.column_config.NumberColumn("Annual Yield", format="%.4f"),
            "payout_frequency": st.column_config.TextColumn("Payout Freq"),
            "payout_months": st.column_config.TextColumn("Payout Months"),
            "notes": st.column_config.TextColumn("Notes", width="medium"),
        },
        key="portfolio_editor",
    )

    # Clean edited data before saving.
    for col in ["qty", "avg_cost", "manual_price", "target_weight", "annual_yield"]:
        edited_df[col] = pd.to_numeric(edited_df[col], errors="coerce").fillna(0.0)
    for col in ["ticker", "payout_frequency", "payout_months", "notes"]:
        edited_df[col] = edited_df[col].fillna("").astype(str)

    st.session_state.portfolio_df = edited_df.copy()

    st.caption(
        "Edit quantities, cost basis, and manual prices here. "
        "Changing holdings does NOT change Invested Cost Basis. "
        "Only the Add New Money buttons do that."
    )

with right:
    st.subheader("Invested Basis Control")

    new_basis = st.number_input(
        "Invested Cost Basis",
        min_value=0.0,
        value=float(st.session_state.invested_cost_basis),
        step=1000.0,
        help="This should reflect total external money added into this account. Your current confirmed baseline is $359,000.",
    )
    st.session_state.invested_cost_basis = float(new_basis)

    st.caption(
        "This is NOT market value. It is your deposit / transfer basis for this account."
    )

display_df = apply_prices(st.session_state.portfolio_df.copy(), use_live_prices=use_live_prices)

portfolio_value = float(display_df["market_value"].sum())
holdings_cost_basis = float(display_df["cost_basis"].sum())
invested_cost_basis = float(st.session_state.invested_cost_basis)
gain_loss_vs_basis = portfolio_value - invested_cost_basis
estimated_monthly_income = float(display_df["monthly_income"].sum())
estimated_annual_income = estimated_monthly_income * 12.0

cash_mask = display_df["ticker"].astype(str).str.upper() == "FDRXX"
available_cash = float(display_df.loc[cash_mask, "market_value"].sum()) if cash_mask.any() else 0.0

st.divider()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Portfolio Value", format_dollars(portfolio_value))
m2.metric("Invested Cost Basis", format_dollars(invested_cost_basis))
m3.metric("Gain / Loss vs Basis", format_dollars(gain_loss_vs_basis))
m4.metric("Available Cash (FDRXX)", format_dollars(available_cash))

m5, m6, m7, m8 = st.columns(4)
m5.metric("Estimated Monthly Income", format_dollars(estimated_monthly_income))
m6.metric("Estimated Annual Income", format_dollars(estimated_annual_income))
m7.metric("Holdings Cost Basis", format_dollars(holdings_cost_basis))
m8.metric("Income Goal Progress", f"{(estimated_monthly_income / GOAL_MONTHLY * 100) if GOAL_MONTHLY else 0:.1f}%")

progress = min(max(estimated_monthly_income / GOAL_MONTHLY, 0.0), 1.0) if GOAL_MONTHLY else 0.0
st.progress(progress)

c_left, c_right = st.columns([1.2, 1.0])

with c_left:
    st.subheader("Income Breakdown")
    income_df = display_df[["ticker", "market_value", "annual_yield", "monthly_income", "annual_income", "notes"]].copy()
    income_df = income_df.sort_values("monthly_income", ascending=False)
    income_df["market_value"] = income_df["market_value"].map(format_dollars)
    income_df["monthly_income"] = income_df["monthly_income"].map(format_dollars)
    income_df["annual_income"] = income_df["annual_income"].map(format_dollars)
    income_df["annual_yield"] = income_df["annual_yield"].map(lambda x: f"{x:.2%}")
    st.dataframe(income_df, use_container_width=True, hide_index=True)

with c_right:
    st.subheader("Estimated Monthly Payment Calendar")
    schedule_df = calc_monthly_schedule(display_df)
    schedule_df["Estimated Income"] = schedule_df["Estimated Income"].map(format_dollars)
    st.dataframe(schedule_df, use_container_width=True, hide_index=True)

st.divider()

log_col, notes_col = st.columns([1.0, 1.0])

with log_col:
    st.subheader("External Money Log")
    log_df = pd.DataFrame(st.session_state.external_cash_log)
    if not log_df.empty:
        log_df["amount"] = log_df["amount"].map(format_dollars)
        st.dataframe(log_df, use_container_width=True, hide_index=True)
    else:
        st.info("No external cash adds logged yet.")

with notes_col:
    st.subheader("What updates basis vs what does not")
    st.markdown(
        """
**Updates Invested Cost Basis**
- New money transferred into BrokerageLink
- New outside cash added to this account
- Future pension rollover or other external deposits

**Does NOT update Invested Cost Basis**
- Selling one holding to buy another inside this account
- Market gains or losses
- Price changes
- Internal rebalancing
        """
    )

st.divider()
st.caption(
    "Locked rule for this dashboard: "
    "Invested Cost Basis starts at $359,000 and only changes when external money is added. "
    "The next new $10,000 transfer should move basis to $369,000 when it actually arrives."
)
