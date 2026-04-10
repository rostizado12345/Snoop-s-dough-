
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

GOAL_MONTHLY = 8000
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
    ["GDXY", 2671.718, 13.25, 0.15, 3.00, "", "monthly", "all", "Primary income engine"],
    ["CHPY", 315.648, 56.08, 0.06, 3.36, "", "monthly", "all", "Primary income engine"],
    ["FEPI", 369.674, 39.90, 0.07, 4.80, "", "monthly", "all", "Primary income engine"],
    ["QQQI", 413.413, 49.95, 0.10, 4.56, "", "monthly", "all", "Primary income engine"],
    ["AIPI", 433.250, 34.05, 0.05, 4.20, "", "monthly", "all", "Primary income engine"],
    ["SPYI", 895.295, 49.43, 0.12, 5.64, "", "monthly", "all", "Core stabilizer"],
    ["SVOL", 1338.302, 15.43, 0.06, 1.92, "", "monthly", "all", "Core stabilizer"],
    ["DIVO", 853.930, 44.91, 0.10, 1.80, "", "quarterly", "3,6,9,12", "Core stabilizer"],
    ["IYRI", 314.264, 46.93, 0.05, 1.56, "", "quarterly", "3,6,9,12", "Diversifier"],
    ["IWMI", 247.328, 47.71, 0.04, 2.64, "", "monthly", "all", "Diversifier"],
    ["IAU", 141.249, 83.54, 0.04, 0.00, "", "none", "", "Gold hedge"],
    ["MLPI", 206.257, 57.21, 0.04, 3.60, "", "quarterly", "2,5,8,11", "Diversifier"],
    ["TLTW", 918.594, 22.48, 0.07, 2.64, "", "monthly", "all", "Shock absorber"],
    ["FDRXX", 17700.220, 1.00, 0.05, 0.045, 1.00, "monthly", "all", "Cash core / manual price"],
]


def load_default_df() -> pd.DataFrame:
    return pd.DataFrame(DEFAULT_ROWS, columns=DEFAULT_COLUMNS)


@st.cache_data(ttl=900)
def fetch_market_data(tickers: tuple[str, ...]) -> pd.DataFrame:
    if yf is None or not tickers:
        return pd.DataFrame(columns=["ticker", "price", "prev_close"])

    records = []
    for ticker in tickers:
        try:
            tk = yf.Ticker(ticker)
            info = tk.fast_info
            price = info.get("lastPrice") or info.get("regularMarketPrice")
            prev_close = info.get("previousClose")
            if price is None:
                hist = tk.history(period="5d")
                if not hist.empty:
                    price = float(hist["Close"].iloc[-1])
                    prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else price
            records.append({"ticker": ticker, "price": price, "prev_close": prev_close})
        except Exception:
            records.append({"ticker": ticker, "price": None, "prev_close": None})
    return pd.DataFrame(records)


MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def parse_months(text: str) -> List[int]:
    if not isinstance(text, str) or not text.strip():
        return []
    val = text.strip().lower()
    if val == "all":
        return list(range(1, 13))
    months = []
    for piece in val.split(","):
        piece = piece.strip()
        if piece.isdigit():
            num = int(piece)
            if 1 <= num <= 12:
                months.append(num)
    return sorted(set(months))


def distribute_income(row: pd.Series) -> Dict[int, float]:
    annual = float(row.get("estimated_annual_income", 0) or 0)
    freq = str(row.get("payout_frequency", "monthly") or "monthly").strip().lower()
    months = parse_months(str(row.get("payout_months", "all") or "all"))
    if annual <= 0:
        return {m: 0.0 for m in range(1, 13)}
    if freq == "none":
        return {m: 0.0 for m in range(1, 13)}
    if not months:
        months = list(range(1, 13)) if freq == "monthly" else [3, 6, 9, 12]
    per_month = annual / len(months)
    out = {m: 0.0 for m in range(1, 13)}
    for m in months:
        out[m] += per_month
    return out


def build_portfolio(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    for col in ["shares", "cost_basis_per_share", "target_weight", "annual_income_per_share", "manual_price"]:
        work[col] = pd.to_numeric(work[col], errors="coerce")

    work["ticker"] = work["ticker"].astype(str).str.upper().str.strip()
    market_tickers = tuple(sorted([t for t in work["ticker"].dropna().unique() if t and t != "FDRXX"]))
    market = fetch_market_data(market_tickers)
    work = work.merge(market, on="ticker", how="left")
    work["used_price"] = work["manual_price"].where(
        work["manual_price"].notna() & (work["manual_price"] > 0),
        work["price"],
    )
    work["used_price"] = work["used_price"].fillna(0)
    work["prev_close"] = work["prev_close"].fillna(work["used_price"])
    work["market_value"] = work["shares"].fillna(0) * work["used_price"]
    work["cost_total"] = work["shares"].fillna(0) * work["cost_basis_per_share"].fillna(0)
    work["gain_loss"] = work["market_value"] - work["cost_total"]
    work["day_change_value"] = work["shares"].fillna(0) * (work["used_price"] - work["prev_close"])
    total_value = float(work["market_value"].sum())
    work["actual_weight"] = work["market_value"] / total_value if total_value else 0
    work["weight_gap"] = work["actual_weight"] - work["target_weight"].fillna(0)
    work["target_value"] = work["target_weight"].fillna(0) * total_value
    work["rebalance_delta_value"] = work["target_value"] - work["market_value"]
    work["estimated_annual_income"] = work["shares"].fillna(0) * work["annual_income_per_share"].fillna(0)
    work["estimated_monthly_income"] = work["estimated_annual_income"] / 12
    work["shares_to_target"] = work.apply(
        lambda r: (r["rebalance_delta_value"] / r["used_price"]) if r["used_price"] else 0,
        axis=1,
    )
    return work


def build_income_calendar(portfolio: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for month_num, month_name in enumerate(MONTH_NAMES, start=1):
        est = 0.0
        for _, row in portfolio.iterrows():
            est += distribute_income(row)[month_num]
        rows.append({"Month": month_name, "Estimated paycheck": est})
    return pd.DataFrame(rows)


def money(x: float) -> str:
    return f"${x:,.0f}"


def money2(x: float) -> str:
    return f"${x:,.2f}"


def pct(x: float) -> str:
    return f"{x * 100:,.1f}%"


st.title("💵 Retirement Paycheck Dashboard")
st.caption("Income first. Portfolio second. iPhone-friendly layout.")

if "quick_cash" not in st.session_state:
    st.session_state.quick_cash = 0.0

if "total_invested" not in st.session_state:
    st.session_state.total_invested = DEFAULT_TOTAL_INVESTED

if "contribution_input" not in st.session_state:
    st.session_state.contribution_input = 0.0

with st.sidebar:
    st.header("Your setup")
    st.write("Edit positions here or upload a CSV.")

    uploaded = st.file_uploader("Upload portfolio CSV", type=["csv"])
    if uploaded is not None:
        user_df = pd.read_csv(uploaded)
    else:
        user_df = load_default_df()

    st.download_button(
        "Download template CSV",
        load_default_df().to_csv(index=False).encode("utf-8"),
        file_name="retirement_paycheck_template.csv",
        mime="text/csv",
    )

    st.info(
        "Prices come from Yahoo Finance where available. Cash-like positions such as FDRXX use manual price. "
        "Income and payout schedules are editable estimates."
    )

    st.divider()
    st.subheader("Invested amount")
    st.caption("Use this for total money you have added. This prevents cash deposits from showing up as fake gains.")

    invest_q1, invest_q2, invest_q3, invest_q4 = st.columns(4)
    if invest_q1.button("+10k", use_container_width=True, key="invest_add_10k"):
        st.session_state.total_invested += 10000.0
    if invest_q2.button("+25k", use_container_width=True, key="invest_add_25k"):
        st.session_state.total_invested += 25000.0
    if invest_q3.button("+50k", use_container_width=True, key="invest_add_50k"):
        st.session_state.total_invested += 50000.0
    if invest_q4.button("Reset", use_container_width=True, key="invest_reset"):
        st.session_state.total_invested = DEFAULT_TOTAL_INVESTED

    st.number_input(
        "Edit total invested",
        min_value=0.0,
        step=1000.0,
        key="total_invested",
        help="This is your contribution total, not your market value.",
    )

edited_df = st.data_editor(
    user_df,
    use_container_width=True,
    num_rows="dynamic",
    hide_index=True,
    column_config={
        "ticker": st.column_config.TextColumn("Ticker"),
        "shares": st.column_config.NumberColumn("Shares", step=0.001, format="%.3f"),
        "cost_basis_per_share": st.column_config.NumberColumn("Cost/Share", step=0.01, format="%.2f"),
        "target_weight": st.column_config.NumberColumn("Target Wt", step=0.01, format="%.4f"),
        "annual_income_per_share": st.column_config.NumberColumn("Annual Income/Share", step=0.01, format="%.2f"),
        "manual_price": st.column_config.NumberColumn("Manual Price", step=0.01, format="%.2f"),
        "payout_frequency": st.column_config.SelectboxColumn("Payout Freq", options=["monthly", "quarterly", "none"]),
        "payout_months": st.column_config.TextColumn("Payout Months"),
        "notes": st.column_config.TextColumn("Notes"),
    },
)

portfolio = build_portfolio(edited_df)
calendar_df = build_income_calendar(portfolio)

total_value = float(portfolio["market_value"].sum())
holdings_cost_gain = float(portfolio["gain_loss"].sum())
day_change = float(portfolio["day_change_value"].sum())
monthly_income = float(portfolio["estimated_monthly_income"].sum())
annual_income = float(portfolio["estimated_annual_income"].sum())
progress = (monthly_income / GOAL_MONTHLY) if GOAL_MONTHLY else 0
next_pay_month = calendar_df.sort_values("Estimated paycheck", ascending=False).iloc[0]["Month"] if not calendar_df.empty else "N/A"

total_invested = float(st.session_state.total_invested)
true_portfolio_gain = total_value - total_invested
true_gain_pct = (true_portfolio_gain / total_invested) if total_invested > 0 else 0.0

st.subheader("Your Paycheck")
col1, col2 = st.columns(2)
col1.metric("Estimated monthly income", money(monthly_income), delta=f"Goal progress: {progress * 100:,.0f}%")
col2.metric("Income goal", money(GOAL_MONTHLY), delta=f"Gap: {money(monthly_income - GOAL_MONTHLY)}")

st.progress(min(max(progress, 0.0), 1.0), text=f"Monthly income progress toward {money(GOAL_MONTHLY)}")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Current portfolio value", money(total_value))
m2.metric("Today's move", money(day_change))
m3.metric("True portfolio gain/loss", money(true_portfolio_gain), delta=f"{true_gain_pct * 100:,.2f}%")
m4.metric("Highest payout month", next_pay_month, delta=money(float(calendar_df["Estimated paycheck"].max()) if not calendar_df.empty else 0))

mini1, mini2 = st.columns(2)
mini1.metric("Total invested", money(total_invested))
mini2.metric("Holdings cost-basis gain/loss", money(holdings_cost_gain))

st.divider()

left, right = st.columns([1.1, 1])
with left:
    st.subheader("Paycheck by holding")
    income_view = portfolio[["ticker", "estimated_monthly_income", "estimated_annual_income", "market_value", "payout_frequency"]].copy()
    income_view = income_view.sort_values("estimated_monthly_income", ascending=False)
    income_view["estimated_monthly_income"] = income_view["estimated_monthly_income"].map(money)
    income_view["estimated_annual_income"] = income_view["estimated_annual_income"].map(money)
    income_view["market_value"] = income_view["market_value"].map(money)
    st.dataframe(income_view, use_container_width=True, hide_index=True)

with right:
    st.subheader("Estimated paycheck calendar")
    st.bar_chart(calendar_df.set_index("Month"))
    st.caption("This version uses editable monthly and quarterly payout timing so bonus months show up instead of a flat 12-month average.")

st.divider()

st.subheader("Rebalance helper")
rb1, rb2 = st.columns([1, 1.3])

with rb1:
    st.caption("Quick add-cash buttons")
    qb1, qb2, qb3, qb4 = st.columns(4)
    if qb1.button("+10k", use_container_width=True, key="cash_10k"):
        st.session_state.quick_cash = 10000.0
    if qb2.button("+25k", use_container_width=True, key="cash_25k"):
        st.session_state.quick_cash = 25000.0
    if qb3.button("+50k", use_container_width=True, key="cash_50k"):
        st.session_state.quick_cash = 50000.0
    if qb4.button("Clear", use_container_width=True, key="cash_clear"):
        st.session_state.quick_cash = 0.0

    new_cash = st.number_input(
        "New cash to invest",
        min_value=0.0,
        value=float(st.session_state.quick_cash),
        step=1000.0,
        key="new_cash_input",
    )
    st.session_state.quick_cash = float(new_cash)

    if st.button("Add this cash to total invested", use_container_width=True):
        st.session_state.total_invested += float(new_cash)
        st.session_state.quick_cash = 0.0
        st.rerun()

    threshold_pct = st.slider(
        "Only show weight gaps bigger than",
        min_value=0.0,
        max_value=5.0,
        value=0.5,
        step=0.1,
    )
    threshold = threshold_pct / 100

rebal = portfolio[[
    "ticker", "market_value", "target_value", "rebalance_delta_value", "shares_to_target",
    "actual_weight", "target_weight", "weight_gap", "used_price"
]].copy()
rebal = rebal[rebal["ticker"].str.len() > 0].copy()
rebal["Action"] = rebal["rebalance_delta_value"].apply(lambda x: "Buy" if x > 0 else ("Trim" if x < 0 else "Hold"))

underweights = rebal[rebal["rebalance_delta_value"] > 0].copy()
if new_cash > 0 and not underweights.empty:
    total_need = float(underweights["rebalance_delta_value"].sum())
    alloc_factor = min(1.0, new_cash / total_need) if total_need > 0 else 0.0
    underweights["cash_to_add"] = underweights["rebalance_delta_value"] * alloc_factor
    underweights["shares_to_buy_with_cash"] = underweights.apply(
        lambda r: (r["cash_to_add"] / r["used_price"]) if r["used_price"] else 0,
        axis=1,
    )
    add_cash_view = underweights[["ticker", "cash_to_add", "shares_to_buy_with_cash", "actual_weight", "target_weight"]].copy()
    add_cash_view = add_cash_view[add_cash_view["cash_to_add"] > 1].sort_values("cash_to_add", ascending=False)
    add_cash_view["cash_to_add"] = add_cash_view["cash_to_add"].map(money)
    add_cash_view["shares_to_buy_with_cash"] = add_cash_view["shares_to_buy_with_cash"].map(lambda x: f"{x:,.3f}")
    add_cash_view["actual_weight"] = add_cash_view["actual_weight"].map(pct)
    add_cash_view["target_weight"] = add_cash_view["target_weight"].map(pct)
else:
    add_cash_view = pd.DataFrame()

rebal_filtered = rebal[rebal["weight_gap"].abs() >= threshold].copy().sort_values("rebalance_delta_value", ascending=False)
rebal_view = rebal_filtered[["ticker", "actual_weight", "target_weight", "weight_gap", "rebalance_delta_value", "shares_to_target", "Action"]].copy()
rebal_view["actual_weight"] = rebal_view["actual_weight"].map(pct)
rebal_view["target_weight"] = rebal_view["target_weight"].map(pct)
rebal_view["weight_gap"] = rebal_view["weight_gap"].map(pct)
rebal_view["rebalance_delta_value"] = rebal_view["rebalance_delta_value"].map(money)
rebal_view["shares_to_target"] = rebal_view["shares_to_target"].map(lambda x: f"{x:,.3f}")

with rb2:
    if new_cash > 0 and not add_cash_view.empty:
        st.caption("Add-cash mode")
        st.dataframe(add_cash_view, use_container_width=True, hide_index=True)
    st.caption("Full rebalance mode")
    st.dataframe(rebal_view, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Holdings and allocation")
holdings_view = portfolio[[
    "ticker", "shares", "used_price", "market_value", "cost_basis_per_share", "gain_loss",
    "target_weight", "actual_weight", "weight_gap", "payout_frequency", "payout_months", "notes"
]].copy()

for c in ["used_price", "market_value", "cost_basis_per_share", "gain_loss"]:
    holdings_view[c] = holdings_view[c].map(money2)

holdings_view["target_weight"] = holdings_view["target_weight"].map(pct)
holdings_view["actual_weight"] = holdings_view["actual_weight"].map(pct)
holdings_view["weight_gap"] = holdings_view["weight_gap"].map(pct)
holdings_view["shares"] = holdings_view["shares"].map(lambda x: f"{x:,.3f}")

st.dataframe(holdings_view, use_container_width=True, hide_index=True)

st.divider()
st.subheader("How to use updates")
st.write(
    "- Edit holdings in the table like before.\n"
    "- Use 'Edit total invested' when you want to correct your total contribution number.\n"
    "- Use 'Add this cash to total invested' when new money gets added to the account.\n"
    "- Current portfolio value includes FDRXX and all other holdings.\n"
    "- True portfolio gain/loss now compares current value against total invested, so deposits stop showing up as fake gains.\n"
    "- Holdings cost-basis gain/loss is still shown separately for reference.\n"
    "- The new cash box in Rebalance helper tells you where to add money without selling.\n"
    "- Full rebalance mode shows the exact dollar amount and share count to buy or trim to get back to target."
)
