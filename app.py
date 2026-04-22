import json
import os
from typing import Dict, List

import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except Exception:
    yf = None


st.set_page_config(page_title="Retirement Paycheck Dashboard", page_icon="💵", layout="wide")

GOAL_MONTHLY = 8000.0

REALISTIC_INCOME_FACTOR = 0.843
CONSERVATIVE_INCOME_FACTOR = 0.632

STATE_FILE = "retirement_dashboard_state.json"

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
    ["DIVO", 988.162, 44.82, 44.82, 10.0, 0.048, "monthly", "all", ""],
    ["FEPI", 762.053, 40.55, 40.55, 7.0, 0.120, "monthly", "all", ""],
    ["GDXY", 3311.524, 13.11, 13.11, 15.0, 0.180, "monthly", "all", ""],
    ["IAU", 174.866, 84.64, 84.64, 4.0, 0.000, "none", "none", ""],
    ["IWMI", 306.959, 48.01, 48.01, 4.0, 0.120, "monthly", "all", ""],
    ["IYRI", 314.264, 46.93, 46.93, 5.0, 0.080, "monthly", "all", ""],
    ["MLPI", 273.825, 56.88, 56.88, 4.0, 0.080, "quarterly", "3,6,9,12", ""],
    ["QQQI", 598.751, 50.55, 53.89, 10.0, 0.140, "monthly", "all", ""],
    ["SPYI", 991.550, 49.67, 52.55, 12.0, 0.120, "monthly", "all", ""],
    ["SVOL", 1542.230, 15.47, 15.93, 6.0, 0.160, "monthly", "all", ""],
    ["TLTW", 971.555, 22.27, 22.57, 7.0, 0.120, "monthly", "all", ""],
]

DEFAULT_CASH_FDRXX = 8690.50

SMART_INCOME_TIERS = {
    "tier_1": ["SPYI", "DIVO"],
    "tier_2": ["QQQI", "FEPI"],
    "tier_3": ["SVOL", "IYRI", "TLTW"],
    "avoid": ["GDXY", "IAU"],
}

SMART_INCOME_SPLITS = {
    "tier_1": 0.75,
    "tier_2": 0.20,
    "tier_3": 0.05,
}


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


def normalize_portfolio_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    for col in DEFAULT_COLUMNS:
        if col not in out.columns:
            if col in ["qty", "avg_cost", "manual_price", "target_weight", "annual_yield"]:
                out[col] = 0.0
            else:
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


def get_default_portfolio_df() -> pd.DataFrame:
    return normalize_portfolio_df(pd.DataFrame(DEFAULT_ROWS, columns=DEFAULT_COLUMNS))


def get_default_total_contributions(df: pd.DataFrame, cash_fdrxx: float) -> float:
    holdings_cost = float((df["qty"].astype(float) * df["avg_cost"].astype(float)).sum())
    return float(holdings_cost + cash_fdrxx)


def round_money(value: float) -> float:
    return round(float(value), 2)


def round_shares(value: float) -> float:
    return round(float(value), 6)


def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)

        portfolio_records = raw.get("portfolio_df", [])
        if portfolio_records:
            portfolio_df = normalize_portfolio_df(pd.DataFrame(portfolio_records))
        else:
            portfolio_df = get_default_portfolio_df()

        cash_fdrxx = to_float(raw.get("cash_fdrxx", DEFAULT_CASH_FDRXX), DEFAULT_CASH_FDRXX)
        total_contributions = to_float(
            raw.get("total_contributions", get_default_total_contributions(portfolio_df, cash_fdrxx)),
            get_default_total_contributions(portfolio_df, cash_fdrxx),
        )
        use_live_prices = bool(raw.get("use_live_prices", True))

        return {
            "portfolio_df": portfolio_df,
            "cash_fdrxx": cash_fdrxx,
            "total_contributions": total_contributions,
            "use_live_prices": use_live_prices,
        }
    except Exception:
        return {}


def save_state() -> None:
    try:
        df = normalize_portfolio_df(st.session_state.portfolio_df.copy())
        payload = {
            "portfolio_df": df.to_dict(orient="records"),
            "cash_fdrxx": round_money(st.session_state.cash_fdrxx),
            "total_contributions": round_money(st.session_state.total_contributions),
            "use_live_prices": bool(st.session_state.use_live_prices),
        }
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception:
        pass


def init_state() -> None:
    if st.session_state.get("app_initialized", False):
        return

    loaded = load_state()

    portfolio_df = loaded.get("portfolio_df", get_default_portfolio_df())
    cash_fdrxx = to_float(loaded.get("cash_fdrxx", DEFAULT_CASH_FDRXX), DEFAULT_CASH_FDRXX)
    total_contributions = to_float(
        loaded.get("total_contributions", get_default_total_contributions(portfolio_df, cash_fdrxx)),
        get_default_total_contributions(portfolio_df, cash_fdrxx),
    )
    use_live_prices = bool(loaded.get("use_live_prices", True))

    st.session_state.portfolio_df = normalize_portfolio_df(portfolio_df)
    st.session_state.editor_df = normalize_portfolio_df(portfolio_df.copy())
    st.session_state.cash_fdrxx = round_money(cash_fdrxx)
    st.session_state.total_contributions = round_money(total_contributions)
    st.session_state.use_live_prices = use_live_prices
    st.session_state.app_initialized = True

    save_state()


def sync_editor_from_portfolio() -> None:
    st.session_state.editor_df = normalize_portfolio_df(st.session_state.portfolio_df.copy())


def get_live_prices(tickers: List[str]) -> Dict[str, float]:
    prices: Dict[str, float] = {}
    if yf is None or not tickers:
        return prices

    cleaned_tickers = [str(t).strip().upper() for t in tickers if str(t).strip()]
    if not cleaned_tickers:
        return prices

    try:
        joined = " ".join(sorted(set(cleaned_tickers)))
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

        unique_tickers = sorted(set(cleaned_tickers))

        if len(unique_tickers) == 1:
            close_series = data["Close"] if "Close" in data else None
            if close_series is not None and len(close_series.dropna()) > 0:
                prices[unique_tickers[0]] = float(close_series.dropna().iloc[-1])
            return prices

        for ticker in unique_tickers:
            try:
                close_series = data[ticker]["Close"]
                if len(close_series.dropna()) > 0:
                    prices[ticker] = float(close_series.dropna().iloc[-1])
            except Exception:
                continue
    except Exception:
        return prices

    return prices


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
    cash_fdrxx = round_money(cash_fdrxx)

    invested_cost_basis = holdings_cost_basis
    total_portfolio_value = holdings_market_value + cash_fdrxx
    total_contributions = float(st.session_state.total_contributions)

    net_vs_contributions = total_portfolio_value - total_contributions
    gain_loss_holdings_only = holdings_market_value - holdings_cost_basis

    total_annual_income_actual = float(working["annual_income_est"].sum())
    total_monthly_income_actual = total_annual_income_actual / 12.0

    total_monthly_income_realistic = total_monthly_income_actual * REALISTIC_INCOME_FACTOR
    total_annual_income_realistic = total_monthly_income_realistic * 12.0

    total_monthly_income_conservative = total_monthly_income_actual * CONSERVATIVE_INCOME_FACTOR
    total_annual_income_conservative = total_monthly_income_conservative * 12.0

    income_goal_progress = (total_monthly_income_realistic / GOAL_MONTHLY) if GOAL_MONTHLY > 0 else 0.0

    total_target_weight = float(working["target_weight"].sum())
    if total_target_weight > 0 and holdings_market_value > 0:
        working["current_weight"] = working["market_value"] / holdings_market_value
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
        "total_contributions": total_contributions,
        "net_vs_contributions": net_vs_contributions,
        "gain_loss_holdings_only": gain_loss_holdings_only,
        "total_monthly_income_actual": total_monthly_income_actual,
        "total_annual_income_actual": total_annual_income_actual,
        "total_monthly_income_realistic": total_monthly_income_realistic,
        "total_annual_income_realistic": total_annual_income_realistic,
        "total_monthly_income_conservative": total_monthly_income_conservative,
        "total_annual_income_conservative": total_annual_income_conservative,
        "income_goal_progress": income_goal_progress,
    }


def add_new_money(amount: float) -> None:
    amount = round_money(amount)
    if amount <= 0:
        return

    st.session_state.cash_fdrxx = round_money(st.session_state.cash_fdrxx + amount)
    st.session_state.total_contributions = round_money(st.session_state.total_contributions + amount)
    save_state()


def deploy_cash_to_position(ticker: str, dollars: float, calc_df: pd.DataFrame) -> None:
    ticker = str(ticker).upper().strip()
    dollars = round_money(dollars)

    if ticker == "" or dollars <= 0:
        return

    available_cash = round_money(st.session_state.cash_fdrxx)
    if dollars > available_cash:
        st.error("Not enough FDRXX cash available for that deployment.")
        return

    before_total_value = round_money(float(calc_df["market_value"].sum()) + available_cash)

    df = normalize_portfolio_df(st.session_state.portfolio_df.copy())
    calc_df = calc_df.copy()

    price_lookup = {
        str(row["ticker"]).upper().strip(): to_float(row["price_used"])
        for _, row in calc_df.iterrows()
    }
    manual_price_lookup = {
        str(row["ticker"]).upper().strip(): to_float(row["manual_price"])
        for _, row in df.iterrows()
    }

    price_used = price_lookup.get(ticker, 0.0)
    if price_used <= 0:
        price_used = manual_price_lookup.get(ticker, 0.0)

    price_used = round(to_float(price_used), 6)

    if price_used <= 0:
        st.error(f"Could not determine a valid price for {ticker}.")
        return

    shares_added = round_shares(dollars / price_used)
    match_idx = df.index[df["ticker"] == ticker].tolist()

    if match_idx:
        idx = match_idx[0]
        old_qty = to_float(df.at[idx, "qty"])
        old_avg_cost = to_float(df.at[idx, "avg_cost"])
        old_cost_basis = old_qty * old_avg_cost

        new_qty = round_shares(old_qty + shares_added)
        new_cost_basis = old_cost_basis + dollars
        new_avg_cost = round(new_cost_basis / new_qty, 6) if new_qty > 0 else 0.0

        df.at[idx, "qty"] = new_qty
        df.at[idx, "avg_cost"] = new_avg_cost

        existing_manual = to_float(df.at[idx, "manual_price"])
        if existing_manual <= 0:
            df.at[idx, "manual_price"] = round(price_used, 4)
    else:
        new_row = {
            "ticker": ticker,
            "qty": shares_added,
            "avg_cost": round(price_used, 6),
            "manual_price": round(price_used, 4),
            "target_weight": 0.0,
            "annual_yield": 0.0,
            "payout_frequency": "monthly",
            "payout_months": "all",
            "notes": "Added from cash deployment",
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    st.session_state.portfolio_df = normalize_portfolio_df(df)
    sync_editor_from_portfolio()
    st.session_state.cash_fdrxx = round_money(available_cash - dollars)

    post_calc = calculate_portfolio(
        st.session_state.portfolio_df,
        cash_fdrxx=st.session_state.cash_fdrxx,
        use_live_prices=bool(st.session_state.use_live_prices),
    )
    after_total_value = round_money(post_calc["total_portfolio_value"])

    if abs(after_total_value - before_total_value) > 0.05:
        st.warning(
            f"Transfer check: before deploy total was {format_dollars(before_total_value)} "
            f"and after deploy total is {format_dollars(after_total_value)}."
        )

    save_state()


def build_smarter_income_suggestions(df: pd.DataFrame, available_cash: float) -> pd.DataFrame:
    if available_cash <= 0:
        return pd.DataFrame()

    working = df.copy()
    if "price_used" not in working.columns:
        return pd.DataFrame()

    working["ticker"] = working["ticker"].astype(str).str.upper().str.strip()

    price_map = {
        row["ticker"]: to_float(row["price_used"])
        for _, row in working.iterrows()
        if row["ticker"] != ""
    }
    drift_map = {
        row["ticker"]: to_float(row.get("drift_dollars", 0.0))
        for _, row in working.iterrows()
        if row["ticker"] != ""
    }

    suggestions = []

    def choose_eligible(tickers: List[str]) -> List[str]:
        valid = [t for t in tickers if t in price_map and price_map[t] > 0]
        if not valid:
            return []

        under_or_equal = [t for t in valid if drift_map.get(t, 0.0) <= 0]
        if under_or_equal:
            return under_or_equal

        min_positive_drift = min(drift_map.get(t, 0.0) for t in valid)
        fallback = [t for t in valid if abs(drift_map.get(t, 0.0) - min_positive_drift) < 0.01]
        return fallback if fallback else valid

    def allocate_group(tickers: List[str], dollars: float) -> None:
        eligible = choose_eligible(tickers)
        if dollars <= 0 or not eligible:
            return

        per_ticker = dollars / len(eligible)
        for ticker in eligible:
            price = price_map[ticker]
            est_shares = per_ticker / price if price > 0 else 0.0
            drift_value = drift_map.get(ticker, 0.0)
            suggestions.append(
                {
                    "Ticker": ticker,
                    "Suggested Buy $": round(per_ticker, 2),
                    "Est Shares": round(est_shares, 3),
                    "Price Used": round(price, 2),
                    "Current Drift $": round(drift_value, 2),
                }
            )

    tier_1_amt = available_cash * SMART_INCOME_SPLITS["tier_1"]
    tier_2_amt = available_cash * SMART_INCOME_SPLITS["tier_2"]
    tier_3_amt = available_cash * SMART_INCOME_SPLITS["tier_3"]

    allocate_group(SMART_INCOME_TIERS["tier_1"], tier_1_amt)
    allocate_group(SMART_INCOME_TIERS["tier_2"], tier_2_amt)
    allocate_group(SMART_INCOME_TIERS["tier_3"], tier_3_amt)

    if not suggestions:
        return pd.DataFrame()

    return pd.DataFrame(suggestions)


def render_top_controls():
    st.title("💵 Retirement Paycheck Dashboard")

    left, middle, right = st.columns([1.1, 1.1, 1.4])

    with left:
        use_live = st.checkbox(
            "Use Yahoo Finance live prices",
            value=bool(st.session_state.use_live_prices),
            help="If Yahoo Finance is unavailable, the app falls back to Manual Price.",
        )
        if bool(use_live) != bool(st.session_state.use_live_prices):
            st.session_state.use_live_prices = bool(use_live)
            save_state()

    with middle:
        cash_input = st.number_input(
            "Available Cash (FDRXX)",
            min_value=0.0,
            value=float(st.session_state.cash_fdrxx),
            step=100.0,
            format="%.2f",
        )
        cash_input = round_money(cash_input)
        if cash_input != round_money(st.session_state.cash_fdrxx):
            st.session_state.cash_fdrxx = cash_input
            save_state()

    with right:
        total_contrib_input = st.number_input(
            "Total Contributions",
            min_value=0.0,
            value=float(st.session_state.total_contributions),
            step=100.0,
            format="%.2f",
            help="This should only change when new outside money is added, or if you manually correct the starting total.",
        )
        total_contrib_input = round_money(total_contrib_input)
        if total_contrib_input != round_money(st.session_state.total_contributions):
            st.session_state.total_contributions = total_contrib_input
            save_state()

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
    st.markdown("## 📊 Portfolio Overview")

    top1, top2, top3, top4 = st.columns(4)

    with top1:
        st.metric("Portfolio Value", format_dollars(calc["total_portfolio_value"]))

    with top2:
        st.metric("Net vs Contributions", format_dollars(calc["net_vs_contributions"]))

    with top3:
        st.metric("Available Cash (FDRXX)", format_dollars(calc["cash_fdrxx"]))

    with top4:
        st.metric("Total Contributions", format_dollars(calc["total_contributions"]))

    st.markdown("---")

    st.subheader("Monthly Income")
    m1, m2, m3 = st.columns(3)

    with m1:
        st.metric("Conservative", format_dollars(calc["total_monthly_income_conservative"]))

    with m2:
        st.metric("Realistic", format_dollars(calc["total_monthly_income_realistic"]))

    with m3:
        st.metric("Actual", format_dollars(calc["total_monthly_income_actual"]))

    st.markdown("---")

    st.subheader("Annual Income")
    a1, a2, a3 = st.columns(3)

    with a1:
        st.metric("Conservative", format_dollars(calc["total_annual_income_conservative"]))

    with a2:
        st.metric("Realistic", format_dollars(calc["total_annual_income_realistic"]))

    with a3:
        st.metric("Actual", format_dollars(calc["total_annual_income_actual"]))

    st.markdown("---")

    st.metric("Income Goal Progress", format_percent(calc["income_goal_progress"] * 100.0))


def render_portfolio_editor():
    st.subheader("Portfolio Holdings")
    st.caption("Edit the holdings, then click Save Holdings Changes.")

    with st.form("portfolio_form", clear_on_submit=False):
        edited_df = st.data_editor(
            st.session_state.editor_df,
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
            key="portfolio_editor_form",
        )

        save_pressed = st.form_submit_button("Save Holdings Changes", use_container_width=True)

    if save_pressed:
        cleaned = normalize_portfolio_df(edited_df)
        st.session_state.portfolio_df = cleaned
        st.session_state.editor_df = cleaned.copy()
        save_state()
        st.success("Holdings updated.")
        st.rerun()
    else:
        if not st.session_state.editor_df.equals(st.session_state.portfolio_df):
            pass


def render_deploy_cash(calc: dict):
    st.subheader("Deploy Cash Into a Position")

    available_cash = float(st.session_state.cash_fdrxx)
    ticker_options = sorted(calc["df"]["ticker"].astype(str).str.upper().tolist())

    if not ticker_options:
        st.info("No holdings available to deploy cash into yet.")
        return

    c1, c2, c3 = st.columns([1.3, 1.0, 0.9])

    with c1:
        deploy_ticker = st.selectbox(
            "Ticker",
            options=ticker_options,
            key="deploy_ticker",
        )

    with c2:
        deploy_amount = st.number_input(
            "Amount to Deploy",
            min_value=0.0,
            max_value=available_cash if available_cash > 0 else 0.0,
            value=0.0,
            step=100.0,
            format="%.2f",
            key="deploy_amount",
        )

    with c3:
        st.write("")
        st.write("")
        if st.button("Deploy Cash", use_container_width=True, disabled=available_cash <= 0):
            deploy_cash_to_position(deploy_ticker, float(deploy_amount), calc["df"])
            st.rerun()

    st.caption(
        "This moves money from FDRXX into the selected holding. "
        "Cash goes down, holding shares go up, invested cost basis goes up, total contributions do not change."
    )


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

    if calc["cash_fdrxx"] > 0:
        st.subheader("Smart Income Buys")
        st.caption(
            "Smarter aggressive income mode: prioritize SPYI/DIVO first, but skip overweight names when possible; "
            "then QQQI/FEPI; then SVOL/IYRI/TLTW. GDXY and IAU remain excluded."
        )

        sugg_df = build_smarter_income_suggestions(df, calc["cash_fdrxx"])

        if not sugg_df.empty:
            st.dataframe(
                sugg_df.style.format(
                    {
                        "Suggested Buy $": "${:,.2f}",
                        "Est Shares": "{:,.3f}",
                        "Price Used": "${:,.2f}",
                        "Current Drift $": "${:,.2f}",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No smart income suggestions available right now.")


def main():
    init_state()

    calc = calculate_portfolio(
        st.session_state.portfolio_df,
        cash_fdrxx=float(st.session_state.cash_fdrxx),
        use_live_prices=bool(st.session_state.use_live_prices),
    )

    render_top_controls()
    render_portfolio_editor()

    calc = calculate_portfolio(
        st.session_state.portfolio_df,
        cash_fdrxx=float(st.session_state.cash_fdrxx),
        use_live_prices=bool(st.session_state.use_live_prices),
    )

    render_metrics(calc)
    st.markdown("---")
    render_deploy_cash(calc)
    st.markdown("---")
    render_breakdowns(calc)


if __name__ == "__main__":
    main()
