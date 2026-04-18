import math
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except Exception:
    yf = None

st.set_page_config(page_title="Retirement Paycheck Dashboard", page_icon="💵", layout="wide")

GOAL_MONTHLY = 8000.0
CASH_TICKERS = {"FDRXX", "SPAXX", "CASH", "MMF"}

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

# NOTE:
# I rebuilt this from the app structure we had in chat.
# The rows below are starter rows only. If you had more holdings in your previous file,
# paste those rows back into DEFAULT_ROWS after replacing your file with this one.
DEFAULT_ROWS = [
    ["AIPI", 668.196, 34.05, 33.79, 5.0, 0.124, "monthly", "all", ""],
    ["CHPY", 436.770, 60.2043356916, 61.01, 6.0, 0.050, "monthly", "all", "Basis inferred from value and G/L"],
    ["DIVO", 857.354, 39.10, 39.10, 10.0, 0.049, "monthly", "all", ""],
    ["SPYI", 0.0, 0.0, 47.50, 12.0, 0.120, "monthly", "all", ""],
    ["QQQI", 0.0, 0.0, 51.00, 10.0, 0.140, "monthly", "all", ""],
    ["FEPI", 0.0, 0.0, 51.00, 7.0, 0.180, "monthly", "all", ""],
    ["SVOL", 0.0, 0.0, 22.50, 6.0, 0.160, "monthly", "all", ""],
    ["FDRXX", 18690.50, 1.00, 1.00, 0.0, 0.048, "monthly", "all", "Available cash sweep"],
]

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


@st.cache_data(ttl=900)
def get_live_prices(tickers: Tuple[str, ...]) -> Dict[str, float]:
    prices: Dict[str, float] = {}
    clean = [t for t in tickers if t and t.upper() not in CASH_TICKERS]
    if not clean or yf is None:
        return prices

    try:
        downloaded = yf.download(clean, period="1d", interval="1d", progress=False, auto_adjust=False)
        if downloaded is None or downloaded.empty:
            return prices

        if isinstance(downloaded.columns, pd.MultiIndex):
            close_df = downloaded.get("Close")
            if close_df is not None:
                last_row = close_df.ffill().iloc[-1]
                for ticker, value in last_row.items():
                    if pd.notna(value):
                        prices[str(ticker).upper()] = float(value)
        else:
            close_series = downloaded.get("Close")
            if close_series is not None and not close_series.empty and len(clean) == 1:
                prices[clean[0].upper()] = float(close_series.ffill().iloc[-1])
    except Exception:
        return prices

    return prices


def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in DEFAULT_COLUMNS:
        if col not in df.columns:
            df[col] = "" if col in {"ticker", "payout_frequency", "payout_months", "notes"} else 0.0

    df = df[DEFAULT_COLUMNS]
    df["ticker"] = df["ticker"].fillna("").astype(str).str.upper().str.strip()

    numeric_cols = ["qty", "avg_cost", "manual_price", "target_weight", "annual_yield"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    for col in ["payout_frequency", "payout_months", "notes"]:
        df[col] = df[col].fillna("").astype(str)

    df = df[df["ticker"] != ""].reset_index(drop=True)
    return df


def payout_month_count(freq: str, months_text: str) -> int:
    freq = str(freq).strip().lower()
    months_text = str(months_text).strip().lower()

    if months_text == "all":
        return 12

    if months_text:
        count = 0
        for part in [p.strip()[:3] for p in months_text.split(",") if p.strip()]:
            if part in MONTH_MAP:
                count += 1
        if count > 0:
            return count

    if freq == "monthly":
        return 12
    if freq == "quarterly":
        return 4
    if freq == "semiannual":
        return 2
    if freq == "annual":
        return 1
    return 12


def add_calculated_columns(df: pd.DataFrame, use_live_prices: bool) -> pd.DataFrame:
    df = normalize_df(df)
    df = df.copy()
    df["is_cash"] = df["ticker"].isin(CASH_TICKERS)

    live_prices: Dict[str, float] = {}
    if use_live_prices:
        tickers = tuple(df.loc[~df["is_cash"], "ticker"].dropna().astype(str).unique().tolist())
        live_prices = get_live_prices(tickers)

    def resolved_price(row: pd.Series) -> float:
        ticker = row["ticker"]
        if row["is_cash"]:
            return 1.0 if row["manual_price"] <= 0 else float(row["manual_price"])
        if use_live_prices and ticker in live_prices and live_prices[ticker] > 0:
            return float(live_prices[ticker])
        if row["manual_price"] > 0:
            return float(row["manual_price"])
        if row["avg_cost"] > 0:
            return float(row["avg_cost"])
        return 0.0

    df["price"] = df.apply(resolved_price, axis=1)
    df["market_value"] = df["qty"] * df["price"]
    df["cost_basis"] = df["qty"] * df["avg_cost"]
    df["gain_loss"] = df["market_value"] - df["cost_basis"]
    df["return_pct"] = df.apply(
        lambda r: (r["gain_loss"] / r["cost_basis"] * 100.0) if r["cost_basis"] > 0 else 0.0,
        axis=1,
    )
    df["annual_income"] = df["market_value"] * df["annual_yield"]
    df["monthly_income"] = df["annual_income"] / 12.0
    df["payout_count"] = df.apply(lambda r: payout_month_count(r["payout_frequency"], r["payout_months"]), axis=1)
    return df


def summarize_portfolio(df: pd.DataFrame) -> Dict[str, float]:
    invested = df[~df["is_cash"]].copy()
    cash = df[df["is_cash"]].copy()

    available_cash = float(cash["market_value"].sum())
    invested_market_value = float(invested["market_value"].sum())
    invested_cost_basis = float(invested["cost_basis"].sum())
    invested_gain_loss = invested_market_value - invested_cost_basis
    total_portfolio_value = invested_market_value + available_cash
    monthly_income = float(df["monthly_income"].sum())
    annual_income = monthly_income * 12.0
    target_weight_total = float(invested["target_weight"].sum())
    goal_progress = (monthly_income / GOAL_MONTHLY * 100.0) if GOAL_MONTHLY > 0 else 0.0

    return {
        "available_cash": available_cash,
        "invested_market_value": invested_market_value,
        "invested_cost_basis": invested_cost_basis,
        "invested_gain_loss": invested_gain_loss,
        "invested_return_pct": (invested_gain_loss / invested_cost_basis * 100.0) if invested_cost_basis > 0 else 0.0,
        "total_portfolio_value": total_portfolio_value,
        "monthly_income": monthly_income,
        "annual_income": annual_income,
        "goal_progress": goal_progress,
        "target_weight_total": target_weight_total,
    }


def income_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    working = df.copy()
    working["income_tier"] = working["annual_yield"].apply(
        lambda y: "Safe" if y <= 0.06 else ("Middle" if y <= 0.11 else "Actual")
    )
    grouped = (
        working.groupby("income_tier", dropna=False)[["market_value", "monthly_income", "annual_income"]]
        .sum()
        .reset_index()
    )
    order = {"Safe": 0, "Middle": 1, "Actual": 2}
    grouped["sort_key"] = grouped["income_tier"].map(order).fillna(99)
    grouped = grouped.sort_values("sort_key").drop(columns="sort_key")
    return grouped


def rebalance_suggestions(df: pd.DataFrame, new_money: float) -> pd.DataFrame:
    invested = df[~df["is_cash"]].copy()
    invested = invested[invested["target_weight"] > 0].copy()
    if invested.empty or new_money <= 0:
        return pd.DataFrame(columns=["ticker", "current_weight", "target_weight", "gap_to_target", "suggested_buy"])

    current_total = float(invested["market_value"].sum())
    future_total = current_total + new_money

    invested["current_weight"] = invested["market_value"] / current_total * 100.0 if current_total > 0 else 0.0
    invested["target_value"] = future_total * invested["target_weight"] / 100.0
    invested["gap_to_target"] = invested["target_value"] - invested["market_value"]
    invested["gap_to_target"] = invested["gap_to_target"].clip(lower=0.0)

    total_gap = float(invested["gap_to_target"].sum())
    if total_gap <= 0:
        invested["suggested_buy"] = 0.0
    else:
        invested["suggested_buy"] = invested["gap_to_target"] / total_gap * new_money

    out = invested[["ticker", "current_weight", "target_weight", "gap_to_target", "suggested_buy"]].copy()
    out = out.sort_values("suggested_buy", ascending=False).reset_index(drop=True)
    return out


def fmt_money(x: float) -> str:
    return f"${x:,.2f}"


def fmt_pct(x: float) -> str:
    return f"{x:,.2f}%"


st.title("💵 Retirement Paycheck Dashboard")
st.caption("Invested Cost Basis now tracks invested positions only. Cash stays separate.")

if "portfolio_df" not in st.session_state:
    st.session_state.portfolio_df = pd.DataFrame(DEFAULT_ROWS, columns=DEFAULT_COLUMNS)

with st.sidebar:
    st.header("Settings")
    use_live_prices = st.toggle("Use Yahoo Finance live prices", value=True)
    goal_monthly = st.number_input("Monthly income goal", min_value=0.0, value=GOAL_MONTHLY, step=100.0)
    show_cash_row = st.toggle("Show cash row in table", value=True)

st.subheader("Portfolio Table")
edited_df = st.data_editor(
    st.session_state.portfolio_df,
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    column_config={
        "ticker": st.column_config.TextColumn("Ticker"),
        "qty": st.column_config.NumberColumn("Qty", format="%.4f"),
        "avg_cost": st.column_config.NumberColumn("Avg Cost", format="$%.4f"),
        "manual_price": st.column_config.NumberColumn("Manual Price", format="$%.4f"),
        "target_weight": st.column_config.NumberColumn("Target Weight %", format="%.2f"),
        "annual_yield": st.column_config.NumberColumn("Annual Yield", format="%.4f"),
        "payout_frequency": st.column_config.TextColumn("Payout Frequency"),
        "payout_months": st.column_config.TextColumn("Payout Months"),
        "notes": st.column_config.TextColumn("Notes", width="large"),
    },
    key="portfolio_editor",
)
st.session_state.portfolio_df = edited_df.copy()

calc_df = add_calculated_columns(edited_df, use_live_prices=use_live_prices)
summary = summarize_portfolio(calc_df)

goal_progress = (summary["monthly_income"] / goal_monthly * 100.0) if goal_monthly > 0 else 0.0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Portfolio Value", fmt_money(summary["total_portfolio_value"]))
c2.metric("Available Cash", fmt_money(summary["available_cash"]))
c3.metric("Invested Cost Basis", fmt_money(summary["invested_cost_basis"]))
c4.metric(
    "Invested Gain / Loss",
    fmt_money(summary["invested_gain_loss"]),
    delta=fmt_pct(summary["invested_return_pct"]),
)

c5, c6, c7, c8 = st.columns(4)
c5.metric("Invested Market Value", fmt_money(summary["invested_market_value"]))
c6.metric("Estimated Monthly Income", fmt_money(summary["monthly_income"]))
c7.metric("Estimated Annual Income", fmt_money(summary["annual_income"]))
c8.metric("Goal Progress", fmt_pct(goal_progress))

st.progress(min(max(goal_progress / 100.0, 0.0), 1.0))
st.caption(f"Monthly income goal progress: {fmt_money(summary['monthly_income'])} / {fmt_money(goal_monthly)}")

st.subheader("Holdings Summary")
display_df = calc_df.copy()
if not show_cash_row:
    display_df = display_df[~display_df["is_cash"]].copy()

display_cols = [
    "ticker",
    "qty",
    "avg_cost",
    "price",
    "market_value",
    "cost_basis",
    "gain_loss",
    "return_pct",
    "target_weight",
    "annual_yield",
    "monthly_income",
    "notes",
]
st.dataframe(
    display_df[display_cols],
    use_container_width=True,
    hide_index=True,
    column_config={
        "qty": st.column_config.NumberColumn("Qty", format="%.4f"),
        "avg_cost": st.column_config.NumberColumn("Avg Cost", format="$%.4f"),
        "price": st.column_config.NumberColumn("Price", format="$%.4f"),
        "market_value": st.column_config.NumberColumn("Market Value", format="$%.2f"),
        "cost_basis": st.column_config.NumberColumn("Cost Basis", format="$%.2f"),
        "gain_loss": st.column_config.NumberColumn("Gain / Loss", format="$%.2f"),
        "return_pct": st.column_config.NumberColumn("Return %", format="%.2f%%"),
        "target_weight": st.column_config.NumberColumn("Target Weight %", format="%.2f"),
        "annual_yield": st.column_config.NumberColumn("Annual Yield", format="%.4f"),
        "monthly_income": st.column_config.NumberColumn("Monthly Income", format="$%.2f"),
    },
)

st.subheader("Income Breakdown")
breakdown_df = income_breakdown(calc_df)
st.dataframe(
    breakdown_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "market_value": st.column_config.NumberColumn("Market Value", format="$%.2f"),
        "monthly_income": st.column_config.NumberColumn("Monthly Income", format="$%.2f"),
        "annual_income": st.column_config.NumberColumn("Annual Income", format="$%.2f"),
    },
)

st.subheader("Add New Money Helper")
quick_cols = st.columns(5)
quick_amount = 0.0
button_amounts = [1000, 5000, 10000, 16000, 32000]
for idx, amount in enumerate(button_amounts):
    if quick_cols[idx].button(f"${amount:,.0f}"):
        quick_amount = float(amount)

manual_new_money = st.number_input("Custom new money amount", min_value=0.0, value=quick_amount, step=100.0)

suggest_df = rebalance_suggestions(calc_df, manual_new_money)
if manual_new_money > 0:
    st.dataframe(
        suggest_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "current_weight": st.column_config.NumberColumn("Current Weight %", format="%.2f"),
            "target_weight": st.column_config.NumberColumn("Target Weight %", format="%.2f"),
            "gap_to_target": st.column_config.NumberColumn("Gap to Target", format="$%.2f"),
            "suggested_buy": st.column_config.NumberColumn("Suggested Buy", format="$%.2f"),
        },
    )
else:
    st.info("Tap a quick amount or enter a custom number to see suggested buys.")

with st.expander("What changed in this fixed version"):
    st.markdown(
        """
        - **Total Contributions default removed** — no more hard-coded $327,000.
        - **Invested Cost Basis** now auto-calculates from `qty × avg_cost` for invested positions only.
        - **Available Cash** stays separate and no longer inflates invested performance.
        - **Invested Gain / Loss** compares invested market value against invested cost basis only.
        - **FDRXX/SPAXX** are treated as cash rows by default.
        """
    )
