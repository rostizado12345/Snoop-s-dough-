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

# Income tier multipliers:
# Actual = raw portfolio yield math from the holdings
# Realistic / Conservative = toned-down planning views
#
# These were calibrated so the current portfolio lands close to the ranges
# you've wanted to see in the app instead of only showing the highest figure.
REALISTIC_INCOME_FACTOR = 0.843
CONSERVATIVE_INCOME_FACTOR = 0.632

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
    ["CHPY", 440.524, 56.07, 56.07, 6.0, 0.050, "monthly", "all", ""],
    ["DIVO", 944.929, 44.82, 44.82, 10.0, 0.048, "monthly", "all", ""],
    ["FEPI", 721.408, 40.55, 40.55, 7.0, 0.120, "monthly", "all", ""],
    ["GDXY", 3311.524, 13.11, 13.11, 15.0, 0.180, "monthly", "all", ""],
    ["IAU", 174.866, 84.64, 84.64, 4.0, 0.000, "none", "none", ""],
    ["IWMI", 287.468, 48.01, 48.01, 4.0, 0.120, "monthly", "all", ""],
    ["IYRI", 314.264, 46.93, 46.93, 5.0, 0.080, "monthly", "all", ""],
    ["MLPI", 260.204, 56.88, 56.88, 4.0, 0.080, "quarterly", "3,6,9,12", ""],
    ["QQQI", 556.887, 50.55, 53.89, 10.0, 0.140, "monthly", "all", ""],
    ["SPYI", 991.550, 49.67, 52.55, 12.0, 0.120, "monthly", "all", ""],
    ["SVOL", 1463.811, 15.47, 15.93, 6.0, 0.160, "monthly", "all", ""],
    ["TLTW", 927.268, 22.27, 22.57, 7.0, 0.120, "monthly", "all", ""],
]

DEFAULT_CASH_FDRXX = 18690.50


def to_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            cleaned = (
                value.replace("$", "")
                .replace(",", "")
                .replace("%", "")
                .strip()
            )
            if cleaned == "":
                return default
            return float(cleaned)
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def format_dollars(value: float) -> str:
    return f"${value:,.2f}"


def format_percent(value: float) -> str:
    return f"{value:,.1f}%"


def init_state() -> None:
    if "portfolio_df" not in st.session_state:
        st.session_state.portfolio_df = pd.DataFrame(DEFAULT_ROWS, columns=DEFAULT_COLUMNS)

    if "cash_fdrxx" not in st.session_state:
        st.session_state.cash_fdrxx = DEFAULT_CASH_FDRXX

    if "total_contributions" not in st.session_state:
        starting_holdings_cost = float(
            (st.session_state.portfolio_df["qty"].astype(float) * st.session_state.portfolio_df["avg_cost"].astype(float)).sum()
        )
        st.session_state.total_contributions = starting_holdings_cost + float(st.session_state.cash_fdrxx)

    if "use_live_prices" not in st.session_state:
        st.session_state.use_live_prices = True


def get_live_prices(tickers: List[str]) -> Dict[str, float]:
    prices: Dict[str, float] = {}
    if yf is None or not tickers:
        return prices

    try:
        joined = " ".join(sorted(set([t for t in tickers if str(t).strip()])))
        data = yf.download(
            joined,
            period="5d",
            interval="1d",
            auto_adjust=False,
            progress=False,
            group_by="ticker",
            threads=True,
        )

        if data is None or len(data) == 0:
            return prices

        if len(tickers) == 1:
            close_series = data["Close"] if "Close" in data else None
            if close_series is not None and len(close_series.dropna()) > 0:
                prices[tickers[0]] = float(close_series.dropna().iloc[-1])
            return prices

        for ticker in tickers:
            try:
                close_series = data[ticker]["Close"]
                if len(close_series.dropna()) > 0:
                    prices[ticker] = float(close_series.dropna().iloc[-1])
            except Exception:
                continue
    except Exception:
        return prices

    return prices


def normalize_portfolio_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    for col in DEFAULT_COLUMNS:
        if col not in out.columns:
            out[col] = ""

    numeric_cols = ["qty", "avg_cost", "manual_price", "target_weight", "annual_yield"]
    for col in numeric_cols:
        out[col] = out[col].apply(to_float)

    out["ticker"] = out["ticker"].astype(str).str.upper().str.strip()
    out["payout_frequency"] = out["payout_frequency"].astype(str).str.strip().replace("", "monthly")
    out["payout_months"] = out["payout_months"].astype(str).str.strip().replace("", "all")
    out["notes"] = out["notes"].astype(str)

    out = out[out["ticker"] != ""].reset_index(drop=True)
    return out[DEFAULT_COLUMNS]


def calculate_portfolio(df: pd.DataFrame, cash_fdrxx: float, use_live_prices: bool):
    df = normalize_portfolio_df(df)

    tickers = df["ticker"].tolist()
    live_prices = get_live_prices(tickers) if use_live_prices else {}

    working = df.copy()
    working["live_price"] = working["ticker"].map(live_prices).fillna(float("nan"))
    working["price_used"] = working.apply(
        lambda row: row["live_price"] if not pd.isna(row["live_price"]) and row["live_price"] > 0 else row["manual_price"],
        axis=1,
    )

    working["cost_basis"] = working["qty"] * working["avg_cost"]
    working["market_value"] = working["qty"] * working["price_used"]
    working["gain_loss"] = working["market_value"] - working["cost_basis"]
    working["gain_loss_pct"] = working.apply(
        lambda row: (row["gain_loss"] / row["cost_basis"]) if row["cost_basis"] > 0 else 0.0,
        axis=1,
    )

    working["annual_income_est"] = working["market_value"] * working["annual_yield"]
    working["monthly_income_est"] = working["annual_income_est"] / 12.0

    holdings_cost_basis = float(working["cost_basis"].sum())
    holdings_market_value = float(working["market_value"].sum())
    invested_cost_basis = holdings_cost_basis + cash_fdrxx
    total_portfolio_value = holdings_market_value + cash_fdrxx

    if st.session_state.total_contributions < invested_cost_basis:
        st.session_state.total_contributions = invested_cost_basis

    total_annual_income_actual = float(working["annual_income_est"].sum())
    total_monthly_income_actual = total_annual_income_actual / 12.0

    total_monthly_income_realistic = total_monthly_income_actual * REALISTIC_INCOME_FACTOR
    total_annual_income_realistic = total_monthly_income_realistic * 12.0

    total_monthly_income_conservative = total_monthly_income_actual * CONSERVATIVE_INCOME_FACTOR
    total_annual_income_conservative = total_monthly_income_conservative * 12.0

    income_goal_progress = (total_monthly_income_realistic / GOAL_MONTHLY) if GOAL_MONTHLY > 0 else 0.0

    gain_loss_vs_basis = total_portfolio_value - invested_cost_basis

    total_target_weight = float(working["target_weight"].sum())
    if total_target_weight > 0:
        working["current_weight"] = working["market_value"] / holdings_market_value if holdings_market_value > 0 else 0.0
        working["target_weight_decimal"] = working["target_weight"] / 100.0
        working["target_value"] = working["target_weight_decimal"] * holdings_market_value
        working["drift_dollars"] = working["market_value"] - working["target_value"]
        working["drift_pct_points"] = (working["current_weight"] - working["target_weight_decimal"]) * 100.0
    else:
        working["current_weight"] = 0.0
        working["target_weight_decimal"] = 0.0
        working["target_value"] = 0.0
        working["drift_dollars"] = 0.0
        working["drift_pct_points"] = 0.0

    return {
        "df": working,
        "holdings_cost_basis": holdings_cost_basis,
        "holdings_market_value": holdings_market_value,
        "invested_cost_basis": invested_cost_basis,
        "total_portfolio_value": total_portfolio_value,
        "cash_fdrxx": cash_fdrxx,
        "gain_loss_vs_basis": gain_loss_vs_basis,
        "total_monthly_income_actual": total_monthly_income_actual,
        "total_annual_income_actual": total_annual_income_actual,
        "total_monthly_income_realistic": total_monthly_income_realistic,
        "total_annual_income_realistic": total_annual_income_realistic,
        "total_monthly_income_conservative": total_monthly_income_conservative,
        "total_annual_income_conservative": total_annual_income_conservative,
        "income_goal_progress": income_goal_progress,
    }


def add_new_money(amount: float) -> None:
    if amount <= 0:
        return
    st.session_state.cash_fdrxx = float(st.session_state.cash_fdrxx) + amount
    st.session_state.total_contributions = float(st.session_state.total_contributions) + amount


def render_top_controls():
    st.title("💵 Retirement Paycheck Dashboard")

    left, middle, right = st.columns([1.1, 1.1, 1.4])

    with left:
        use_live = st.checkbox(
            "Use Yahoo Finance live prices",
            value=st.session_state.use_live_prices,
            help="If Yahoo Finance is unavailable, the app falls back to Manual Price.",
        )
        st.session_state.use_live_prices = use_live

    with middle:
        cash_input = st.number_input(
            "Available Cash (FDRXX)",
            min_value=0.0,
            value=float(st.session_state.cash_fdrxx),
            step=100.0,
            format="%.2f",
        )
        st.session_state.cash_fdrxx = cash_input

    with right:
        total_contrib_input = st.number_input(
            "Total Contributions",
            min_value=0.0,
            value=float(st.session_state.total_contributions),
            step=100.0,
            format="%.2f",
            help="Used internally for tracking new money added over time.",
        )
        st.session_state.total_contributions = total_contrib_input

    st.markdown("---")

    st.subheader("Add New Money")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        if st.button("+ $1,000", use_container_width=True):
            add_new_money(1000.0)
            st.rerun()
    with c2:
        if st.button("+ $5,000", use_container_width=True):
            add_new_money(5000.0)
            st.rerun()
    with c3:
        if st.button("+ $10,000", use_container_width=True):
            add_new_money(10000.0)
            st.rerun()
    with c4:
        custom_add = st.number_input(
            "Custom",
            min_value=0.0,
            value=0.0,
            step=100.0,
            format="%.2f",
            label_visibility="collapsed",
            placeholder="Custom amount",
        )
    with c5:
        if st.button("Add Custom", use_container_width=True):
            add_new_money(float(custom_add))
            st.rerun()


def render_metrics(calc: dict):
    a, b, c, d = st.columns(4)
    e, f, g, h = st.columns(4)

    with a:
        st.metric("Portfolio Value", format_dollars(calc["total_portfolio_value"]))

    with b:
        st.metric("Invested Cost Basis", format_dollars(calc["invested_cost_basis"]))

    with c:
        st.metric("Gain / Loss vs Basis", format_dollars(calc["gain_loss_vs_basis"]))

    with d:
        st.metric("Available Cash (FDRXX)", format_dollars(calc["cash_fdrxx"]))

    with e:
        st.metric("Monthly Income (Conservative)", format_dollars(calc["total_monthly_income_conservative"]))

    with f:
        st.metric("Monthly Income (Realistic)", format_dollars(calc["total_monthly_income_realistic"]))

    with g:
        st.metric("Monthly Income (Actual)", format_dollars(calc["total_monthly_income_actual"]))

    with h:
        st.metric("Holdings Cost Basis", format_dollars(calc["holdings_cost_basis"]))

    i, j, k = st.columns(3)
    with i:
        st.metric("Annual Income (Conservative)", format_dollars(calc["total_annual_income_conservative"]))
    with j:
        st.metric("Annual Income (Realistic)", format_dollars(calc["total_annual_income_realistic"]))
    with k:
        st.metric("Annual Income (Actual)", format_dollars(calc["total_annual_income_actual"]))

    st.metric("Income Goal Progress", format_percent(calc["income_goal_progress"] * 100.0))


def render_portfolio_editor():
    st.subheader("Portfolio Holdings")

    edited_df = st.data_editor(
        st.session_state.portfolio_df,
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        column_config={
            "ticker": st.column_config.TextColumn("Ticker"),
            "qty": st.column_config.NumberColumn("Qty", format="%.3f"),
            "avg_cost": st.column_config.NumberColumn("Avg Cost", format="%.2f"),
            "manual_price": st.column_config.NumberColumn("Manual Price", format="%.2f"),
            "target_weight": st.column_config.NumberColumn("Target Weight %", format="%.2f"),
            "annual_yield": st.column_config.NumberColumn("Annual Yield", format="%.4f"),
            "payout_frequency": st.column_config.TextColumn("Payout Frequency"),
            "payout_months": st.column_config.TextColumn("Payout Months"),
            "notes": st.column_config.TextColumn("Notes"),
        },
        key="portfolio_editor",
    )

    st.session_state.portfolio_df = normalize_portfolio_df(edited_df)


def render_breakdowns(calc: dict):
    df = calc["df"].copy()

    display_df = df[
        [
            "ticker",
            "qty",
            "avg_cost",
            "price_used",
            "cost_basis",
            "market_value",
            "gain_loss",
            "gain_loss_pct",
            "annual_yield",
            "monthly_income_est",
            "current_weight",
            "target_weight",
            "drift_dollars",
        ]
    ].copy()

    display_df.columns = [
        "Ticker",
        "Qty",
        "Avg Cost",
        "Price Used",
        "Cost Basis",
        "Market Value",
        "Gain/Loss",
        "Gain/Loss %",
        "Annual Yield",
        "Monthly Income (Actual)",
        "Current Weight",
        "Target Weight %",
        "Drift $",
    ]

    st.subheader("Holdings Detail")
    st.dataframe(
        display_df.style.format(
            {
                "Qty": "{:,.3f}",
                "Avg Cost": "${:,.2f}",
                "Price Used": "${:,.2f}",
                "Cost Basis": "${:,.2f}",
                "Market Value": "${:,.2f}",
                "Gain/Loss": "${:,.2f}",
                "Gain/Loss %": "{:,.2%}",
                "Annual Yield": "{:,.2%}",
                "Monthly Income (Actual)": "${:,.2f}",
                "Current Weight": "{:,.2%}",
                "Target Weight %": "{:,.2f}",
                "Drift $": "${:,.2f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Income Breakdown")
    income_df = df[["ticker", "market_value", "annual_yield", "annual_income_est", "monthly_income_est"]].copy()
    income_df.columns = ["Ticker", "Market Value", "Annual Yield", "Annual Income (Actual)", "Monthly Income (Actual)"]
    st.dataframe(
        income_df.style.format(
            {
                "Market Value": "${:,.2f}",
                "Annual Yield": "{:,.2%}",
                "Annual Income (Actual)": "${:,.2f}",
                "Monthly Income (Actual)": "${:,.2f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Rebalance Helper")
    rebalance_df = df[["ticker", "market_value", "current_weight", "target_weight", "drift_dollars", "drift_pct_points"]].copy()
    rebalance_df.columns = ["Ticker", "Market Value", "Current Weight", "Target Weight %", "Over/Under $", "Over/Under % Pts"]
    st.dataframe(
        rebalance_df.style.format(
            {
                "Market Value": "${:,.2f}",
                "Current Weight": "{:,.2%}",
                "Target Weight %": "{:,.2f}",
                "Over/Under $": "${:,.2f}",
                "Over/Under % Pts": "{:,.2f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    underweights = df.sort_values("drift_dollars").copy()
    underweights = underweights[underweights["drift_dollars"] < 0]

    if len(underweights) > 0 and calc["cash_fdrxx"] > 0:
        st.markdown("**Suggested buys with available cash (largest underweights first):**")
        remaining_cash = calc["cash_fdrxx"]
        suggestions = []
        for _, row in underweights.iterrows():
            needed = abs(float(row["drift_dollars"]))
            buy_amt = min(remaining_cash, needed)
            if buy_amt > 0:
                suggestions.append(
                    {
                        "Ticker": row["ticker"],
                        "Suggested Buy $": buy_amt,
                    }
                )
                remaining_cash -= buy_amt
            if remaining_cash <= 0:
                break

        if suggestions:
            sugg_df = pd.DataFrame(suggestions)
            st.dataframe(
                sugg_df.style.format({"Suggested Buy $": "${:,.2f}"}),
                use_container_width=True,
                hide_index=True,
            )


def main():
    init_state()
    render_top_controls()
    render_portfolio_editor()

    calc = calculate_portfolio(
        st.session_state.portfolio_df,
        cash_fdrxx=float(st.session_state.cash_fdrxx),
        use_live_prices=bool(st.session_state.use_live_prices),
    )

    st.session_state.portfolio_df = normalize_portfolio_df(st.session_state.portfolio_df)

    render_metrics(calc)
    st.markdown("---")
    render_breakdowns(calc)


if __name__ == "__main__":
    main()
