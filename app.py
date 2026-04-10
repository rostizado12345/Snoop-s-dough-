import math
from datetime import datetime
from io import StringIO
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

# =========================================================
# DEFAULTS
# =========================================================
GOAL_MONTHLY_DEFAULT = 8000.0
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

DEFAULT_ROWS = [
    ["GDXY", 2671.718, 13.98, 0.15, 2.04, 13.98, "Monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Primary income engine"],
    ["CHPY", 1115.000, 24.80, 0.06, 1.92, 24.80, "Monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Income layer"],
    ["FEPI", 1120.000, 54.25, 0.07, 6.60, 54.25, "Monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "High income"],
    ["QQQI", 1550.000, 20.70, 0.10, 2.64, 20.70, "Monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Growth income"],
    ["AIPI", 620.000, 50.00, 0.05, 6.00, 50.00, "Monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "AI income sleeve"],
    ["SPYI", 1675.000, 47.00, 0.12, 5.70, 47.00, "Monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Core income"],
    ["SVOL", 1350.000, 22.00, 0.06, 1.92, 22.00, "Monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Volatility income"],
    ["DIVO", 920.000, 40.00, 0.10, 2.64, 40.00, "Monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Stable income"],
    ["IYRI", 510.000, 26.00, 0.05, 0.92, 26.00, "Quarterly", "3,6,9,12", "REIT diversifier"],
    ["IWMI", 680.000, 18.00, 0.04, 1.56, 18.00, "Monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Small cap income"],
    ["IAU", 250.000, 58.00, 0.04, 0.00, 58.00, "None", "", "Gold hedge"],
    ["MLPI", 375.000, 49.00, 0.04, 3.60, 49.00, "Quarterly", "2,5,8,11", "MLP exposure"],
    ["TLTW", 840.000, 28.00, 0.07, 2.76, 28.00, "Monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Shock absorber income"],
    ["FDRXX", 17000.000, 1.00, 0.05, 0.048, 1.00, "Monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Cash sweep / money market"],
]

MONTH_NAMES = {
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


# =========================================================
# HELPERS
# =========================================================
def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure required columns exist and types are sane."""
    df = df.copy()

    for col in DEFAULT_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    numeric_cols = [
        "shares",
        "cost_basis_per_share",
        "target_weight",
        "annual_income_per_share",
        "manual_price",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    text_cols = ["ticker", "payout_frequency", "payout_months", "notes"]
    for col in text_cols:
        df[col] = df[col].fillna("").astype(str)

    df["ticker"] = df["ticker"].str.upper().str.strip()
    df = df[df["ticker"] != ""].reset_index(drop=True)

    return df[DEFAULT_COLUMNS]


def parse_months(month_text: str) -> List[int]:
    if not month_text or str(month_text).strip() == "":
        return []
    out = []
    for part in str(month_text).split(","):
        part = part.strip()
        if part.isdigit():
            m = int(part)
            if 1 <= m <= 12:
                out.append(m)
    return sorted(list(set(out)))


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_prices_yahoo(tickers: List[str]) -> Dict[str, float]:
    """Fetch latest prices from Yahoo when available."""
    results: Dict[str, float] = {}

    if yf is None:
        return results

    cleaned = [t for t in tickers if t and t.upper() not in ["CASH", "FDRXX", "SPAXX"]]
    if not cleaned:
        return results

    try:
        data = yf.download(
            tickers=cleaned,
            period="5d",
            interval="1d",
            group_by="ticker",
            auto_adjust=False,
            progress=False,
            threads=True,
        )

        if len(cleaned) == 1:
            ticker = cleaned[0]
            if isinstance(data, pd.DataFrame) and "Close" in data.columns and not data.empty:
                val = data["Close"].dropna()
                if not val.empty:
                    results[ticker] = float(val.iloc[-1])
            return results

        for ticker in cleaned:
            try:
                if ticker in data and "Close" in data[ticker]:
                    series = data[ticker]["Close"].dropna()
                    if not series.empty:
                        results[ticker] = float(series.iloc[-1])
            except Exception:
                pass

    except Exception:
        pass

    return results


def safe_price_for_row(row: pd.Series, yahoo_prices: Dict[str, float]) -> Tuple[float, str]:
    ticker = str(row["ticker"]).upper().strip()
    manual = float(row["manual_price"] or 0.0)

    if ticker in ["FDRXX", "SPAXX", "CASH"]:
        return (manual if manual > 0 else 1.0), "Manual"

    if ticker in yahoo_prices and yahoo_prices[ticker] > 0:
        return float(yahoo_prices[ticker]), "Yahoo"

    return (manual if manual > 0 else 0.0), "Manual"


def add_computed_columns(df: pd.DataFrame, yahoo_prices: Dict[str, float]) -> pd.DataFrame:
    df = df.copy()

    prices = []
    sources = []
    for _, row in df.iterrows():
        p, src = safe_price_for_row(row, yahoo_prices)
        prices.append(p)
        sources.append(src)

    df["live_price"] = prices
    df["price_source"] = sources
    df["market_value"] = df["shares"] * df["live_price"]
    df["cost_basis_total"] = df["shares"] * df["cost_basis_per_share"]
    df["position_income_annual"] = df["shares"] * df["annual_income_per_share"]
    df["position_income_monthly"] = df["position_income_annual"] / 12.0

    total_market = float(df["market_value"].sum())
    if total_market > 0:
        df["actual_weight"] = df["market_value"] / total_market
    else:
        df["actual_weight"] = 0.0

    df["weight_gap"] = df["actual_weight"] - df["target_weight"]
    return df


def estimate_monthly_schedule(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for month_num in range(1, 13):
        month_total = 0.0
        details = []

        for _, row in df.iterrows():
            months = parse_months(row["payout_months"])
            if month_num in months:
                monthly_piece = 0.0
                if row["payout_frequency"].lower() == "monthly":
                    monthly_piece = float(row["position_income_annual"]) / 12.0
                elif row["payout_frequency"].lower() == "quarterly":
                    monthly_piece = float(row["position_income_annual"]) / 4.0
                elif row["payout_frequency"].lower() == "semiannual":
                    monthly_piece = float(row["position_income_annual"]) / 2.0
                elif row["payout_frequency"].lower() == "annual":
                    monthly_piece = float(row["position_income_annual"])

                if monthly_piece > 0:
                    month_total += monthly_piece
                    details.append(f'{row["ticker"]}: ${monthly_piece:,.0f}')

        rows.append(
            {
                "Month": MONTH_NAMES[month_num],
                "Estimated Income": month_total,
                "Notes": " | ".join(details[:6]) + (" ..." if len(details) > 6 else ""),
            }
        )

    return pd.DataFrame(rows)


def tiered_income(annual_income: float) -> Dict[str, float]:
    """
    Realistic tiers.
    Safe = 75% of modeled
    Middle = 90% of modeled
    Actual = 100% of modeled
    """
    return {
        "safe_monthly": annual_income * 0.75 / 12.0,
        "middle_monthly": annual_income * 0.90 / 12.0,
        "actual_monthly": annual_income / 12.0,
        "safe_annual": annual_income * 0.75,
        "middle_annual": annual_income * 0.90,
        "actual_annual": annual_income,
    }


def rebalance_plan(df: pd.DataFrame, add_amount: float) -> pd.DataFrame:
    """
    Uses new money only.
    Sends money first to most underweight positions.
    """
    if add_amount <= 0 or df.empty:
        return pd.DataFrame(columns=["ticker", "current_weight", "target_weight", "dollars_to_add"])

    working = df.copy().sort_values("weight_gap")
    remaining = add_amount
    allocations = []

    underweights = working[working["weight_gap"] < 0].copy()
    if underweights.empty:
        return pd.DataFrame(columns=["ticker", "current_weight", "target_weight", "dollars_to_add"])

    total_need = (-underweights["weight_gap"]).sum()
    if total_need <= 0:
        return pd.DataFrame(columns=["ticker", "current_weight", "target_weight", "dollars_to_add"])

    for _, row in underweights.iterrows():
        share = float((-row["weight_gap"]) / total_need)
        dollars = remaining * share
        allocations.append(
            {
                "ticker": row["ticker"],
                "current_weight": row["actual_weight"],
                "target_weight": row["target_weight"],
                "dollars_to_add": dollars,
            }
        )

    out = pd.DataFrame(allocations).sort_values("dollars_to_add", ascending=False).reset_index(drop=True)
    return out


def df_to_csv_download(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def money(x: float) -> str:
    return f"${x:,.2f}"


def pct(x: float) -> str:
    return f"{x * 100:,.2f}%"


# =========================================================
# SESSION STATE
# =========================================================
if "portfolio_df" not in st.session_state:
    st.session_state.portfolio_df = clean_dataframe(pd.DataFrame(DEFAULT_ROWS, columns=DEFAULT_COLUMNS))

if "total_invested" not in st.session_state:
    st.session_state.total_invested = DEFAULT_TOTAL_INVESTED

if "goal_monthly" not in st.session_state:
    st.session_state.goal_monthly = GOAL_MONTHLY_DEFAULT

if "new_money_helper" not in st.session_state:
    st.session_state.new_money_helper = 1000.0

if "last_refresh_time" not in st.session_state:
    st.session_state.last_refresh_time = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")


# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.header("Dashboard Controls")

    if st.button("Refresh Prices"):
        st.cache_data.clear()
        st.session_state.last_refresh_time = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        st.rerun()

    st.caption(f"Last refresh: {st.session_state.last_refresh_time}")

    st.subheader("Invested Amount")
    st.session_state.total_invested = st.number_input(
        "Total money added / invested",
        min_value=0.0,
        value=float(st.session_state.total_invested),
        step=100.0,
        help="This is your contribution tracker. Add new money here so it does not show up as fake profit.",
    )

    c1, c2, c3 = st.columns(3)
    if c1.button("+$1,000"):
        st.session_state.total_invested += 1000.0
        st.rerun()
    if c2.button("+$5,000"):
        st.session_state.total_invested += 5000.0
        st.rerun()
    if c3.button("+$10,000"):
        st.session_state.total_invested += 10000.0
        st.rerun()

    st.subheader("Goal")
    st.session_state.goal_monthly = st.number_input(
        "Monthly income goal",
        min_value=0.0,
        value=float(st.session_state.goal_monthly),
        step=100.0,
    )

    st.subheader("Import / Export")
    upload = st.file_uploader("Import holdings CSV", type=["csv"])
    if upload is not None:
        try:
            imported = pd.read_csv(upload)
            st.session_state.portfolio_df = clean_dataframe(imported)
            st.success("Holdings imported.")
            st.rerun()
        except Exception as e:
            st.error(f"Could not import CSV: {e}")

    st.download_button(
        "Download holdings CSV",
        data=df_to_csv_download(st.session_state.portfolio_df),
        file_name="retirement_dashboard_holdings.csv",
        mime="text/csv",
    )

    st.markdown("---")
    st.subheader("About")
    st.info(
        "This app tracks your portfolio value, income estimates, cash positions, "
        "and contribution-adjusted gain/loss. New money should be added to "
        "'Total money added / invested' so it is not counted as market profit."
    )


# =========================================================
# MAIN DATA
# =========================================================
base_df = clean_dataframe(st.session_state.portfolio_df)

tickers = base_df["ticker"].tolist()
yahoo_prices = fetch_prices_yahoo(tickers)
df = add_computed_columns(base_df, yahoo_prices)

total_market_value = float(df["market_value"].sum())
total_cost_basis_positions = float(df["cost_basis_total"].sum())
total_invested = float(st.session_state.total_invested)
portfolio_gain_vs_invested = total_market_value - total_invested
portfolio_gain_vs_cost_basis = total_market_value - total_cost_basis_positions
annual_income_total = float(df["position_income_annual"].sum())
income = tiered_income(annual_income_total)
goal_monthly = float(st.session_state.goal_monthly)
income_gap = income["middle_monthly"] - goal_monthly if goal_monthly else income["middle_monthly"]
progress_to_goal = (income["middle_monthly"] / goal_monthly) if goal_monthly > 0 else 0.0


# =========================================================
# HEADER
# =========================================================
st.title("💵 Retirement Paycheck Dashboard")
st.caption("Built to separate added money from real gains, and make the app editable without touching code.")

# =========================================================
# TOP METRICS
# =========================================================
m1, m2, m3, m4, m5 = st.columns(5)

m1.metric("Portfolio Value", money(total_market_value))
m2.metric("Total Invested", money(total_invested))
m3.metric(
    "Gain / Loss vs Invested",
    money(portfolio_gain_vs_invested),
    delta=f'{portfolio_gain_vs_invested / total_invested * 100:,.2f}%' if total_invested > 0 else None,
)
m4.metric("Middle Monthly Income", money(income["middle_monthly"]))
m5.metric(
    "Goal Progress",
    pct(progress_to_goal) if goal_monthly > 0 else "N/A",
    delta=money(income_gap),
)

r1, r2, r3 = st.columns(3)
r1.metric("Safe Monthly", money(income["safe_monthly"]))
r2.metric("Actual Monthly", money(income["actual_monthly"]))
r3.metric("Gain / Loss vs Position Cost Basis", money(portfolio_gain_vs_cost_basis))


# =========================================================
# TABS
# =========================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "Overview",
        "Edit Holdings",
        "Income Calendar",
        "Rebalance Helper",
        "Raw Data",
    ]
)

# =========================================================
# TAB 1 - OVERVIEW
# =========================================================
with tab1:
    st.subheader("Position Summary")

    overview_df = df[
        [
            "ticker",
            "shares",
            "live_price",
            "price_source",
            "market_value",
            "target_weight",
            "actual_weight",
            "weight_gap",
            "position_income_monthly",
            "position_income_annual",
            "notes",
        ]
    ].copy()

    overview_df = overview_df.sort_values("market_value", ascending=False).reset_index(drop=True)

    display_df = overview_df.copy()
    display_df["shares"] = display_df["shares"].map(lambda x: f"{x:,.3f}")
    display_df["live_price"] = display_df["live_price"].map(money)
    display_df["market_value"] = display_df["market_value"].map(money)
    display_df["target_weight"] = display_df["target_weight"].map(pct)
    display_df["actual_weight"] = display_df["actual_weight"].map(pct)
    display_df["weight_gap"] = display_df["weight_gap"].map(pct)
    display_df["position_income_monthly"] = display_df["position_income_monthly"].map(money)
    display_df["position_income_annual"] = display_df["position_income_annual"].map(money)

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    st.subheader("What the numbers mean")
    st.write(
        f"""
- **Portfolio Value** = current market value of all positions
- **Total Invested** = money you have added to the portfolio
- **Gain / Loss vs Invested** = Portfolio Value minus Total Invested
- This is the fix that keeps a new cash contribution from pretending to be a gain
        """
    )

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Top Income Positions")
        top_income = df[["ticker", "position_income_annual", "position_income_monthly"]].copy()
        top_income = top_income.sort_values("position_income_annual", ascending=False).head(10)
        top_income["position_income_annual"] = top_income["position_income_annual"].map(money)
        top_income["position_income_monthly"] = top_income["position_income_monthly"].map(money)
        st.dataframe(top_income, use_container_width=True, hide_index=True)

    with c2:
        st.subheader("Most Underweight")
        underweight = df[["ticker", "actual_weight", "target_weight", "weight_gap", "market_value"]].copy()
        underweight = underweight.sort_values("weight_gap").head(10)
        underweight["actual_weight"] = underweight["actual_weight"].map(pct)
        underweight["target_weight"] = underweight["target_weight"].map(pct)
        underweight["weight_gap"] = underweight["weight_gap"].map(pct)
        underweight["market_value"] = underweight["market_value"].map(money)
        st.dataframe(underweight, use_container_width=True, hide_index=True)


# =========================================================
# TAB 2 - EDIT HOLDINGS
# =========================================================
with tab2:
    st.subheader("Edit Holdings Inside the App")

    st.write(
        "You can change shares, cost basis, target weight, annual income per share, manual price, payout months, and notes here."
    )

    edited = st.data_editor(
        st.session_state.portfolio_df,
        use_container_width=True,
        num_rows="dynamic",
        hide_index=True,
        column_config={
            "ticker": st.column_config.TextColumn("Ticker"),
            "shares": st.column_config.NumberColumn("Shares", format="%.6f"),
            "cost_basis_per_share": st.column_config.NumberColumn("Cost Basis / Share", format="%.4f"),
            "target_weight": st.column_config.NumberColumn("Target Weight", format="%.4f"),
            "annual_income_per_share": st.column_config.NumberColumn("Annual Income / Share", format="%.4f"),
            "manual_price": st.column_config.NumberColumn("Manual Price", format="%.4f"),
            "payout_frequency": st.column_config.SelectboxColumn(
                "Payout Frequency",
                options=["None", "Monthly", "Quarterly", "Semiannual", "Annual"],
            ),
            "payout_months": st.column_config.TextColumn("Payout Months"),
            "notes": st.column_config.TextColumn("Notes"),
        },
        key="holdings_editor",
    )

    b1, b2, b3 = st.columns(3)
    if b1.button("Save Holdings Changes"):
        st.session_state.portfolio_df = clean_dataframe(pd.DataFrame(edited))
        st.success("Holdings updated.")
        st.rerun()

    if b2.button("Reset to Default Demo Data"):
        st.session_state.portfolio_df = clean_dataframe(pd.DataFrame(DEFAULT_ROWS, columns=DEFAULT_COLUMNS))
        st.success("Reset to defaults.")
        st.rerun()

    if b3.button("Add FDRXX Cash Row"):
        current = clean_dataframe(st.session_state.portfolio_df)
        new_row = pd.DataFrame(
            [
                {
                    "ticker": "FDRXX",
                    "shares": 0.0,
                    "cost_basis_per_share": 1.0,
                    "target_weight": 0.00,
                    "annual_income_per_share": 0.048,
                    "manual_price": 1.0,
                    "payout_frequency": "Monthly",
                    "payout_months": "1,2,3,4,5,6,7,8,9,10,11,12",
                    "notes": "Cash sweep / money market",
                }
            ]
        )
        st.session_state.portfolio_df = clean_dataframe(pd.concat([current, new_row], ignore_index=True))
        st.success("FDRXX row added.")
        st.rerun()

    st.markdown("---")
    st.subheader("Quick Rule")
    st.write(
        "When you add fresh money, increase **Total money added / invested** in the sidebar. "
        "If that money is sitting in cash like FDRXX, also increase the FDRXX shares so the value matches."
    )


# =========================================================
# TAB 3 - INCOME CALENDAR
# =========================================================
with tab3:
    st.subheader("Estimated Monthly Income Calendar")

    calendar_df = estimate_monthly_schedule(df)
    cal_display = calendar_df.copy()
    cal_display["Estimated Income"] = cal_display["Estimated Income"].map(money)
    st.dataframe(cal_display, use_container_width=True, hide_index=True)

    best_month = calendar_df.loc[calendar_df["Estimated Income"].idxmax()]
    worst_month = calendar_df.loc[calendar_df["Estimated Income"].idxmin()]

    c1, c2 = st.columns(2)
    c1.metric("Best Income Month", f'{best_month["Month"]} - {money(float(best_month["Estimated Income"]))}')
    c2.metric("Lowest Income Month", f'{worst_month["Month"]} - {money(float(worst_month["Estimated Income"]))}')


# =========================================================
# TAB 4 - REBALANCE HELPER
# =========================================================
with tab4:
    st.subheader("Rebalance Helper")
    st.write("This uses new money only. No selling required.")

    st.session_state.new_money_helper = st.number_input(
        "New money to deploy",
        min_value=0.0,
        value=float(st.session_state.new_money_helper),
        step=100.0,
        key="rebalance_input",
    )

    rc1, rc2, rc3 = st.columns(3)
    if rc1.button("Use $1,000"):
        st.session_state.new_money_helper = 1000.0
        st.rerun()
    if rc2.button("Use $5,000"):
        st.session_state.new_money_helper = 5000.0
        st.rerun()
    if rc3.button("Use $10,000"):
        st.session_state.new_money_helper = 10000.0
        st.rerun()

    plan_df = rebalance_plan(df, st.session_state.new_money_helper)

    if plan_df.empty:
        st.info("No rebalance suggestion available.")
    else:
        show_plan = plan_df.copy()
        show_plan["current_weight"] = show_plan["current_weight"].map(pct)
        show_plan["target_weight"] = show_plan["target_weight"].map(pct)
        show_plan["dollars_to_add"] = show_plan["dollars_to_add"].map(money)
        st.dataframe(show_plan, use_container_width=True, hide_index=True)

        st.write("Priority goes to the most underweight positions first.")


# =========================================================
# TAB 5 - RAW DATA
# =========================================================
with tab5:
    st.subheader("Raw Working Data")
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Snapshot")
    st.json(
        {
            "portfolio_value": round(total_market_value, 2),
            "total_invested": round(total_invested, 2),
            "gain_vs_invested": round(portfolio_gain_vs_invested, 2),
            "gain_vs_cost_basis": round(portfolio_gain_vs_cost_basis, 2),
            "annual_income_total": round(annual_income_total, 2),
            "safe_monthly": round(income["safe_monthly"], 2),
            "middle_monthly": round(income["middle_monthly"], 2),
            "actual_monthly": round(income["actual_monthly"], 2),
        }
    )
