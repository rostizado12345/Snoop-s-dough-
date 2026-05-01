import json
import os
from datetime import datetime
from typing import Dict, List

import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except Exception:
    yf = None


st.set_page_config(page_title="Retirement Paycheck Dashboard", page_icon="💵", layout="wide")

APP_BASELINE_VERSION = "2026-04-30-production-fidelity-snapshot-v2-color-ui"

GOAL_MONTHLY = 8000.0
REALISTIC_INCOME_FACTOR = 0.843
CONSERVATIVE_INCOME_FACTOR = 0.632

STATE_FILE = "retirement_dashboard_state.json"
BACKUP_FILE = "retirement_dashboard_state_backup.json"

DEFAULT_CASH_FDRXX = 23690.85
DEFAULT_TOTAL_CONTRIBUTIONS = 366299.07

DEFAULT_COLUMNS = [
    "ticker", "qty", "avg_cost", "manual_price", "target_weight",
    "annual_yield", "payout_frequency", "payout_months", "notes",
]

DEFAULT_ROWS = [
    ["AIPI", 668.196, 34.04685, 35.68, 5.0, 0.124, "monthly", "all", ""],
    ["CHPY", 440.524, 56.06939, 67.70, 6.0, 0.050, "monthly", "all", ""],
    ["DIVO", 1087.280, 44.92944, 45.13, 10.0, 0.048, "monthly", "all", ""],
    ["FEPI", 820.192, 39.99048, 42.93, 7.0, 0.120, "monthly", "all", ""],
    ["GDXY", 3311.524, 13.10574, 12.71, 15.0, 0.180, "monthly", "all", ""],
    ["IAU", 174.866, 84.63566, 85.55, 4.0, 0.000, "none", "none", ""],
    ["IWMI", 306.959, 48.21481, 50.37, 4.0, 0.120, "monthly", "all", ""],
    ["IYRI", 314.264, 46.93339, 49.16, 5.0, 0.080, "monthly", "all", ""],
    ["MLPI", 273.825, 56.78753, 56.38, 4.0, 0.080, "quarterly", "3,6,9,12", ""],
    ["QQQI", 655.929, 50.46252, 53.86, 10.0, 0.140, "monthly", "all", ""],
    ["SPYI", 1116.585, 49.48005, 52.14, 12.0, 0.120, "monthly", "all", ""],
    ["SVOL", 1542.230, 15.49701, 15.91, 6.0, 0.160, "monthly", "all", ""],
    ["TLTW", 971.555, 22.28491, 22.30, 7.0, 0.120, "monthly", "all", ""],
]

SMART_INCOME_TIERS = {
    "tier_1": ["SPYI", "DIVO"],
    "tier_2": ["QQQI", "FEPI"],
    "tier_3": ["SVOL", "IYRI", "TLTW"],
    "avoid": ["GDXY", "IAU"],
}

SMART_INCOME_SPLITS = {"tier_1": 0.75, "tier_2": 0.20, "tier_3": 0.05}


def to_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            cleaned = value.replace("$", "").replace(",", "").replace("%", "").strip()
            return default if cleaned == "" else float(cleaned)
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def round_money(value: float) -> float:
    return round(float(value), 2)


def round_shares(value: float) -> float:
    return round(float(value), 6)


def format_dollars(value: float) -> str:
    return f"${float(value):,.2f}"


def format_percent(value: float) -> str:
    return f"{float(value):,.1f}%"


def normalize_portfolio_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    for col in DEFAULT_COLUMNS:
        if col not in out.columns:
            out[col] = 0.0 if col in ["qty", "avg_cost", "manual_price", "target_weight", "annual_yield"] else ""

    for col in ["qty", "avg_cost", "manual_price", "target_weight", "annual_yield"]:
        out[col] = out[col].apply(to_float)

    out["ticker"] = out["ticker"].astype(str).str.upper().str.strip()
    out["payout_frequency"] = out["payout_frequency"].astype(str).str.strip()
    out["payout_months"] = out["payout_months"].astype(str).str.strip()
    out["notes"] = out["notes"].astype(str)

    out.loc[out["payout_frequency"] == "", "payout_frequency"] = "monthly"
    out.loc[out["payout_months"] == "", "payout_months"] = "all"

    out = out[out["ticker"] != ""].reset_index(drop=True)
    return out[DEFAULT_COLUMNS]


def get_default_portfolio_df() -> pd.DataFrame:
    return normalize_portfolio_df(pd.DataFrame(DEFAULT_ROWS, columns=DEFAULT_COLUMNS))


def baseline_state_payload() -> dict:
    return {
        "app_baseline_version": APP_BASELINE_VERSION,
        "portfolio_df": get_default_portfolio_df(),
        "cash_fdrxx": DEFAULT_CASH_FDRXX,
        "total_contributions": DEFAULT_TOTAL_CONTRIBUTIONS,
        "use_live_prices": True,
        "auto_sync_prices": True,
        "last_price_sync": "2026-04-30 07:17:29 AM",
        "last_saved": "",
        "last_deploy_message": "Loaded real Fidelity production baseline.",
        "last_cash_message": f"FDRXX cash baseline: {format_dollars(DEFAULT_CASH_FDRXX)}.",
    }


def normalize_state_payload(raw: dict) -> dict:
    records = raw.get("portfolio_df", raw.get("portfolio", []))
    portfolio_df = normalize_portfolio_df(pd.DataFrame(records)) if records else get_default_portfolio_df()

    return {
        "app_baseline_version": raw.get("app_baseline_version", ""),
        "portfolio_df": portfolio_df,
        "cash_fdrxx": round_money(to_float(raw.get("cash_fdrxx", raw.get("cash", DEFAULT_CASH_FDRXX)), DEFAULT_CASH_FDRXX)),
        "total_contributions": round_money(to_float(raw.get("total_contributions", DEFAULT_TOTAL_CONTRIBUTIONS), DEFAULT_TOTAL_CONTRIBUTIONS)),
        "use_live_prices": bool(raw.get("use_live_prices", True)),
        "auto_sync_prices": bool(raw.get("auto_sync_prices", True)),
        "last_price_sync": str(raw.get("last_price_sync", "")),
        "last_saved": str(raw.get("last_saved", "")),
        "last_deploy_message": str(raw.get("last_deploy_message", "")),
        "last_cash_message": str(raw.get("last_cash_message", "")),
    }


def load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return baseline_state_payload()

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)

        loaded = normalize_state_payload(raw)

        if loaded.get("app_baseline_version") != APP_BASELINE_VERSION:
            migrated = baseline_state_payload()
            migrated["last_deploy_message"] = "Migrated regular app to real production Fidelity snapshot baseline with restored color UI."
            return migrated

        return loaded

    except Exception as exc:
        st.warning(f"Could not read saved state file. Loading production Fidelity baseline. Error: {exc}")
        return baseline_state_payload()


def make_state_payload() -> dict:
    df = normalize_portfolio_df(st.session_state.portfolio_df.copy())
    return {
        "app_baseline_version": APP_BASELINE_VERSION,
        "portfolio_df": df.to_dict(orient="records"),
        "cash_fdrxx": round_money(st.session_state.cash_fdrxx),
        "total_contributions": round_money(st.session_state.total_contributions),
        "use_live_prices": bool(st.session_state.use_live_prices),
        "auto_sync_prices": bool(st.session_state.auto_sync_prices),
        "last_price_sync": str(st.session_state.last_price_sync),
        "last_saved": datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"),
        "last_deploy_message": str(st.session_state.get("last_deploy_message", "")),
        "last_cash_message": str(st.session_state.get("last_cash_message", "")),
    }


def save_state() -> bool:
    try:
        payload = make_state_payload()

        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as src:
                    existing = src.read()
                with open(BACKUP_FILE, "w", encoding="utf-8") as b:
                    b.write(existing)
            except Exception:
                pass

        temp_file = STATE_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(temp_file, STATE_FILE)

        st.session_state.last_saved = payload["last_saved"]
        st.session_state.last_save_error = ""
        return True
    except Exception as exc:
        st.session_state.last_save_error = str(exc)
        return False


def bump_editor_version() -> None:
    st.session_state.editor_version = int(st.session_state.get("editor_version", 0)) + 1


def sync_editor_from_portfolio() -> None:
    st.session_state.editor_df = normalize_portfolio_df(st.session_state.portfolio_df.copy())
    bump_editor_version()


def apply_state_dict(state: dict, message: str = "") -> None:
    st.session_state.portfolio_df = normalize_portfolio_df(state["portfolio_df"])
    st.session_state.editor_df = normalize_portfolio_df(state["portfolio_df"].copy())
    st.session_state.cash_fdrxx = round_money(state["cash_fdrxx"])
    st.session_state.total_contributions = round_money(state["total_contributions"])
    st.session_state.use_live_prices = bool(state.get("use_live_prices", True))
    st.session_state.auto_sync_prices = bool(state.get("auto_sync_prices", True))
    st.session_state.last_price_sync = state.get("last_price_sync", "")
    st.session_state.last_saved = state.get("last_saved", "")
    st.session_state.last_deploy_message = message or state.get("last_deploy_message", "")
    st.session_state.last_cash_message = state.get("last_cash_message", "")
    sync_editor_from_portfolio()


def init_state() -> None:
    if st.session_state.get("app_initialized", False):
        return

    loaded = load_state()

    st.session_state.portfolio_df = normalize_portfolio_df(loaded["portfolio_df"])
    st.session_state.editor_df = normalize_portfolio_df(loaded["portfolio_df"].copy())
    st.session_state.cash_fdrxx = round_money(loaded["cash_fdrxx"])
    st.session_state.total_contributions = round_money(loaded["total_contributions"])
    st.session_state.use_live_prices = bool(loaded.get("use_live_prices", True))
    st.session_state.auto_sync_prices = bool(loaded.get("auto_sync_prices", True))
    st.session_state.last_price_sync = loaded.get("last_price_sync", "")
    st.session_state.last_saved = loaded.get("last_saved", "")
    st.session_state.last_deploy_message = loaded.get("last_deploy_message", "")
    st.session_state.last_cash_message = loaded.get("last_cash_message", "")
    st.session_state.last_save_error = ""
    st.session_state.editor_version = 0
    st.session_state.app_initialized = True

    st.session_state.session_start_payload = make_state_payload()
    save_state()


def is_valid_price(live_price: float, fallback_price: float) -> bool:
    try:
        if live_price is None or pd.isna(live_price) or float(live_price) <= 0:
            return False
        if fallback_price is not None and float(fallback_price) > 0:
            pct_diff = abs(float(live_price) - float(fallback_price)) / float(fallback_price)
            if pct_diff > 0.25:
                return False
        return True
    except Exception:
        return False


@st.cache_data(ttl=900, show_spinner=False)
def get_live_prices_cached(tickers_key: str) -> Dict[str, float]:
    if yf is None:
        return {}

    tickers = [t.strip().upper() for t in tickers_key.split(",") if t.strip()]
    if not tickers:
        return {}

    try:
        unique_tickers = sorted(set(tickers))
        data = yf.download(
            " ".join(unique_tickers),
            period="5d",
            interval="1d",
            auto_adjust=False,
            progress=False,
            group_by="ticker",
            threads=True,
        )

        prices: Dict[str, float] = {}
        if data is None or len(data) == 0:
            return prices

        if len(unique_tickers) == 1:
            ticker = unique_tickers[0]
            if "Close" in data:
                close = data["Close"].dropna()
                if len(close) > 0:
                    prices[ticker] = float(close.iloc[-1])
            return prices

        for ticker in unique_tickers:
            try:
                close = data[ticker]["Close"].dropna()
                if len(close) > 0:
                    prices[ticker] = float(close.iloc[-1])
            except Exception:
                continue

        return prices
    except Exception:
        return {}


def get_live_prices(tickers: List[str]) -> Dict[str, float]:
    cleaned = sorted(set([str(t).upper().strip() for t in tickers if str(t).strip()]))
    return get_live_prices_cached(",".join(cleaned))


def calculate_portfolio(df: pd.DataFrame, cash_fdrxx: float, use_live_prices: bool) -> dict:
    working = normalize_portfolio_df(df)
    tickers = working["ticker"].tolist()
    live_prices = get_live_prices(tickers) if use_live_prices else {}

    working["live_price"] = working["ticker"].map(live_prices).fillna(float("nan"))

    price_used = []
    price_source = []
    for _, row in working.iterrows():
        live = row["live_price"]
        manual = row["manual_price"]
        if is_valid_price(live, manual):
            price_used.append(float(live))
            price_source.append("LIVE")
        else:
            price_used.append(float(manual))
            price_source.append("MANUAL")

    working["price_used"] = price_used
    working["price_source"] = price_source
    working["cost_basis"] = working["qty"] * working["avg_cost"]
    working["market_value"] = working["qty"] * working["price_used"]
    working["gain_loss"] = working["market_value"] - working["cost_basis"]
    working["gain_loss_pct"] = working.apply(
        lambda r: (r["gain_loss"] / r["cost_basis"]) if r["cost_basis"] > 0 else 0.0,
        axis=1,
    )

    working["annual_income_est"] = working["market_value"] * working["annual_yield"]
    working["monthly_income_est"] = working["annual_income_est"] / 12.0

    holdings_market_value = float(working["market_value"].sum())
    holdings_basis = float(working["cost_basis"].sum())
    cash_fdrxx = round_money(cash_fdrxx)
    total_value = holdings_market_value + cash_fdrxx
    total_contributions = round_money(st.session_state.total_contributions)

    total_monthly_actual = float(working["monthly_income_est"].sum())
    total_monthly_realistic = total_monthly_actual * REALISTIC_INCOME_FACTOR
    total_monthly_conservative = total_monthly_actual * CONSERVATIVE_INCOME_FACTOR

    working["current_weight"] = working["market_value"] / holdings_market_value if holdings_market_value > 0 else 0.0
    working["target_weight_decimal"] = working["target_weight"] / 100.0
    working["target_value"] = working["target_weight_decimal"] * holdings_market_value
    working["drift_dollars"] = working["market_value"] - working["target_value"]
    working["drift_pct_points"] = (working["current_weight"] - working["target_weight_decimal"]) * 100.0

    return {
        "df": working,
        "holdings_market_value": holdings_market_value,
        "holdings_cost_basis": holdings_basis,
        "available_cash": cash_fdrxx,
        "total_portfolio_value": total_value,
        "total_contributions": total_contributions,
        "net_vs_contributions": total_value - total_contributions,
        "holdings_gain_loss": holdings_market_value - holdings_basis,
        "monthly_actual": total_monthly_actual,
        "monthly_realistic": total_monthly_realistic,
        "monthly_conservative": total_monthly_conservative,
        "goal_progress": total_monthly_realistic / GOAL_MONTHLY if GOAL_MONTHLY else 0.0,
    }


def refresh_saved_manual_prices(calc_df: pd.DataFrame) -> None:
    if not bool(st.session_state.auto_sync_prices):
        return

    df = normalize_portfolio_df(st.session_state.portfolio_df.copy())
    changed = False

    for _, row in calc_df.iterrows():
        ticker = str(row["ticker"]).upper().strip()
        if str(row.get("price_source", "")) != "LIVE":
            continue

        price = to_float(row.get("price_used", 0.0))
        if price <= 0:
            continue

        mask = df["ticker"] == ticker
        if mask.any():
            old = to_float(df.loc[mask, "manual_price"].iloc[0])
            if abs(old - price) > 0.0001:
                df.loc[mask, "manual_price"] = round(price, 4)
                changed = True

    if changed:
        st.session_state.portfolio_df = normalize_portfolio_df(df)
        st.session_state.editor_df = normalize_portfolio_df(df.copy())
        st.session_state.last_price_sync = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        save_state()


def add_new_money(amount: float) -> None:
    amount = round_money(amount)
    if amount <= 0:
        return

    st.session_state.cash_fdrxx = round_money(st.session_state.cash_fdrxx + amount)
    st.session_state.total_contributions = round_money(st.session_state.total_contributions + amount)
    st.session_state.last_cash_message = f"Added new money: {format_dollars(amount)} to FDRXX."
    save_state()


def set_exact_cash(new_cash: float) -> None:
    old_cash = round_money(st.session_state.cash_fdrxx)
    new_cash = round_money(new_cash)
    difference = round_money(new_cash - old_cash)

    st.session_state.cash_fdrxx = new_cash
    st.session_state.last_cash_message = (
        f"FDRXX cash set exactly to {format_dollars(new_cash)}. "
        f"Adjustment: {format_dollars(difference)}."
    )
    save_state()


def deploy_cash_to_position(ticker: str, dollars: float, calc_df: pd.DataFrame) -> None:
    ticker = str(ticker).upper().strip()
    dollars = round_money(dollars)

    if ticker == "" or dollars <= 0:
        st.error("Enter a valid ticker and dollar amount.")
        return

    available_cash = round_money(st.session_state.cash_fdrxx)
    if dollars > available_cash:
        st.error(f"Not enough FDRXX cash. Available: {format_dollars(available_cash)}")
        return

    df = normalize_portfolio_df(st.session_state.portfolio_df.copy())

    price_lookup = {
        str(row["ticker"]).upper().strip(): to_float(row.get("price_used", 0.0))
        for _, row in calc_df.iterrows()
    }

    price_used = round(to_float(price_lookup.get(ticker, 0.0)), 6)

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
    st.session_state.cash_fdrxx = round_money(available_cash - dollars)
    st.session_state.last_deploy_message = (
        f"Deployment saved: {format_dollars(dollars)} into {ticker} "
        f"at {format_dollars(price_used)}; added {shares_added:,.6f} shares."
    )

    sync_editor_from_portfolio()

    ok = save_state()
    if not ok:
        st.error(f"Deployment changed the screen but DID NOT SAVE. Error: {st.session_state.last_save_error}")


def build_smarter_income_suggestions(df: pd.DataFrame, available_cash: float) -> pd.DataFrame:
    if available_cash <= 0 or df.empty:
        return pd.DataFrame()

    working = df.copy()
    working["ticker"] = working["ticker"].astype(str).str.upper().str.strip()

    eligible_rows = []
    for _, row in working.iterrows():
        ticker = row["ticker"]
        if ticker in SMART_INCOME_TIERS["avoid"]:
            continue
        if to_float(row.get("price_used", 0.0)) <= 0:
            continue
        eligible_rows.append(row)

    if not eligible_rows:
        return pd.DataFrame()

    suggestions = []
    for tier_name, tier_tickers in SMART_INCOME_TIERS.items():
        if tier_name == "avoid":
            continue

        tier_budget = available_cash * SMART_INCOME_SPLITS.get(tier_name, 0.0)
        tier_rows = [r for r in eligible_rows if r["ticker"] in tier_tickers]
        if not tier_rows or tier_budget <= 0:
            continue

        each_budget = tier_budget / len(tier_rows)
        for row in tier_rows:
            ticker = row["ticker"]
            price = to_float(row["price_used"])
            annual_yield = to_float(row["annual_yield"])
            shares = each_budget / price if price > 0 else 0.0
            monthly_income = (each_budget * annual_yield) / 12.0
            suggestions.append(
                {
                    "Ticker": ticker,
                    "Tier": tier_name.replace("_", " ").title(),
                    "Suggested Buy $": each_budget,
                    "Approx Shares": shares,
                    "Price Used": price,
                    "Added Monthly Income": monthly_income,
                }
            )

    return pd.DataFrame(suggestions)


def inject_dashboard_css() -> None:
    st.markdown(
        """
        <style>
        .main .block-container {
            padding-top: 1.1rem;
            padding-bottom: 2rem;
            max-width: 1400px;
        }

        .dashboard-title {
            font-size: 2.25rem;
            font-weight: 900;
            margin-bottom: 0.15rem;
            color: #0f172a;
        }

        .dashboard-subtitle {
            color: #64748b;
            font-size: 1.02rem;
            margin-bottom: 1.0rem;
        }

        .hero-card {
            border-radius: 24px;
            padding: 26px 28px;
            margin: 10px 0 18px 0;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 55%, #334155 100%);
            color: #ffffff !important;
            box-shadow: 0 14px 30px rgba(15, 23, 42, 0.22);
        }

        .hero-card * {
            color: #ffffff !important;
        }

        .hero-label {
            font-size: 0.90rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            opacity: 0.82;
            margin-bottom: 4px;
        }

        .hero-number {
            font-size: 2.7rem;
            font-weight: 900;
            margin: 2px 0 2px 0;
        }

        .hero-small {
            opacity: 0.92;
            font-size: 1.0rem;
            margin-top: 4px;
        }

        .paycheck-bar-wrap {
            margin-top: 18px;
            background: rgba(255,255,255,0.18);
            border-radius: 999px;
            height: 22px;
            overflow: hidden;
        }

        .paycheck-bar-fill {
            height: 22px;
            background: linear-gradient(90deg, #22c55e, #84cc16);
            border-radius: 999px;
        }

        .metric-card {
            border-radius: 18px;
            padding: 18px 18px 16px 18px;
            border: 1px solid rgba(148, 163, 184, 0.35);
            box-shadow: 0 8px 20px rgba(15, 23, 42, 0.07);
            margin-bottom: 12px;
            min-height: 118px;
        }

        .metric-blue {
            background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
        }

        .metric-purple {
            background: linear-gradient(135deg, #faf5ff 0%, #ede9fe 100%);
        }

        .metric-green {
            background: linear-gradient(135deg, #ecfdf5 0%, #dcfce7 100%);
        }

        .metric-amber {
            background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
        }

        .metric-gray {
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
        }

        .metric-label {
            color: #334155 !important;
            font-size: 0.88rem;
            font-weight: 800;
            margin-bottom: 6px;
        }

        .metric-value {
            color: #0f172a !important;
            font-size: 1.55rem;
            font-weight: 900;
            line-height: 1.15;
        }

        .metric-note {
            color: #475569 !important;
            font-size: 0.82rem;
            margin-top: 7px;
        }

        .section-title {
            font-size: 1.35rem;
            font-weight: 900;
            margin-bottom: 2px;
            color: #0f172a;
        }

        .section-subtitle {
            color: #64748b;
            font-size: 0.93rem;
            margin-bottom: 12px;
        }

        .status-pill {
            display: inline-block;
            border-radius: 999px;
            padding: 5px 11px;
            font-size: 0.82rem;
            font-weight: 750;
            background: #ecfdf5;
            color: #047857 !important;
            border: 1px solid #bbf7d0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_card(icon: str, label: str, value: str, note: str = "") -> None:
    label_lower = label.lower()

    if any(word in label_lower for word in ["cash", "fdrxx", "deploy"]):
        tone = "metric-green"
    elif any(word in label_lower for word in ["income", "goal", "conservative", "realistic"]):
        tone = "metric-purple"
    elif any(word in label_lower for word in ["gain", "profit", "loss"]):
        tone = "metric-amber"
    elif any(word in label_lower for word in ["value", "basis", "contribution", "holdings"]):
        tone = "metric-blue"
    else:
        tone = "metric-gray"

    st.markdown(
        f"""
        <div class="metric-card {tone}">
            <div style="font-size:1.25rem;margin-bottom:4px;">{icon}</div>
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(title: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <div class="section-title">{title}</div>
        <div class="section-subtitle">{subtitle}</div>
        """,
        unsafe_allow_html=True,
    )


def render_paycheck_hero(calc: dict) -> None:
    realistic = calc["monthly_realistic"]
    conservative = calc["monthly_conservative"]
    actual = calc["monthly_actual"]
    progress_pct = max(0.0, min(calc["goal_progress"] * 100.0, 100.0))

    st.markdown(
        f"""
        <div class="hero-card">
            <div class="hero-label">Regular Production App</div>
            <div class="hero-number">{format_dollars(realistic)} / {format_dollars(GOAL_MONTHLY)}</div>
            <div class="hero-small">
                Realistic monthly income estimate • {format_percent(progress_pct)} of your goal
            </div>
            <div class="paycheck-bar-wrap">
                <div class="paycheck-bar-fill" style="width: {progress_pct:.1f}%;"></div>
            </div>
            <div class="hero-small" style="margin-top: 14px;">
                🛡️ Conservative: {format_dollars(conservative)} &nbsp;&nbsp;|&nbsp;&nbsp;
                📈 Actual estimate: {format_dollars(actual)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metrics(calc: dict) -> None:
    render_paycheck_hero(calc)

    render_section_header(
        "📊 Account Command Center",
        "Cash, total value, cost basis, and gains are separated clearly."
    )

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        render_card("💼", "Total Account Value", format_dollars(calc["total_portfolio_value"]), "Holdings + FDRXX cash")
    with m2:
        render_card("📈", "Profit / Loss", format_dollars(calc["net_vs_contributions"]), "Total value minus total contributions")
    with m3:
        render_card("📦", "Holdings Value", format_dollars(calc["holdings_market_value"]), "Money currently invested")
    with m4:
        render_card("💰", "Cash Ready (FDRXX)", format_dollars(calc["available_cash"]), "Available dry powder")

    b1, b2, b3, b4 = st.columns(4)
    with b1:
        render_card("🧱", "Total Contributions", format_dollars(calc["total_contributions"]), "Your total money added")
    with b2:
        render_card("📦", "Invested Cost Basis", format_dollars(calc["holdings_cost_basis"]), "Cost basis currently in holdings")
    with b3:
        render_card("🟢", "Holdings Gain / Loss", format_dollars(calc["holdings_gain_loss"]), "Market value minus invested basis")
    with b4:
        render_card("🎯", "Monthly Goal", format_dollars(GOAL_MONTHLY), f"Progress: {format_percent(calc['goal_progress'] * 100.0)}")


def render_top_controls(calc: dict) -> None:
    render_section_header(
        "💰 Cash Command Center",
        "Use this area to match Fidelity cash, update total contributions, or add new money."
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        render_card("💰", "Available Cash (FDRXX)", format_dollars(calc["available_cash"]), "Cash available for deployment")
    with c2:
        render_card("🧱", "Total Contributions", format_dollars(st.session_state.total_contributions), "Your total money added")
    with c3:
        render_card("📦", "Invested Cost Basis", format_dollars(calc["holdings_cost_basis"]), "Cost basis currently in holdings")

    st.markdown("#### Set Exact FDRXX Cash")
    with st.form("exact_cash_form"):
        exact_cash = st.number_input(
            "Exact Fidelity FDRXX Cash",
            min_value=0.0,
            value=float(st.session_state.cash_fdrxx),
            step=100.0,
            format="%.2f",
        )
        set_cash_pressed = st.form_submit_button("Set Exact FDRXX Cash", use_container_width=True)

    if set_cash_pressed:
        set_exact_cash(float(exact_cash))
        st.success("Exact FDRXX cash saved.")
        st.rerun()

    if st.session_state.get("last_cash_message"):
        st.info(st.session_state.last_cash_message)

    st.markdown("#### Total Contributions")
    with st.form("contribution_form"):
        new_total = st.number_input(
            "Total Contributions",
            min_value=0.0,
            value=float(st.session_state.total_contributions),
            step=1000.0,
            format="%.2f",
            help="Deploying cash does NOT change this.",
        )
        saved = st.form_submit_button("Save Total Contributions", use_container_width=True)

    if saved:
        st.session_state.total_contributions = round_money(new_total)
        if save_state():
            st.success("Total contributions saved.")
        st.rerun()

    st.markdown("#### Add New Money to FDRXX")
    cols = st.columns(5)
    quick_amounts = [1000, 5000, 10000, 16000, 32000]
    for i, amt in enumerate(quick_amounts):
        if cols[i].button(f"+ ${amt:,.0f}", use_container_width=True):
            add_new_money(float(amt))
            st.rerun()

    with st.form("custom_cash_form"):
        custom_cash = st.number_input("Custom cash deposit to FDRXX", min_value=0.0, step=500.0, value=0.0, format="%.2f")
        add_custom = st.form_submit_button("Add Custom Deposit", use_container_width=True)

    if add_custom and custom_cash > 0:
        add_new_money(float(custom_cash))
        st.rerun()


def render_deploy_cash(calc: dict) -> None:
    render_section_header(
        "🚀 Deploy Cash Into a Position",
        "Deploying lowers FDRXX cash and raises the selected holding. Total contributions do not change."
    )

    calc_df = calc["df"].copy()
    available_cash = round_money(st.session_state.cash_fdrxx)
    ticker_options = sorted(calc_df["ticker"].astype(str).str.upper().tolist())

    with st.form("deploy_cash_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([1.3, 1.0, 0.9])
        with c1:
            deploy_ticker = st.selectbox("Ticker", options=ticker_options)
        with c2:
            deploy_amount = st.number_input(
                "Amount to Deploy",
                min_value=0.0,
                max_value=available_cash if available_cash > 0 else 0.0,
                value=0.0,
                step=100.0,
                format="%.2f",
            )
        with c3:
            st.write("")
            deploy_pressed = st.form_submit_button("Deploy Cash", use_container_width=True, disabled=available_cash <= 0)

    if deploy_pressed:
        deploy_cash_to_position(deploy_ticker, float(deploy_amount), calc_df)
        st.rerun()

    if st.session_state.get("last_deploy_message"):
        st.success(st.session_state.last_deploy_message)


def render_holdings_editor() -> None:
    render_section_header(
        "🧾 Portfolio Holdings Editor",
        "Manual share edits do NOT move cash. Use Set Exact FDRXX Cash if Fidelity cash needs to match exactly."
    )

    editor_key = f"portfolio_editor_v{st.session_state.get('editor_version', 0)}"

    edited_df = st.data_editor(
        st.session_state.editor_df,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key=editor_key,
        column_config={
            "ticker": st.column_config.TextColumn("Ticker"),
            "qty": st.column_config.NumberColumn("Qty / Shares", format="%.6f"),
            "avg_cost": st.column_config.NumberColumn("Avg Cost", format="$%.6f"),
            "manual_price": st.column_config.NumberColumn("Manual / Fallback Price", format="$%.4f"),
            "target_weight": st.column_config.NumberColumn("Target Weight %", format="%.2f"),
            "annual_yield": st.column_config.NumberColumn("Annual Yield", format="%.4f"),
            "payout_frequency": st.column_config.TextColumn("Payout Frequency"),
            "payout_months": st.column_config.TextColumn("Payout Months"),
            "notes": st.column_config.TextColumn("Notes"),
        },
    )

    if st.button("Save Holdings Changes", use_container_width=True):
        cleaned = normalize_portfolio_df(edited_df)
        st.session_state.portfolio_df = cleaned.copy()
        st.session_state.editor_df = cleaned.copy()
        st.session_state.last_deploy_message = "Holdings table saved from latest visible editor values."

        ok = save_state()
        sync_editor_from_portfolio()

        if ok:
            st.success("Holdings saved permanently.")
        else:
            st.error(f"Could not save holdings. Error: {st.session_state.last_save_error}")

        st.rerun()


def render_breakdowns(calc: dict) -> None:
    df = calc["df"].copy()

    render_section_header(
        "📊 Holdings Breakdown",
        "Detailed position values, gain/loss, income estimate, and target drift."
    )

    display_df = df[
        [
            "ticker", "qty", "avg_cost", "manual_price", "live_price", "price_used",
            "price_source", "cost_basis", "market_value", "gain_loss", "gain_loss_pct",
            "annual_yield", "monthly_income_est", "current_weight", "target_weight", "drift_dollars",
        ]
    ].copy()

    display_df.columns = [
        "Ticker", "Qty", "Avg Cost", "Manual Price", "Live Price", "Price Used", "Source",
        "Cost Basis", "Market Value", "Gain/Loss", "Gain/Loss %",
        "Annual Yield", "Monthly Income", "Current Weight", "Target Weight %", "Drift $",
    ]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Qty": st.column_config.NumberColumn("Qty", format="%.6f"),
            "Avg Cost": st.column_config.NumberColumn("Avg Cost", format="$%.4f"),
            "Manual Price": st.column_config.NumberColumn("Manual Price", format="$%.4f"),
            "Live Price": st.column_config.NumberColumn("Live Price", format="$%.4f"),
            "Price Used": st.column_config.NumberColumn("Price Used", format="$%.4f"),
            "Cost Basis": st.column_config.NumberColumn("Cost Basis", format="$%.2f"),
            "Market Value": st.column_config.NumberColumn("Market Value", format="$%.2f"),
            "Gain/Loss": st.column_config.NumberColumn("Gain/Loss", format="$%.2f"),
            "Gain/Loss %": st.column_config.NumberColumn("Gain/Loss %", format="%.2%"),
            "Annual Yield": st.column_config.NumberColumn("Annual Yield", format="%.4f"),
            "Monthly Income": st.column_config.NumberColumn("Monthly Income", format="$%.2f"),
            "Current Weight": st.column_config.NumberColumn("Current Weight", format="%.2%"),
            "Target Weight %": st.column_config.NumberColumn("Target Weight %", format="%.2f"),
            "Drift $": st.column_config.NumberColumn("Drift $", format="$%.2f"),
        },
    )

    render_section_header(
        "💵 Income Breakdown",
        "Estimated monthly and annual income by position."
    )

    income_df = df[["ticker", "market_value", "annual_yield", "monthly_income_est", "annual_income_est"]].copy()
    income_df = income_df.sort_values("monthly_income_est", ascending=False)
    income_df.columns = ["Ticker", "Market Value", "Annual Yield", "Monthly Income", "Annual Income"]

    st.dataframe(
        income_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Market Value": st.column_config.NumberColumn("Market Value", format="$%.2f"),
            "Annual Yield": st.column_config.NumberColumn("Annual Yield", format="%.4f"),
            "Monthly Income": st.column_config.NumberColumn("Monthly Income", format="$%.2f"),
            "Annual Income": st.column_config.NumberColumn("Annual Income", format="$%.2f"),
        },
    )


def render_income_helper(calc: dict) -> None:
    render_section_header(
        "🧭 Suggested Use of Available Cash",
        "Priority rules: SPYI/DIVO first, then QQQI/FEPI, then smaller add-ons."
    )

    suggestions = build_smarter_income_suggestions(calc["df"], calc["available_cash"])

    if suggestions.empty:
        st.info("No cash suggestions right now.")
        return

    st.dataframe(
        suggestions,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Suggested Buy $": st.column_config.NumberColumn("Suggested Buy $", format="$%.2f"),
            "Approx Shares": st.column_config.NumberColumn("Approx Shares", format="%.6f"),
            "Price Used": st.column_config.NumberColumn("Price Used", format="$%.4f"),
            "Added Monthly Income": st.column_config.NumberColumn("Added Monthly Income", format="$%.2f"),
        },
    )


def render_system_tools() -> None:
    render_section_header(
        "🛠️ System Tools",
        "Backup, restore, reload, and safety tools."
    )

    st.warning("Use Download Snapshot Backup before big changes.")

    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("Reverse This Session", use_container_width=True):
            try:
                raw = st.session_state.get("session_start_payload", {})
                state = normalize_state_payload(raw)
                apply_state_dict(state, "Reversed this session back to the state from when the app opened.")
                save_state()
                st.success("Session reversed.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not reverse session: {exc}")

    with c2:
        if st.button("Reload Saved File", use_container_width=True):
            loaded = load_state()
            apply_state_dict(loaded, "Reloaded from saved JSON file.")
            st.rerun()

    with c3:
        if st.button("Save Now", use_container_width=True):
            if save_state():
                st.success("Saved current dashboard state.")
            else:
                st.error(f"Save failed: {st.session_state.last_save_error}")

    st.markdown("#### Snapshot Backup / Restore")

    payload = make_state_payload()
    st.download_button(
        "Download Snapshot Backup",
        data=json.dumps(payload, indent=2),
        file_name=f"retirement_dashboard_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
        use_container_width=True,
    )

    session_payload = st.session_state.get("session_start_payload", {})
    st.download_button(
        "Download Session-Start Backup",
        data=json.dumps(session_payload, indent=2),
        file_name=f"retirement_dashboard_session_start_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
        use_container_width=True,
    )

    uploaded_file = st.file_uploader("Upload Snapshot Backup", type=["json"], key="snapshot_upload")

    if uploaded_file is not None:
        try:
            uploaded_raw = json.loads(uploaded_file.getvalue().decode("utf-8"))
            uploaded_state = normalize_state_payload(uploaded_raw)

            st.info(
                "Uploaded snapshot ready: "
                f"Cash {format_dollars(uploaded_state['cash_fdrxx'])}, "
                f"Total Contributions {format_dollars(uploaded_state['total_contributions'])}."
            )

            if st.button("Restore Uploaded Snapshot", use_container_width=True):
                apply_state_dict(uploaded_state, "Restored from uploaded snapshot backup.")
                save_state()
                st.success("Uploaded snapshot restored.")
                st.rerun()

        except Exception as exc:
            st.error(f"That file could not be restored. Error: {exc}")

    st.markdown("#### Dangerous Reset")

    with st.expander("Reset to Real Fidelity Production Baseline"):
        st.error("Only use this if you want to wipe current numbers back to the uploaded Fidelity snapshot baseline.")
        confirm_reset = st.checkbox("I understand this will reset to the real Fidelity production baseline.")
        if st.button("Reset to Production Baseline", use_container_width=True, disabled=not confirm_reset):
            baseline = baseline_state_payload()
            apply_state_dict(baseline, "Reset to real Fidelity production baseline complete.")
            save_state()
            st.rerun()

    st.caption(f"App version: {APP_BASELINE_VERSION}")
    st.caption(f"Last saved: {st.session_state.get('last_saved', 'not yet') or 'not yet'}")

    if st.session_state.get("last_save_error"):
        st.error(f"Last save error: {st.session_state.last_save_error}")


def main() -> None:
    init_state()
    inject_dashboard_css()

    st.markdown('<div class="dashboard-title">💵 Retirement Paycheck Dashboard</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="dashboard-subtitle">Regular production app • real Fidelity snapshot baseline • exact cash, holdings, restored color UI, and anti-revert save logic.</div>',
        unsafe_allow_html=True,
    )

    settings_cols = st.columns(3)
    with settings_cols[0]:
        st.session_state.use_live_prices = st.checkbox("Use Yahoo Finance live prices", value=bool(st.session_state.use_live_prices))
    with settings_cols[1]:
        st.session_state.auto_sync_prices = st.checkbox("Auto-save good live prices as fallback", value=bool(st.session_state.auto_sync_prices))
    with settings_cols[2]:
        if st.button("Sync Prices Now", use_container_width=True):
            get_live_prices_cached.clear()
            st.session_state.last_price_sync = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            save_state()
            st.rerun()

    calc = calculate_portfolio(
        st.session_state.portfolio_df,
        cash_fdrxx=st.session_state.cash_fdrxx,
        use_live_prices=bool(st.session_state.use_live_prices),
    )

    refresh_saved_manual_prices(calc["df"])

    calc = calculate_portfolio(
        st.session_state.portfolio_df,
        cash_fdrxx=st.session_state.cash_fdrxx,
        use_live_prices=bool(st.session_state.use_live_prices),
    )

    st.markdown(
        f'<span class="status-pill">Last price sync: {st.session_state.last_price_sync or "not yet"}</span>',
        unsafe_allow_html=True,
    )

    render_metrics(calc)
    st.divider()

    render_top_controls(calc)
    st.divider()

    render_deploy_cash(calc)
    st.divider()

    render_holdings_editor()
    st.divider()

    render_breakdowns(calc)
    st.divider()

    render_income_helper(calc)
    st.divider()

    render_system_tools()


if __name__ == "__main__":
    main()
