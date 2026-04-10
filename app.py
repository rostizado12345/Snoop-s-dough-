import math
from typing import Dict, List

import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except Exception:
    yf = None

st.set_page_config(
    page_title="Retirement Paycheck Dashboard",
    page_icon="💵",
    layout="wide",
)

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

DEFAULT_ROWS = [
    ["GDXY", 2671.718, 13.38, 0.15, 2.64, None, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Primary income engine"],
    ["CHPY", 1155.000, 24.25, 0.06, 1.80, None, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Income layer"],
    ["FEPI", 1330.000, 22.40, 0.07, 1.92, None, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Income layer"],
    ["QQQI", 1740.000, 18.90, 0.10, 1.68, None, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Income layer"],
    ["AIPI", 820.000, 39.75, 0.05, 2.10, None, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Primary income engine"],
    ["SPYI", 1350.000, 47.10, 0.12, 5.88, None, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Core priority add"],
    ["SVOL", 1200.000, 22.85, 0.06, 1.92, None, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Volatility income"],
    ["DIVO", 880.000, 38.40, 0.10, 2.40, None, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Core priority add"],
    ["IYRI", 500.000, 24.10, 0.05, 1.12, None, "quarterly", "3,6,9,12", "REIT diversifier"],
    ["IWMI", 620.000, 18.25, 0.04, 1.08, None, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Small cap income"],
    ["IAU", 300.000, 44.00, 0.04, 0.00, None, "none", "", "Gold hedge"],
    ["MLPI", 410.000, 48.15, 0.04, 3.20, None, "quarterly", "2,5,8,11", "MLP income"],
    ["TLTW", 760.000, 26.50, 0.07, 2.88, None, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Shock absorber"],
    ["FDRXX", 17000.000, 1.00, 0.05, 0.045, 1.00, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", "Cash sweep / dry powder"],
]


def safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def safe_text(value, default=""):
    if value is None:
        return default
    return str(value)


def parse_months(text):
    if text is None:
        return []
    text = str(text).strip()
    if not text:
        return []
    months = []
    for part in text.split(","):
        part = part.strip()
        if part.isdigit():
            m = int(part)
            if 1 <= m <= 12:
                months.append(m)
    return sorted(list(set(months)))


def load_default_df():
    return pd.DataFrame(DEFAULT_ROWS, columns=DEFAULT_COLUMNS)


def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    for col in DEFAULT_COLUMNS:
        if col not in df.columns:
            df[col] = None

    df = df[DEFAULT_COLUMNS]

    numeric_cols = [
        "shares",
        "cost_basis_per_share",
        "target_weight",
        "annual_income_per_share",
        "manual_price",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df["payout_frequency"] = df["payout_frequency"].fillna("monthly").astype(str).str.lower().str.strip()
    df["payout_months"] = df["payout_months"].fillna("").astype(str)
    df["notes"] = df["notes"].fillna("").astype(str)

    df = df[df["ticker"] != ""].reset_index(drop=True)
    return df


def get_live_prices(tickers: List[str]) -> Dict[str, float]:
    prices = {}
    if yf is None or not tickers:
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

        if len(clean) == 1:
            ticker = clean[0]
            try:
                px = float(data["Close"].dropna().iloc[-1])
                prices[ticker] = px
            except Exception:
                pass
        else:
            for ticker in clean:
                try:
                    px = float(data[ticker]["Close"].dropna().iloc[-1])
                    prices[ticker] = px
                except Exception:
                    pass
    except Exception:
        return prices

    return prices


def compute_portfolio(df: pd.DataFrame):
    df = df.copy()

    live_prices = get_live_prices(df["ticker"].tolist())
    resolved_prices = []

    for _, row in df.iterrows():
        ticker = row["ticker"]
        manual_price = row["manual_price"]

        if pd.notna(manual_price) and safe_float(manual_price, 0) > 0:
            resolved_prices.append(float(manual_price))
        elif ticker in live_prices:
            resolved_prices.append(float(live_prices[ticker]))
        elif ticker == "FDRXX":
            resolved_prices.append(1.00)
        else:
            resolved_prices.append(float(row["cost_basis_per_share"]) if pd.notna(row["cost_basis_per_share"]) else 0.0)

    df["price"] = resolved_prices
    df["shares"] = df["shares"].fillna(0.0)
    df["cost_basis_per_share"] = df["cost_basis_per_share"].fillna(0.0)
    df["target_weight"] = df["target_weight"].fillna(0.0)
    df["annual_income_per_share"] = df["annual_income_per_share"].fillna(0.0)

    df["market_value"] = df["shares"] * df["price"]
    df["cost_basis_total"] = df["shares"] * df["cost_basis_per_share"]
    df["gain_loss"] = df["market_value"] - df["cost_basis_total"]
    total_value = float(df["market_value"].sum())
    df["actual_weight"] = df["market_value"] / total_value if total_value > 0 else 0.0
    df["annual_income"] = df["shares"] * df["annual_income_per_share"]
    df["monthly_income_est"] = df["annual_income"] / 12.0
    return df


def build_rebalance_table(df: pd.DataFrame, new_money: float):
    rebal = df.copy()
    total_value = float(rebal["market_value"].sum())
    future_total = total_value + float(new_money)

    rebal["target_value_now"] = rebal["target_weight"] * total_value
    rebal["target_value_with_new_money"] = rebal["target_weight"] * future_total
    rebal["current_gap"] = rebal["target_value_now"] - rebal["market_value"]
    rebal["rebalance_dollars"] = rebal["target_value_with_new_money"] - rebal["market_value"]
    rebal["rebalance_dollars"] = rebal["rebalance_dollars"].apply(lambda x: max(0.0, float(x)))
    rebal["shares_to_buy"] = rebal.apply(
        lambda row: (row["rebalance_dollars"] / row["price"]) if row["price"] > 0 else 0.0,
        axis=1,
    )

    total_needed = float(rebal["rebalance_dollars"].sum())
    if total_needed > 0 and new_money > 0:
        scale = min(1.0, new_money / total_needed)
        rebal["buy_now_dollars"] = rebal["rebalance_dollars"] * scale
        rebal["buy_now_shares"] = rebal.apply(
            lambda row: (row["buy_now_dollars"] / row["price"]) if row["price"] > 0 else 0.0,
            axis=1,
        )
    else:
        rebal["buy_now_dollars"] = 0.0
        rebal["buy_now_shares"] = 0.0

    return rebal


def build_monthly_income_calendar(df: pd.DataFrame):
    month_names = {
        1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
        5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
        9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
    }

    rows = []
    for month in range(1, 13):
        total = 0.0
        details = []
        for _, row in df.iterrows():
            months = parse_months(row["payout_months"])
            freq = safe_text(row["payout_frequency"], "monthly").lower()
            annual_income = safe_float(row["annual_income"], 0.0)

            if freq == "none" or annual_income <= 0:
                continue

            if freq == "monthly":
                amt = annual_income / 12.0
                total += amt
                details.append(f'{row["ticker"]}: ${amt:,.0f}')
            elif month in months and len(months) > 0:
                amt = annual_income / len(months)
                total += amt
                details.append(f'{row["ticker"]}: ${amt:,.0f}')

        rows.append({
            "Month": month_names[month],
            "Estimated Income": total,
            "Details": " | ".join(details) if details else "-",
        })

    return pd.DataFrame(rows)


def format_money(x):
    return f"${x:,.0f}"


def format_money_2(x):
    return f"${x:,.2f}"


def priority_bucket(ticker: str) -> str:
    ticker = str(ticker).upper().strip()
    if ticker in ["SPYI", "DIVO"]:
        return "Priority 1"
    if ticker in ["FEPI", "QQQI"]:
        return "Priority 2"
    if ticker in ["SVOL"]:
        return "Priority 3"
    if ticker in ["GDXY", "IAU"]:
        return "Lower priority"
    return "Other"


if "portfolio_df" not in st.session_state:
    st.session_state.portfolio_df = load_default_df()

if "total_invested" not in st.session_state:
    st.session_state.total_invested = DEFAULT_TOTAL_INVESTED

st.title("💵 Retirement Paycheck Dashboard")
st.caption("Income-first portfolio tracker with editable invested amount, live prices, and add-only rebalance helper.")

with st.sidebar:
    st.header("Settings")

    if st.button("Reset portfolio to default"):
        st.session_state.portfolio_df = load_default_df()
        st.session_state.total_invested = DEFAULT_TOTAL_INVESTED
        st.success("Portfolio reset to default values.")

    st.subheader("Portfolio cash flow")
    new_money = st.number_input(
        "New money to deploy",
        min_value=0.0,
        value=0.0,
        step=100.0,
        help="Use this for add-only rebalancing suggestions.",
    )

    st.subheader("Goal")
    goal_monthly = st.number_input(
        "Monthly income goal",
        min_value=0.0,
        value=float(GOAL_MONTHLY),
        step=100.0,
    )

st.subheader("Total invested")
c1, c2 = st.columns([1, 2])

with c1:
    edited_total_invested = st.number_input(
        "Edit total invested amount",
        min_value=0.0,
        value=float(st.session_state.total_invested),
        step=100.0,
        help="Use this to track deposits/additions so cash positions are not treated like gains.",
    )

with c2:
    st.info(
        "This is your money contributed/invested basis for the full portfolio. "
        "Change it here anytime you add money, instead of editing code."
    )

st.session_state.total_invested = float(edited_total_invested)

st.subheader("Positions")
edited_df = st.data_editor(
    st.session_state.portfolio_df,
    num_rows="dynamic",
    use_container_width=True,
    key="portfolio_editor",
    column_config={
        "ticker": st.column_config.TextColumn("Ticker"),
        "shares": st.column_config.NumberColumn("Shares", format="%.4f"),
        "cost_basis_per_share": st.column_config.NumberColumn("Cost Basis/Share", format="%.4f"),
        "target_weight": st.column_config.NumberColumn("Target Weight", format="%.4f"),
        "annual_income_per_share": st.column_config.NumberColumn("Annual Income/Share", format="%.4f"),
        "manual_price": st.column_config.NumberColumn("Manual Price", format="%.4f"),
        "payout_frequency": st.column_config.TextColumn("Payout Frequency"),
        "payout_months": st.column_config.TextColumn("Payout Months"),
        "notes": st.column_config.TextColumn("Notes"),
    },
)

df = normalize_df(pd.DataFrame(edited_df))
st.session_state.portfolio_df = df

portfolio = compute_portfolio(df)

total_value = float(portfolio["market_value"].sum())
total_cost_basis = float(portfolio["cost_basis_total"].sum())
market_gain = total_value - total_cost_basis
net_gain_vs_invested = total_value - float(st.session_state.total_invested)
annual_income = float(portfolio["annual_income"].sum())
monthly_income = annual_income / 12.0
income_goal_pct = (monthly_income / goal_monthly * 100.0) if goal_monthly > 0 else 0.0

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Portfolio Value", format_money(total_value))
m2.metric("Total Invested", format_money(st.session_state.total_invested))
m3.metric("Gain vs Invested", format_money(net_gain_vs_invested))
m4.metric("Est. Monthly Income", format_money(monthly_income))
m5.metric("% of Goal", f"{income_goal_pct:,.1f}%")

with st.expander("Portfolio summary table", expanded=True):
    summary = portfolio.copy()
    summary["Priority"] = summary["ticker"].apply(priority_bucket)
    summary = summary[
        [
            "ticker",
            "shares",
            "price",
            "market_value",
            "cost_basis_total",
            "gain_loss",
            "actual_weight",
            "target_weight",
            "annual_income",
            "monthly_income_est",
            "Priority",
            "notes",
        ]
    ].sort_values(by="market_value", ascending=False)

    styled = summary.copy()
    styled["price"] = styled["price"].map(format_money_2)
    styled["market_value"] = styled["market_value"].map(format_money)
    styled["cost_basis_total"] = styled["cost_basis_total"].map(format_money)
    styled["gain_loss"] = styled["gain_loss"].map(format_money)
    styled["actual_weight"] = styled["actual_weight"].map(lambda x: f"{x*100:,.2f}%")
    styled["target_weight"] = styled["target_weight"].map(lambda x: f"{x*100:,.2f}%")
    styled["annual_income"] = styled["annual_income"].map(format_money)
    styled["monthly_income_est"] = styled["monthly_income_est"].map(format_money)
    st.dataframe(styled, use_container_width=True, hide_index=True)

st.subheader("Add-only rebalance helper")
rebal = build_rebalance_table(portfolio, new_money)

if not rebal.empty:
    rebalance_col = None
    for candidate in [
        "buy_now_dollars",
        "rebalance_dollars",
        "rebalance_amount",
        "rebalance_needed",
        "rebalance_gap",
        "rebalance",
    ]:
        if candidate in rebal.columns:
            rebalance_col = candidate
            break

    if rebalance_col is None:
        st.warning("Could not find a rebalance column in the table.")
        underweights = pd.DataFrame()
    else:
        underweights = rebal[rebal[rebalance_col] > 0].copy()
        underweights = underweights.sort_values(by=rebalance_col, ascending=False)
else:
    underweights = pd.DataFrame()

if new_money <= 0:
    st.info("Enter an amount in 'New money to deploy' in the sidebar to see buy suggestions.")
else:
    if underweights.empty:
        st.success("No underweight positions found based on your target weights.")
    else:
        rebalance_view = underweights[
            [
                "ticker",
                "price",
                "market_value",
                "actual_weight",
                "target_weight",
                "rebalance_dollars",
                "shares_to_buy",
                "buy_now_dollars",
                "buy_now_shares",
            ]
        ].copy()

        rebalance_view["Priority"] = rebalance_view["ticker"].apply(priority_bucket)
        rebalance_view = rebalance_view.sort_values(by="buy_now_dollars", ascending=False)

        shown = rebalance_view.copy()
        shown["price"] = shown["price"].map(format_money_2)
        shown["market_value"] = shown["market_value"].map(format_money)
        shown["actual_weight"] = shown["actual_weight"].map(lambda x: f"{x*100:,.2f}%")
        shown["target_weight"] = shown["target_weight"].map(lambda x: f"{x*100:,.2f}%")
        shown["rebalance_dollars"] = shown["rebalance_dollars"].map(format_money)
        shown["buy_now_dollars"] = shown["buy_now_dollars"].map(format_money)
        shown["shares_to_buy"] = shown["shares_to_buy"].map(lambda x: f"{x:,.4f}")
        shown["buy_now_shares"] = shown["buy_now_shares"].map(lambda x: f"{x:,.4f}")

        st.dataframe(shown, use_container_width=True, hide_index=True)

        top_buys = rebalance_view[rebalance_view["buy_now_dollars"] > 0].head(8)
        if not top_buys.empty:
            bullets = []
            for _, row in top_buys.iterrows():
                bullets.append(
                    f'- {row["ticker"]}: {format_money(row["buy_now_dollars"])} '
                    f'(~{row["buy_now_shares"]:,.2f} shares)'
                )
            st.markdown("**Suggested buys with your new money:**")
            st.markdown("\n".join(bullets))

st.subheader("Income calendar")
calendar_df = build_monthly_income_calendar(portfolio)
calendar_show = calendar_df.copy()
calendar_show["Estimated Income"] = calendar_show["Estimated Income"].map(format_money)
st.dataframe(calendar_show, use_container_width=True, hide_index=True)

st.subheader("Quick health check")
h1, h2, h3 = st.columns(3)

with h1:
    st.markdown("**Income snapshot**")
    st.write(f"Estimated annual income: {format_money(annual_income)}")
    st.write(f"Estimated monthly income: {format_money(monthly_income)}")
    st.write(f"Income goal progress: {income_goal_pct:,.1f}%")

with h2:
    st.markdown("**Portfolio snapshot**")
    st.write(f"Market value: {format_money(total_value)}")
    st.write(f"Cost basis from positions: {format_money(total_cost_basis)}")
    st.write(f"Gain/loss from position basis: {format_money(market_gain)}")

with h3:
    st.markdown("**Tracking snapshot**")
    st.write(f"Manual total invested: {format_money(st.session_state.total_invested)}")
    st.write(f"Gain/loss vs invested: {format_money(net_gain_vs_invested)}")
    st.write("Cash additions should be reflected by editing Total Invested above.")

st.divider()
st.caption(
    "Tip: when you add new money, update 'Total invested amount' so cash contributions "
    "do not look like market gains."
