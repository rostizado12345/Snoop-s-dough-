import math
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except Exception:
    yf = None


# =========================================================
# PAGE SETUP
# =========================================================
st.set_page_config(
    page_title="Retirement Paycheck Dashboard",
    page_icon="💵",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 3rem;
        max-width: 1400px;
    }

    div[data-testid="stMetric"] {
        background: #11182708;
        border: 1px solid #e5e7eb;
        padding: 14px;
        border-radius: 14px;
    }

    .section-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 16px;
        padding: 16px 18px;
        margin-bottom: 14px;
    }

    .big-number {
        font-size: 1.9rem;
        font-weight: 700;
        line-height: 1.1;
    }

    .small-muted {
        color: #6b7280;
        font-size: 0.95rem;
    }

    .goal-box {
        background: #f8fafc;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 14px;
    }

    .good-box {
        background: #ecfdf5;
        border: 1px solid #a7f3d0;
        border-radius: 14px;
        padding: 14px;
    }

    .warn-box {
        background: #fffbeb;
        border: 1px solid #fde68a;
        border-radius: 14px;
        padding: 14px;
    }

    .bad-box {
        background: #fef2f2;
        border: 1px solid #fecaca;
        border-radius: 14px;
        padding: 14px;
    }

    .stButton > button {
        border-radius: 10px;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# DEFAULTS
# =========================================================
GOAL_MONTHLY_DEFAULT = 8000.0
TOTAL_INVESTED_DEFAULT = 295090.0
CONTRIBUTION_TICKER_DEFAULT = "FDRXX"  # Fidelity cash / money market placeholder

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

DEFAULT_ROWS = [
    ["GDXY", 2600.0, 13.50, 15.0, 3.00, 0.0, "monthly", "all", "Primary income"],
    ["CHPY", 300.0, 43.00, 6.0, 3.30, 0.0, "monthly", "all", "Primary income"],
    ["FEPI", 370.0, 52.00, 7.0, 4.80, 0.0, "monthly", "all", "Primary income"],
    ["QQQI", 410.0, 49.00, 10.0, 4.50, 0.0, "monthly", "all", "Primary income"],
    ["AIPI", 430.0, 46.00, 5.0, 4.20, 0.0, "monthly", "all", "Primary income"],
    ["SPYI", 900.0, 48.00, 12.0, 5.60, 0.0, "monthly", "all", "Core income"],
    ["SVOL", 1300.0, 22.00, 6.0, 1.90, 0.0, "monthly", "all", "Stability income"],
    ["DIVO", 850.0, 39.00, 10.0, 1.80, 0.0, "monthly", "all", "Core stabilizer"],
    ["FDRXX", 17000.0, 1.00, 5.0, 0.045, 1.00, "monthly", "all", "Cash reserve"],
]

PAYOUT_MAP = {
    "monthly": 12,
    "quarterly": 4,
    "semiannual": 2,
    "annual": 1,
    "other": 0,
}

MONTH_NAME_MAP = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
    5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
    9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}


# =========================================================
# HELPERS
# =========================================================
def safe_float(value, default=0.0) -> float:
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def normalize_ticker(value: str) -> str:
    if value is None:
        return ""
    return str(value).strip().upper()


def load_default_df() -> pd.DataFrame:
    df = pd.DataFrame(DEFAULT_ROWS, columns=DEFAULT_COLUMNS)
    return df


def init_state() -> None:
    if "positions_df" not in st.session_state:
        st.session_state.positions_df = load_default_df()

    if "goal_monthly" not in st.session_state:
        st.session_state.goal_monthly = GOAL_MONTHLY_DEFAULT

    if "total_invested" not in st.session_state:
        st.session_state.total_invested = TOTAL_INVESTED_DEFAULT

    if "contribution_ticker" not in st.session_state:
        st.session_state.contribution_ticker = CONTRIBUTION_TICKER_DEFAULT

    if "price_cache" not in st.session_state:
        st.session_state.price_cache = {}

    if "last_add_message" not in st.session_state:
        st.session_state.last_add_message = ""


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_prices_from_yfinance(tickers: Tuple[str, ...]) -> Dict[str, float]:
    prices: Dict[str, float] = {}

    if yf is None:
        return prices

    cleaned = [t for t in tickers if t and t.upper() != "FDRXX"]
    if not cleaned:
        return prices

    try:
        joined = " ".join(cleaned)
        data = yf.download(
            tickers=joined,
            period="5d",
            interval="1d",
            auto_adjust=False,
            progress=False,
            group_by="ticker",
            threads=False,
        )

        if data is None or len(data) == 0:
            return prices

        # Multi-ticker download
        if isinstance(data.columns, pd.MultiIndex):
            for ticker in cleaned:
                try:
                    close_series = data[ticker]["Close"].dropna()
                    if len(close_series) > 0:
                        prices[ticker] = float(close_series.iloc[-1])
                except Exception:
                    pass
        else:
            # Single ticker download shape
            try:
                close_series = data["Close"].dropna()
                if len(close_series) > 0 and len(cleaned) == 1:
                    prices[cleaned[0]] = float(close_series.iloc[-1])
            except Exception:
                pass

    except Exception:
        pass

    return prices


def get_position_prices(df: pd.DataFrame) -> Dict[str, float]:
    tickers = []
    for _, row in df.iterrows():
        ticker = normalize_ticker(row.get("ticker", ""))
        manual_price = safe_float(row.get("manual_price", 0.0))
        if ticker:
            if manual_price > 0:
                st.session_state.price_cache[ticker] = manual_price
            tickers.append(ticker)

    tickers_tuple = tuple(sorted(set(tickers)))
    live_prices = fetch_prices_from_yfinance(tickers_tuple)

    for ticker, price in live_prices.items():
        if price > 0:
            st.session_state.price_cache[ticker] = price

    # Make sure FDRXX / cash-like tickers stay at manual price if provided
    prices: Dict[str, float] = {}
    for _, row in df.iterrows():
        ticker = normalize_ticker(row.get("ticker", ""))
        manual_price = safe_float(row.get("manual_price", 0.0))
        if not ticker:
            continue
        if manual_price > 0:
            prices[ticker] = manual_price
        else:
            prices[ticker] = safe_float(st.session_state.price_cache.get(ticker, 0.0), 0.0)

    return prices


def get_month_list_from_text(value: str) -> List[int]:
    if value is None:
        return list(range(1, 13))

    value = str(value).strip().lower()
    if value in ("all", "", "monthly"):
        return list(range(1, 13))

    month_lookup = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4,
        "may": 5, "jun": 6, "jul": 7, "aug": 8,
        "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }

    found = []
    for part in value.replace(" ", "").split(","):
        if part in month_lookup:
            found.append(month_lookup[part])

    return found if found else list(range(1, 13))


def build_analysis_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in DEFAULT_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df["shares"] = pd.to_numeric(df["shares"], errors="coerce").fillna(0.0)
    df["cost_basis_per_share"] = pd.to_numeric(df["cost_basis_per_share"], errors="coerce").fillna(0.0)
    df["target_weight"] = pd.to_numeric(df["target_weight"], errors="coerce").fillna(0.0)
    df["annual_income_per_share"] = pd.to_numeric(df["annual_income_per_share"], errors="coerce").fillna(0.0)
    df["manual_price"] = pd.to_numeric(df["manual_price"], errors="coerce").fillna(0.0)
    df["payout_frequency"] = df["payout_frequency"].astype(str).str.lower().str.strip()
    df["payout_months"] = df["payout_months"].astype(str).str.strip()
    df["notes"] = df["notes"].astype(str)

    prices = get_position_prices(df)

    df["current_price"] = df["ticker"].map(lambda x: safe_float(prices.get(x, 0.0), 0.0))
    df["market_value"] = df["shares"] * df["current_price"]
    df["cost_basis_total"] = df["shares"] * df["cost_basis_per_share"]
    df["position_gain"] = df["market_value"] - df["cost_basis_total"]
    df["annual_income"] = df["shares"] * df["annual_income_per_share"]
    df["monthly_income"] = df["annual_income"] / 12.0

    total_value = max(df["market_value"].sum(), 0.0)
    if total_value > 0:
        df["actual_weight"] = (df["market_value"] / total_value) * 100.0
    else:
        df["actual_weight"] = 0.0

    df["weight_gap"] = df["actual_weight"] - df["target_weight"]

    return df


def monthly_distribution_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for month_num in range(1, 13):
        rows.append({"Month": MONTH_NAME_MAP[month_num], "Estimated Income": 0.0})

    month_df = pd.DataFrame(rows)

    for _, row in df.iterrows():
        annual_income = safe_float(row.get("annual_income", 0.0))
        frequency = str(row.get("payout_frequency", "monthly")).lower().strip()
        payout_months = get_month_list_from_text(row.get("payout_months", "all"))
        ticker = row.get("ticker", "")

        if annual_income <= 0:
            continue

        if frequency == "monthly":
            per_payment = annual_income / 12.0
            for month_num in range(1, 13):
                month_df.loc[month_df["Month"] == MONTH_NAME_MAP[month_num], "Estimated Income"] += per_payment

        elif frequency == "quarterly":
            months = payout_months if payout_months else [3, 6, 9, 12]
            if len(months) == 0:
                months = [3, 6, 9, 12]
            per_payment = annual_income / max(len(months), 1)
            for month_num in months:
                month_df.loc[month_df["Month"] == MONTH_NAME_MAP[month_num], "Estimated Income"] += per_payment

        elif frequency == "semiannual":
            months = payout_months if payout_months else [6, 12]
            per_payment = annual_income / max(len(months), 1)
            for month_num in months:
                month_df.loc[month_df["Month"] == MONTH_NAME_MAP[month_num], "Estimated Income"] += per_payment

        elif frequency == "annual":
            months = payout_months if payout_months else [12]
            per_payment = annual_income / max(len(months), 1)
            for month_num in months:
                month_df.loc[month_df["Month"] == MONTH_NAME_MAP[month_num], "Estimated Income"] += per_payment

        else:
            # Fallback: spread evenly so the app never breaks
            per_payment = annual_income / 12.0
            for month_num in range(1, 13):
                month_df.loc[month_df["Month"] == MONTH_NAME_MAP[month_num], "Estimated Income"] += per_payment

    month_df["Estimated Income"] = month_df["Estimated Income"].round(2)
    return month_df


def add_contribution(amount: float) -> None:
    amount = safe_float(amount, 0.0)
    if amount <= 0:
        return

    st.session_state.total_invested = safe_float(st.session_state.total_invested, 0.0) + amount

    ticker = normalize_ticker(st.session_state.contribution_ticker)
    df = st.session_state.positions_df.copy()

    if ticker == "":
        ticker = CONTRIBUTION_TICKER_DEFAULT
        st.session_state.contribution_ticker = ticker

    if "ticker" not in df.columns:
        df = load_default_df()

    existing_idx = None
    for idx, row in df.iterrows():
        if normalize_ticker(row.get("ticker", "")) == ticker:
            existing_idx = idx
            break

    if existing_idx is not None:
        manual_price = safe_float(df.at[existing_idx, "manual_price"], 0.0)
        current_price = manual_price if manual_price > 0 else 1.0
        added_shares = amount / current_price if current_price > 0 else amount
        df.at[existing_idx, "shares"] = safe_float(df.at[existing_idx, "shares"], 0.0) + added_shares

        if safe_float(df.at[existing_idx, "cost_basis_per_share"], 0.0) <= 0:
            df.at[existing_idx, "cost_basis_per_share"] = current_price

        if safe_float(df.at[existing_idx, "manual_price"], 0.0) <= 0:
            df.at[existing_idx, "manual_price"] = current_price

    else:
        new_row = {
            "ticker": ticker,
            "shares": amount,
            "cost_basis_per_share": 1.00,
            "target_weight": 0.0,
            "annual_income_per_share": 0.045 if ticker == "FDRXX" else 0.0,
            "manual_price": 1.00,
            "payout_frequency": "monthly",
            "payout_months": "all",
            "notes": "Added cash contribution",
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    st.session_state.positions_df = df
    st.session_state.last_add_message = f"Added ${amount:,.0f} to invested amount and to {ticker}."


def format_money(value: float) -> str:
    return f"${value:,.0f}"


def format_money_2(value: float) -> str:
    return f"${value:,.2f}"


def progress_status(progress_pct: float) -> Tuple[str, str]:
    if progress_pct >= 100:
        return "good", "Goal reached"
    if progress_pct >= 75:
        return "good", "Getting close"
    if progress_pct >= 40:
        return "warn", "Building nicely"
    return "bad", "Still early"


# =========================================================
# INIT
# =========================================================
init_state()

st.title("💵 Retirement Paycheck Dashboard")
st.caption("Track income, total invested, gains correctly, and new money added without fake performance inflation.")

# =========================================================
# TOP CONTROLS
# =========================================================
with st.container():
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    left, mid, right = st.columns([1.2, 1.2, 1.0])

    with left:
        st.subheader("Portfolio Settings")
        goal_monthly = st.number_input(
            "Monthly income goal",
            min_value=0.0,
            value=safe_float(st.session_state.goal_monthly, GOAL_MONTHLY_DEFAULT),
            step=100.0,
            key="goal_monthly_input",
        )

        total_invested = st.number_input(
            "Total invested",
            min_value=0.0,
            value=safe_float(st.session_state.total_invested, TOTAL_INVESTED_DEFAULT),
            step=500.0,
            key="total_invested_input",
        )

        st.session_state.goal_monthly = goal_monthly
        st.session_state.total_invested = total_invested

    with mid:
        st.subheader("Quick Add New Money")
        contribution_ticker = st.text_input(
            "Send added money to ticker/cash position",
            value=st.session_state.contribution_ticker,
            key="contribution_ticker_input",
            help="Example: FDRXX for Fidelity cash. These buttons add to Total Invested and also add the amount into that position so it is not treated like fake gain.",
        )
        st.session_state.contribution_ticker = normalize_ticker(contribution_ticker)

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            if st.button("+ $1,000", use_container_width=True):
                add_contribution(1000)
        with c2:
            if st.button("+ $5,000", use_container_width=True):
                add_contribution(5000)
        with c3:
            if st.button("+ $10,000", use_container_width=True):
                add_contribution(10000)
        with c4:
            custom_add = st.number_input(
                "Custom",
                min_value=0.0,
                value=0.0,
                step=500.0,
                key="custom_add_input",
                label_visibility="collapsed",
            )
            if st.button("Add Custom", use_container_width=True):
                add_contribution(custom_add)

        if st.session_state.last_add_message:
            st.success(st.session_state.last_add_message)

    with right:
        st.subheader("Notes")
        st.markdown(
            """
            - New money added here updates **Total Invested**
            - It also adds the same amount into your chosen **cash/ticker position**
            - That keeps contributions from showing up as fake gains
            - You can still manually edit any position below
            """
        )

    st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# POSITIONS EDITOR
# =========================================================
st.subheader("Positions")

editor_help_left, editor_help_right = st.columns([1.5, 1.0])
with editor_help_left:
    st.caption(
        "Edit shares, cost basis, annual income per share, manual price, target weight, payout frequency, and notes directly in the table."
    )
with editor_help_right:
    if st.button("Reset to Default Portfolio", type="secondary"):
        st.session_state.positions_df = load_default_df()
        st.session_state.total_invested = TOTAL_INVESTED_DEFAULT
        st.session_state.goal_monthly = GOAL_MONTHLY_DEFAULT
        st.session_state.last_add_message = "Portfolio reset to default."

positions_df = st.data_editor(
    st.session_state.positions_df,
    use_container_width=True,
    num_rows="dynamic",
    key="positions_editor",
    column_config={
        "ticker": st.column_config.TextColumn("Ticker"),
        "shares": st.column_config.NumberColumn("Shares", format="%.4f"),
        "cost_basis_per_share": st.column_config.NumberColumn("Cost Basis / Share", format="$%.4f"),
        "target_weight": st.column_config.NumberColumn("Target Weight %", format="%.2f"),
        "annual_income_per_share": st.column_config.NumberColumn("Annual Income / Share", format="$%.4f"),
        "manual_price": st.column_config.NumberColumn("Manual Price", format="$%.4f"),
        "payout_frequency": st.column_config.SelectboxColumn(
            "Payout Frequency",
            options=["monthly", "quarterly", "semiannual", "annual", "other"],
        ),
        "payout_months": st.column_config.TextColumn("Payout Months"),
        "notes": st.column_config.TextColumn("Notes", width="medium"),
    },
)

st.session_state.positions_df = positions_df
analysis_df = build_analysis_df(positions_df)

# =========================================================
# SUMMARY METRICS
# =========================================================
portfolio_value = safe_float(analysis_df["market_value"].sum(), 0.0)
annual_income = safe_float(analysis_df["annual_income"].sum(), 0.0)
monthly_income = annual_income / 12.0
goal_monthly = safe_float(st.session_state.goal_monthly, GOAL_MONTHLY_DEFAULT)
goal_annual = goal_monthly * 12.0
total_invested = safe_float(st.session_state.total_invested, TOTAL_INVESTED_DEFAULT)
gain_dollar = portfolio_value - total_invested
gain_pct = (gain_dollar / total_invested * 100.0) if total_invested > 0 else 0.0
progress_pct = (monthly_income / goal_monthly * 100.0) if goal_monthly > 0 else 0.0

status_kind, status_text = progress_status(progress_pct)

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Portfolio Value", format_money_2(portfolio_value))
with m2:
    st.metric("Total Invested", format_money_2(total_invested))
with m3:
    st.metric("Monthly Income", format_money_2(monthly_income))
with m4:
    st.metric("Annual Income", format_money_2(annual_income))

m5, m6, m7, m8 = st.columns(4)
with m5:
    st.metric("Gain / Loss", format_money_2(gain_dollar), f"{gain_pct:,.2f}%")
with m6:
    remaining_monthly = max(goal_monthly - monthly_income, 0.0)
    st.metric("Still Needed to Goal", format_money_2(remaining_monthly))
with m7:
    weighted_yield = (annual_income / portfolio_value * 100.0) if portfolio_value > 0 else 0.0
    st.metric("Portfolio Income Yield", f"{weighted_yield:,.2f}%")
with m8:
    st.metric("Goal Progress", f"{progress_pct:,.1f}%")

st.markdown("### Goal Tracker")
st.progress(min(max(progress_pct / 100.0, 0.0), 1.0))
st.markdown(f"**Goal:** {format_money(goal_monthly)} / month")

if status_kind == "good":
    st.markdown(
        f'<div class="good-box"><strong>{status_text}</strong><br>You are at {progress_pct:,.1f}% of your monthly goal.</div>',
        unsafe_allow_html=True,
    )
elif status_kind == "warn":
    st.markdown(
        f'<div class="warn-box"><strong>{status_text}</strong><br>You are at {progress_pct:,.1f}% of your monthly goal.</div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        f'<div class="bad-box"><strong>{status_text}</strong><br>You are at {progress_pct:,.1f}% of your monthly goal.</div>',
        unsafe_allow_html=True,
    )


# =========================================================
# POSITION BREAKDOWN
# =========================================================
st.subheader("Position Breakdown")

display_df = analysis_df[
    [
        "ticker",
        "shares",
        "current_price",
        "market_value",
        "cost_basis_per_share",
        "cost_basis_total",
        "position_gain",
        "annual_income_per_share",
        "annual_income",
        "monthly_income",
        "target_weight",
        "actual_weight",
        "weight_gap",
        "notes",
    ]
].copy()

display_df = display_df.sort_values("market_value", ascending=False).reset_index(drop=True)

st.dataframe(
    display_df.style.format(
        {
            "shares": "{:,.4f}",
            "current_price": "${:,.4f}",
            "market_value": "${:,.2f}",
            "cost_basis_per_share": "${:,.4f}",
            "cost_basis_total": "${:,.2f}",
            "position_gain": "${:,.2f}",
            "annual_income_per_share": "${:,.4f}",
            "annual_income": "${:,.2f}",
            "monthly_income": "${:,.2f}",
            "target_weight": "{:,.2f}%",
            "actual_weight": "{:,.2f}%",
            "weight_gap": "{:,.2f}%",
        }
    ),
    use_container_width=True,
    hide_index=True,
)


# =========================================================
# REBALANCE HELPER
# =========================================================
st.subheader("Rebalance Helper")

rebal_df = analysis_df[
    ["ticker", "market_value", "target_weight", "actual_weight", "weight_gap"]
].copy()

rebal_df["target_value"] = portfolio_value * (rebal_df["target_weight"] / 100.0)
rebal_df["add_or_trim"] = rebal_df["target_value"] - rebal_df["market_value"]
rebal_df = rebal_df.sort_values("add_or_trim", ascending=False).reset_index(drop=True)

st.caption("Positive numbers mean underweight and candidates to add to. Negative numbers mean overweight.")

st.dataframe(
    rebal_df.style.format(
        {
            "market_value": "${:,.2f}",
            "target_weight": "{:,.2f}%",
            "actual_weight": "{:,.2f}%",
            "weight_gap": "{:,.2f}%",
            "target_value": "${:,.2f}",
            "add_or_trim": "${:,.2f}",
        }
    ),
    use_container_width=True,
    hide_index=True,
)


# =========================================================
# MONTHLY INCOME CALENDAR
# =========================================================
st.subheader("Estimated Monthly Income Calendar")

monthly_table = monthly_distribution_table(analysis_df)

c1, c2 = st.columns([1.1, 1.1])
with c1:
    st.dataframe(
        monthly_table.style.format({"Estimated Income": "${:,.2f}"}),
        use_container_width=True,
        hide_index=True,
    )

with c2:
    chart_df = monthly_table.set_index("Month")
    st.bar_chart(chart_df["Estimated Income"])


# =========================================================
# QUICK READOUT
# =========================================================
st.subheader("Quick Readout")

income_gap = max(goal_annual - annual_income, 0.0)

left, right = st.columns(2)

with left:
    st.markdown(
        f"""
        <div class="section-card">
            <div class="small-muted">Income Snapshot</div>
            <div class="big-number">{format_money_2(monthly_income)} / month</div>
            <div class="small-muted">{format_money_2(annual_income)} / year</div>
            <br>
            <div class="small-muted">Still needed to hit goal</div>
            <div class="big-number">{format_money_2(income_gap / 12.0)} / month</div>
            <div class="small-muted">{format_money_2(income_gap)} / year</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with right:
    gain_color_class = "good-box" if gain_dollar >= 0 else "bad-box"
    st.markdown(
        f"""
        <div class="{gain_color_class}">
            <strong>Performance View</strong><br><br>
            Portfolio value: {format_money_2(portfolio_value)}<br>
            Total invested: {format_money_2(total_invested)}<br>
            Gain / loss: {format_money_2(gain_dollar)} ({gain_pct:,.2f}%)
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# DOWNLOAD SECTION
# =========================================================
st.subheader("Download Current Positions")

csv_data = analysis_df.to_csv(index=False).encode("utf-8")
st.download_button(
    "Download positions CSV",
    data=csv_data,
    file_name="retirement_paycheck_positions.csv",
    mime="text/csv",
    use_container_width=False,
)

st.caption(
    "Tip: For cash additions, keep the contribution ticker as FDRXX so new money goes into cash and does not look like fake performance."
)
