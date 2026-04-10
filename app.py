import math
from datetime import date
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except Exception:
    yf = None

# -----------------------------
# PAGE SETUP
# -----------------------------
st.set_page_config(
    page_title="Retirement Paycheck Dashboard",
    page_icon="💵",
    layout="wide",
)

# -----------------------------
# DEFAULTS
# -----------------------------
GOAL_MONTHLY = 8000.0
DEFAULT_TOTAL_INVESTED = 295090.0

DEFAULT_COLUMNS = [
    "ticker",
    "shares",
    "cost_basis_per_share",
    "target_weight",
    "annual_income_per_share",
    "manual_price",
    "payout_frequency",
    "payout_months",
    "notes",
]

# payout_frequency examples:
# monthly, quarterly, semiannual, annual, none
#
# payout_months examples:
# monthly -> "1,2,3,4,5,6,7,8,9,10,11,12"
# quarterly -> "1,4,7,10"
# custom -> "3,6,9,12"
DEFAULT_ROWS = [
    ["GDXY", 2671.718, 13.20, 15.0, 3.48, 0.0, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Primary income engine"],
    ["CHPY", 900.000, 24.00, 6.0, 1.92, 0.0, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Income sleeve"],
    ["FEPI", 1100.000, 52.00, 7.0, 5.76, 0.0, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Income sleeve"],
    ["QQQI", 1550.000, 20.50, 10.0, 2.28, 0.0, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Income sleeve"],
    ["AIPI", 550.000, 49.00, 5.0, 4.20, 0.0, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Income sleeve"],
    ["SPYI", 1400.000, 47.00, 12.0, 5.52, 0.0, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Core stabilizing income"],
    ["SVOL", 1300.000, 22.50, 6.0, 1.92, 0.0, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Volatility income"],
    ["DIVO", 850.000, 38.00, 10.0, 2.52, 0.0, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Defensive income"],
    ["IYRI", 500.000, 24.00, 5.0, 1.00, 0.0, "quarterly", "3,6,9,12", "REIT diversifier"],
    ["IWMI", 400.000, 31.00, 4.0, 2.40, 0.0, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Small cap income"],
    ["IAU", 300.000, 44.00, 4.0, 0.00, 0.0, "none", "", "Gold hedge"],
    ["MLPI", 250.000, 51.00, 4.0, 3.20, 0.0, "quarterly", "2,5,8,11", "MLP diversifier"],
    ["TLTW", 750.000, 29.00, 7.0, 2.64, 0.0, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Shock absorber income"],
    ["FDRXX", 17000.000, 1.00, 5.0, 0.04, 1.0, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Fidelity cash position"],
]

MONTH_NAME = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
    5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
    9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

FREQUENCY_MAP = {
    "monthly": 12,
    "quarterly": 4,
    "semiannual": 2,
    "annual": 1,
    "none": 0,
}

# -----------------------------
# HELPERS
# -----------------------------
def format_money(value: float) -> str:
    return f"${value:,.2f}"


def safe_float(value, default=0.0) -> float:
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def parse_months(month_text: str) -> List[int]:
    if not month_text:
        return []
    result = []
    for part in str(month_text).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            month_num = int(part)
            if 1 <= month_num <= 12:
                result.append(month_num)
        except Exception:
            pass
    return sorted(list(set(result)))


@st.cache_data(show_spinner=False, ttl=900)
def fetch_prices(tickers: Tuple[str, ...]) -> Dict[str, float]:
    prices: Dict[str, float] = {}

    if yf is None or not tickers:
        return prices

    try:
        cleaned = [t for t in tickers if t and str(t).strip()]
        if not cleaned:
            return prices

        data = yf.download(
            tickers=list(cleaned),
            period="5d",
            interval="1d",
            auto_adjust=False,
            progress=False,
            group_by="ticker",
            threads=True,
        )

        # Multiple tickers
        if isinstance(data.columns, pd.MultiIndex):
            for ticker in cleaned:
                try:
                    series = data[ticker]["Close"].dropna()
                    if not series.empty:
                        prices[ticker] = float(series.iloc[-1])
                except Exception:
                    pass
        else:
            # Single ticker
            try:
                series = data["Close"].dropna()
                if len(cleaned) == 1 and not series.empty:
                    prices[cleaned[0]] = float(series.iloc[-1])
            except Exception:
                pass
    except Exception:
        pass

    return prices


def get_position_price(row: pd.Series, live_prices: Dict[str, float]) -> float:
    ticker = str(row.get("ticker", "")).strip().upper()
    manual_price = safe_float(row.get("manual_price", 0.0), 0.0)

    if manual_price > 0:
        return manual_price

    live_price = live_prices.get(ticker)
    if live_price and live_price > 0:
        return float(live_price)

    # fallback to cost basis if no live/manual price
    return safe_float(row.get("cost_basis_per_share", 0.0), 0.0)


def annual_income_for_row(row: pd.Series) -> float:
    shares = safe_float(row.get("shares", 0.0), 0.0)
    annual_income_per_share = safe_float(row.get("annual_income_per_share", 0.0), 0.0)
    return shares * annual_income_per_share


def monthly_income_schedule(row: pd.Series) -> Dict[int, float]:
    annual_income = annual_income_for_row(row)
    months = parse_months(str(row.get("payout_months", "")))
    frequency = str(row.get("payout_frequency", "monthly")).strip().lower()

    if annual_income <= 0:
        return {m: 0.0 for m in range(1, 13)}

    if frequency == "none":
        return {m: 0.0 for m in range(1, 13)}

    if not months:
        # fallback from frequency
        if frequency == "monthly":
            months = list(range(1, 13))
        elif frequency == "quarterly":
            months = [3, 6, 9, 12]
        elif frequency == "semiannual":
            months = [6, 12]
        elif frequency == "annual":
            months = [12]

    count = len(months)
    if count == 0:
        return {m: 0.0 for m in range(1, 13)}

    amount_per_pay = annual_income / count
    return {m: (amount_per_pay if m in months else 0.0) for m in range(1, 13)}


def initialize_state():
    if "positions_df" not in st.session_state:
        st.session_state.positions_df = pd.DataFrame(DEFAULT_ROWS, columns=DEFAULT_COLUMNS)

    if "total_invested" not in st.session_state:
        st.session_state.total_invested = DEFAULT_TOTAL_INVESTED

    if "contribution_log" not in st.session_state:
        st.session_state.contribution_log = []

    if "show_editor" not in st.session_state:
        st.session_state.show_editor = True


def add_contribution(amount: float):
    amount = float(amount)
    st.session_state.total_invested += amount
    st.session_state.contribution_log.insert(
        0,
        {
            "date": str(date.today()),
            "amount_added": amount,
            "new_total_invested": st.session_state.total_invested,
        },
    )


def build_metrics_table(df: pd.DataFrame, live_prices: Dict[str, float]) -> pd.DataFrame:
    work = df.copy()

    work["ticker"] = work["ticker"].astype(str).str.upper().str.strip()
    work["shares"] = pd.to_numeric(work["shares"], errors="coerce").fillna(0.0)
    work["cost_basis_per_share"] = pd.to_numeric(work["cost_basis_per_share"], errors="coerce").fillna(0.0)
    work["target_weight"] = pd.to_numeric(work["target_weight"], errors="coerce").fillna(0.0)
    work["annual_income_per_share"] = pd.to_numeric(work["annual_income_per_share"], errors="coerce").fillna(0.0)
    work["manual_price"] = pd.to_numeric(work["manual_price"], errors="coerce").fillna(0.0)

    work["price"] = work.apply(lambda row: get_position_price(row, live_prices), axis=1)
    work["market_value"] = work["shares"] * work["price"]
    work["cost_value"] = work["shares"] * work["cost_basis_per_share"]
    work["annual_income"] = work["shares"] * work["annual_income_per_share"]
    work["monthly_income_avg"] = work["annual_income"] / 12.0

    total_value = work["market_value"].sum()
    if total_value > 0:
        work["actual_weight"] = (work["market_value"] / total_value) * 100.0
    else:
        work["actual_weight"] = 0.0

    work["weight_diff"] = work["actual_weight"] - work["target_weight"]
    work["unrealized_gain_loss"] = work["market_value"] - work["cost_value"]

    return work


def build_monthly_income_table(df: pd.DataFrame) -> pd.DataFrame:
    month_totals = {m: 0.0 for m in range(1, 13)}
    rows = []

    for _, row in df.iterrows():
        sched = monthly_income_schedule(row)
        out_row = {"ticker": str(row["ticker"]).upper()}
        for m in range(1, 13):
            out_row[MONTH_NAME[m]] = sched[m]
            month_totals[m] += sched[m]
        out_row["Annual"] = sum(sched.values())
        rows.append(out_row)

    total_row = {"ticker": "TOTAL"}
    for m in range(1, 13):
        total_row[MONTH_NAME[m]] = month_totals[m]
    total_row["Annual"] = sum(month_totals.values())
    rows.append(total_row)

    return pd.DataFrame(rows)


def recommendation_text(metrics_df: pd.DataFrame, cash_available: float) -> pd.DataFrame:
    total_value = metrics_df["market_value"].sum()
    if total_value <= 0:
        return pd.DataFrame(columns=["ticker", "status", "current_weight", "target_weight", "difference", "suggestion"])

    recs = []
    for _, row in metrics_df.iterrows():
        target = safe_float(row["target_weight"])
        current = safe_float(row["actual_weight"])
        diff = current - target

        if diff < -0.75:
            if cash_available > 0:
                suggested_add = total_value * abs(diff) / 100.0
                recs.append(
                    {
                        "ticker": row["ticker"],
                        "status": "Underweight",
                        "current_weight": current,
                        "target_weight": target,
                        "difference": diff,
                        "suggestion": f"Add about {format_money(suggested_add)} over time",
                    }
                )
        elif diff > 5.0:
            recs.append(
                {
                    "ticker": row["ticker"],
                    "status": "Overweight",
                    "current_weight": current,
                    "target_weight": target,
                    "difference": diff,
                    "suggestion": "Only trim if you choose to rebalance aggressively",
                }
            )

    if not recs:
        return pd.DataFrame(
            [
                {
                    "ticker": "-",
                    "status": "Balanced",
                    "current_weight": 0.0,
                    "target_weight": 0.0,
                    "difference": 0.0,
                    "suggestion": "No major rebalance issue right now",
                }
            ]
        )

    rec_df = pd.DataFrame(recs)
    rec_df = rec_df.sort_values(by=["status", "difference"], ascending=[True, True]).reset_index(drop=True)
    return rec_df


# -----------------------------
# INIT
# -----------------------------
initialize_state()

st.title("💵 Retirement Paycheck Dashboard")
st.caption("Income-first portfolio tracker with editable invested amount, cash handling, live prices, and monthly income view.")

# -----------------------------
# SIDEBAR
# -----------------------------
with st.sidebar:
    st.header("Settings")

    goal_monthly = st.number_input(
        "Monthly income goal",
        min_value=0.0,
        value=GOAL_MONTHLY,
        step=100.0,
    )

    use_live_prices = st.toggle("Use live Yahoo Finance prices", value=True)
    st.caption("If a manual price is entered for a ticker, that manual price wins.")

    st.divider()
    st.subheader("Invested amount")
    st.caption("This is your actual money contributed. It is separate from market value so cash additions do not look like fake gains.")

    st.session_state.total_invested = st.number_input(
        "Total invested principal",
        min_value=0.0,
        value=float(st.session_state.total_invested),
        step=100.0,
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("+$1,000", use_container_width=True):
            add_contribution(1000.0)
            st.rerun()
    with c2:
        if st.button("+$5,000", use_container_width=True):
            add_contribution(5000.0)
            st.rerun()
    with c3:
        if st.button("+$10,000", use_container_width=True):
            add_contribution(10000.0)
            st.rerun()

    custom_add = st.number_input("Custom add amount", min_value=0.0, value=0.0, step=100.0)
    if st.button("Add custom amount", use_container_width=True):
        if custom_add > 0:
            add_contribution(custom_add)
            st.rerun()

    if st.button("Reset to default invested amount", use_container_width=True):
        st.session_state.total_invested = DEFAULT_TOTAL_INVESTED
        st.session_state.contribution_log = []
        st.rerun()

    st.divider()
    st.subheader("Portfolio editor")
    st.session_state.show_editor = st.toggle("Show position editor", value=st.session_state.show_editor)

    st.divider()
    if st.button("Restore default positions", use_container_width=True):
        st.session_state.positions_df = pd.DataFrame(DEFAULT_ROWS, columns=DEFAULT_COLUMNS)
        st.rerun()

# -----------------------------
# POSITION EDITOR
# -----------------------------
if st.session_state.show_editor:
    st.subheader("Positions")
    st.caption("You can edit shares, cost basis, target weight, income per share, manual prices, payout months, and notes right here.")

    edited_df = st.data_editor(
        st.session_state.positions_df,
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        column_config={
            "ticker": st.column_config.TextColumn("Ticker"),
            "shares": st.column_config.NumberColumn("Shares", format="%.4f"),
            "cost_basis_per_share": st.column_config.NumberColumn("Cost Basis / Share", format="%.4f"),
            "target_weight": st.column_config.NumberColumn("Target Weight %", format="%.2f"),
            "annual_income_per_share": st.column_config.NumberColumn("Annual Income / Share", format="%.4f"),
            "manual_price": st.column_config.NumberColumn("Manual Price", format="%.4f"),
            "payout_frequency": st.column_config.SelectboxColumn(
                "Payout Frequency",
                options=["monthly", "quarterly", "semiannual", "annual", "none"],
            ),
            "payout_months": st.column_config.TextColumn("Payout Months"),
            "notes": st.column_config.TextColumn("Notes"),
        },
        key="positions_editor",
    )

    # Clean and save editor output
    clean_df = edited_df.copy()
    for col in ["ticker", "payout_frequency", "payout_months", "notes"]:
        clean_df[col] = clean_df[col].fillna("").astype(str)
    for col in ["shares", "cost_basis_per_share", "target_weight", "annual_income_per_share", "manual_price"]:
        clean_df[col] = pd.to_numeric(clean_df[col], errors="coerce").fillna(0.0)
    clean_df["ticker"] = clean_df["ticker"].str.upper().str.strip()

    st.session_state.positions_df = clean_df

# -----------------------------
# LIVE PRICES
# -----------------------------
tickers = tuple(
    sorted(
        set(
            t for t in st.session_state.positions_df["ticker"].astype(str).str.upper().str.strip().tolist()
            if t
        )
    )
)

live_prices: Dict[str, float] = {}
if use_live_prices:
    live_prices = fetch_prices(tickers)

metrics_df = build_metrics_table(st.session_state.positions_df, live_prices)

# -----------------------------
# TOP SUMMARY
# -----------------------------
total_value = float(metrics_df["market_value"].sum())
total_cost_value = float(metrics_df["cost_value"].sum())
total_invested = float(st.session_state.total_invested)
portfolio_gain_loss_vs_invested = total_value - total_invested
portfolio_gain_loss_vs_cost = total_value - total_cost_value

annual_income_total = float(metrics_df["annual_income"].sum())
monthly_income_avg = annual_income_total / 12.0
yield_on_market_value = (annual_income_total / total_value * 100.0) if total_value > 0 else 0.0
yield_on_invested = (annual_income_total / total_invested * 100.0) if total_invested > 0 else 0.0
goal_progress = (monthly_income_avg / goal_monthly * 100.0) if goal_monthly > 0 else 0.0

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Portfolio value", format_money(total_value))
with m2:
    st.metric("Total invested", format_money(total_invested))
with m3:
    st.metric(
        "Gain / loss vs invested",
        format_money(portfolio_gain_loss_vs_invested),
        delta=f"{(portfolio_gain_loss_vs_invested / total_invested * 100.0):.2f}%" if total_invested > 0 else None,
    )
with m4:
    st.metric("Avg monthly income", format_money(monthly_income_avg), delta=f"{goal_progress:.1f}% of goal")

m5, m6, m7, m8 = st.columns(4)
with m5:
    st.metric("Annual income", format_money(annual_income_total))
with m6:
    st.metric("Yield on value", f"{yield_on_market_value:.2f}%")
with m7:
    st.metric("Yield on invested", f"{yield_on_invested:.2f}%")
with m8:
    st.metric("Gain / loss vs cost basis", format_money(portfolio_gain_loss_vs_cost))

# -----------------------------
# HEALTH BAR
# -----------------------------
if monthly_income_avg >= goal_monthly:
    st.success(f"Income goal reached. Estimated average monthly income is {format_money(monthly_income_avg)} against a goal of {format_money(goal_monthly)}.")
elif monthly_income_avg >= goal_monthly * 0.8:
    st.warning(f"Income is getting close. Estimated average monthly income is {format_money(monthly_income_avg)} against a goal of {format_money(goal_monthly)}.")
else:
    st.info(f"Income is below target. Estimated average monthly income is {format_money(monthly_income_avg)} against a goal of {format_money(goal_month
