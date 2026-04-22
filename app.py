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


def round_money(value: float) -> float:
    return round(float(value), 2)


def round_shares(value: float) -> float:
    return round(float(value), 6)


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
        last_price_sync = str(raw.get("last_price_sync", ""))

        return {
            "portfolio_df": portfolio_df,
            "cash_fdrxx": cash_fdrxx,
            "total_contributions": total_contributions,
            "use_live_prices": use_live_prices,
            "last_price_sync": last_price_sync,
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
            "last_price_sync": str(st.session_state.get("last_price_sync", "")),
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
    last_price_sync = str(loaded.get("last_price_sync", ""))

    st.session_state.portfolio_df = normalize_portfolio_df(portfolio_df)
    st.session_state.editor_df = normalize_portfolio_df(portfolio_df.copy())
    st.session_state.cash_fdrxx = round_money(cash_fdrxx)
    st.session_state.total_contributions = round_money(total_contributions)
    st.session_state.use_live_prices = use_live_prices
    st.session_state.last_price_sync = last_price_sync
    st.session_state.app_initialized = True

    save_state()


def sync_editor_from_portfolio() -> None:
    st.session_state.editor_df = normalize_portfolio_df(st.session_state.portfolio_df.copy())


def is_valid_price(live_price: float, fallback_price: float) -> bool:
    try:
        live_price = to_float(live_price, 0.0)
        fallback_price = to_float(fallback_price, 0.0)

        if live_price <= 0:
            return False

        if fallback_price > 0:
            pct_diff = abs(live_price - fallback_price) / fallback_price
            if pct_diff > 0.25:
                return False

        return True
    except Exception:
        return False


def get_live_prices(tickers: List[str]) -> Dict[str, float]:
    prices: Dict[str, float] = {}
    if yf is None or not tickers:
        return prices

    cleaned_tickers = [str(t).strip().upper() for t in tickers if str(t).strip()]
    unique_tickers = sorted(set(cleaned_tickers))
    if not unique_tickers:
        return prices

    try:
        if len(unique_tickers) == 1:
            ticker = unique_tickers[0]
            data = yf.download(
                ticker,
                period="5d",
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False,
            )
            if data is not None and len(data) > 0 and "Close" in data:
                close_series = data["Close"].dropna()
                if len(close_series) > 0:
                    prices[ticker] = float(close_series.iloc[-1])
            return prices

        data = yf.download(
            " ".join(unique_tickers),
            period="5d",
            interval="1d",
            auto_adjust=False,
            progress=False,
            group_by="ticker",
            threads=True,
        )

        if data is None or len(data) == 0:
            return prices

        for ticker in unique_tickers:
            try:
                close_series = data[ticker]["Close"].dropna()
                if len(close_series) > 0:
                    prices[ticker] = float(close_series.iloc[-1])
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

    price_used = []
    price_source = []
    refreshed_manual_prices = []

    for _, row in working.iterrows():
        live = to_float(row["live_price"], 0.0)
        manual = to_float(row["manual_price"], 0.0)

        if is_valid_price(live, manual):
            chosen = live
            source = "LIVE"
        else:
            chosen = manual
            source = "MANUAL"

        price_used.append(chosen)
        price_source.append(source)
        refreshed_manual_prices.append(chosen if source == "LIVE" else manual)

    working["price_used"] = price_used
    working["price_source"] = price_source

    updated_portfolio = st.session_state.portfolio_df.copy()
    updated_portfolio["manual_price"] = refreshed_manual_prices
    st.session_state.portfolio_df = normalize_portfolio_df(updated_portfolio)

    if use_live_prices and any(src == "LIVE" for src in price_source):
        st.session_state.last_price_sync = pd.Timestamp.now().strftime("%Y-%m-%d %I:%M:%S %p")
        save_state()

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

    live_count = int((working["price_source"] == "LIVE").sum())
    manual_count = int((working["price_source"] == "MANUAL").sum())

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
        "live_price_count":
