import streamlit as st
import pandas as pd
import altair as alt
from pathlib import Path

# =========================
# PAGE SETUP
# =========================
st.set_page_config(
    page_title="Richard's Retirement Paycheck",
    page_icon="💵",
    layout="wide"
)

# =========================
# STYLING
# =========================
st.markdown("""
<style>
.block-container {
    padding-top: 1rem;
    padding-bottom: 1.2rem;
    max-width: 1250px;
}
.main-title {
    font-size: 2.2rem;
    font-weight: 800;
    margin-bottom: 0.1rem;
}
.subtle-text {
    color: #9ca3af;
    font-size: 1rem;
    margin-bottom: 1rem;
}
.hero-card {
    background: linear-gradient(135deg, #0f172a, #1e293b);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 18px;
    padding: 22px 24px;
    margin-bottom: 14px;
}
.hero-label {
    color: #cbd5e1;
    font-size: 1rem;
    margin-bottom: 8px;
}
.hero-value {
    color: #f8fafc;
    font-size: 2.8rem;
    font-weight: 800;
    line-height: 1.05;
}
.hero-sub {
    color: #94a3b8;
    font-size: 1rem;
    margin-top: 8px;
}
.kpi-card {
    background: #111827;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 16px;
    padding: 14px 16px;
    margin-bottom: 10px;
    min-height: 88px;
}
.kpi-label {
    color: #9ca3af;
    font-size: 0.86rem;
    margin-bottom: 6px;
}
.kpi-value {
    color: #ffffff;
    font-size: 1.35rem;
    font-weight: 700;
    line-height: 1.1;
}
.section-title {
    font-size: 1.15rem;
    font-weight: 700;
    margin-top: 0.4rem;
    margin-bottom: 0.6rem;
}
.small-note {
    color: #9ca3af;
    font-size: 0.9rem;
}
div[data-testid="stDataFrame"] * {
    font-size: 17px !important;
}
thead tr th {
    font-size: 17px !important;
}
</style>
""", unsafe_allow_html=True)

# =========================
# HELPERS
# =========================
def money(x):
    try:
        return f"${float(x):,.0f}"
    except:
        return "$0"

def money_2(x):
    try:
        return f"${float(x):,.2f}"
    except:
        return "$0.00"

def pct(x):
    try:
        return f"{float(x):.1f}%"
    except:
        return "0.0%"

def find_portfolio_file():
    candidates = [
        "portfolio.csv",
        "holdings.csv",
        "retirement_portfolio.csv",
        "portfolio_data.csv",
    ]
    for name in candidates:
        if Path(name).exists():
            return name
    return None

def normalize_columns(df):
    rename_map = {
        "symbol": "ticker",
        "Ticker": "ticker",
        "Symbol": "ticker",
        "market value": "market_value",
        "Market Value": "market_value",
        "value": "market_value",
        "Value": "market_value",
        "annual income": "estimated_annual_income",
        "Annual Income": "estimated_annual_income",
        "monthly income": "estimated_monthly_income",
        "Monthly Income": "estimated_monthly_income",
        "frequency": "payout_frequency",
        "Frequency": "payout_frequency",
        "shares_owned": "shares",
    }
    df = df.rename(columns=rename_map)
    return df

# =========================
# LOAD DATA
# =========================
file_name = find_portfolio_file()

if file_name is None:
    st.error("No portfolio CSV found. Put your portfolio file in the app folder as portfolio.csv.")
    st.stop()

portfolio = pd.read_csv(file_name)
portfolio = normalize_columns(portfolio)

# Make sure required columns exist
if "ticker" not in portfolio.columns:
    st.error("Your CSV needs a ticker column.")
    st.stop()

if "market_value" not in portfolio.columns:
    st.error("Your CSV needs a market_value column.")
    st.stop()

# Fill optional columns if missing
if "estimated_annual_income" not in portfolio.columns:
    portfolio["estimated_annual_income"] = 0.0

if "estimated_monthly_income" not in portfolio.columns:
    portfolio["estimated_monthly_income"] = portfolio["estimated_annual_income"] / 12

if "payout_frequency" not in portfolio.columns:
    portfolio["payout_frequency"] = ""

if "day_change" not in portfolio.columns:
    portfolio["day_change"] = 0.0

if "unrealized_gain" not in portfolio.columns:
    portfolio["unrealized_gain"] = 0.0

# Force numeric
for col in ["market_value", "estimated_annual_income", "estimated_monthly_income", "day_change", "unrealized_gain"]:
    portfolio[col] = pd.to_numeric(portfolio[col], errors="coerce").fillna(0)

# =========================
# CORE NUMBERS
# =========================
GOAL_MONTHLY = 8000

monthly_income = float(portfolio["estimated_monthly_income"].sum())
annual_income = float(portfolio["estimated_annual_income"].sum())
total_value = float(portfolio["market_value"].sum())
day_change = float(portfolio["day_change"].sum())
total_gain = float(portfolio["unrealized_gain"].sum())
progress = monthly_income / GOAL_MONTHLY if GOAL_MONTHLY else 0

# =========================
# SIMPLE CALENDAR / PAYOUT OUTLOOK
# =========================
calendar_rows = []
months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

for m in months:
    calendar_rows.append({
        "Month": m,
        "Estimated paycheck": monthly_income
    })

calendar_df = pd.DataFrame(calendar_rows)
next_pay_month = calendar_df.sort_values("Estimated paycheck", ascending=False).iloc[0]["Month"] if not calendar_df.empty else "N/A"
top_month_amt = float(calendar_df["Estimated paycheck"].max()) if not calendar_df.empty else 0

# =========================
# HEADER
# =========================
st.markdown('<div class="main-title">Richard’s Retirement Paycheck</div>', unsafe_allow_html=True)
st.markdown('<div class="subtle-text">A cleaner, easier-to-read dashboard for your income portfolio.</div>', unsafe_allow_html=True)

st.markdown(f"""
<div class="hero-card">
    <div class="hero-label">Estimated Monthly Income</div>
    <div class="hero-value">{money(monthly_income)}</div>
    <div class="hero-sub">
        Goal progress: {progress * 100:,.0f}% &nbsp;&nbsp;•&nbsp;&nbsp;
        Income goal: {money(GOAL_MONTHLY)} &nbsp;&nbsp;•&nbsp;&nbsp;
        Gap: {money(monthly_income - GOAL_MONTHLY)}
    </div>
</div>
""", unsafe_allow_html=True)

st.progress(
    min(max(progress, 0.0), 1.0),
    text=f"Monthly income progress toward {money(GOAL_MONTHLY)}"
)

# =========================
# KPI ROW
# =========================
k1, k2, k3, k4 = st.columns(4)

with k1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Portfolio Value</div>
        <div class="kpi-value">{money(total_value)}</div>
    </div>
    """, unsafe_allow_html=True)

with k2:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Today’s Move</div>
        <div class="kpi-value">{money(day_change)}</div>
    </div>
    """, unsafe_allow_html=True)

with k3:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Unrealized Gain/Loss</div>
        <div class="kpi-value">{money(total_gain)}</div>
    </div>
    """, unsafe_allow_html=True)

with k4:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Annual Income</div>
        <div class="kpi-value">{money(annual_income)}</div>
    </div>
    """, unsafe_allow_html=True)

# =========================
# MAIN LAYOUT
# =========================
left, right = st.columns([1.25, 1])

with left:
    st.markdown('<div class="section-title">Your Income Engine</div>', unsafe_allow_html=True)

    income_view = portfolio[
        ["ticker", "estimated_monthly_income", "estimated_annual_income", "market_value", "payout_frequency"]
    ].copy()

    income_view = income_view.sort_values("estimated_monthly_income", ascending=False)

    total_row = pd.DataFrame([{
        "ticker": "TOTAL",
        "estimated_monthly_income": float(portfolio["estimated_monthly_income"].sum()),
        "estimated_annual_income": float(portfolio["estimated_annual_income"].sum()),
        "market_value": float(portfolio["market_value"].sum()),
        "payout_frequency": ""
    }])

    income_view = pd.concat([income_view, total_row], ignore_index=True)

    st.dataframe(
        income_view,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ticker": st.column_config.TextColumn("Holding"),
            "estimated_monthly_income": st.column_config.NumberColumn("Monthly Pay", format="$%0.0f"),
            "estimated_annual_income": st.column_config.NumberColumn("Yearly Pay", format="$%0.0f"),
            "market_value": st.column_config.NumberColumn("Value", format="$%0.0f"),
            "payout_frequency": st.column_config.TextColumn("Frequency"),
        },
    )

with right:
    st.markdown('<div class="section-title">Monthly Paycheck Outlook</div>', unsafe_allow_html=True)

    chart_df = calendar_df.copy()

    chart = alt.Chart(chart_df).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
        x=alt.X("Month:N", sort=months, title=""),
        y=alt.Y("Estimated paycheck:Q", title="Income"),
        tooltip=[
            alt.Tooltip("Month:N"),
            alt.Tooltip("Estimated paycheck:Q", format=",.0f")
        ]
    ).properties(height=330)

    st.altair_chart(chart, use_container_width=True)
    st.markdown(f'<div class="small-note">Highest payout month: <b>{next_pay_month}</b> &nbsp;&nbsp;•&nbsp;&nbsp; Projected amount: <b>{money(top_month_amt)}</b></div>', unsafe_allow_html=True)

# =========================
# BOTTOM DETAIL TABLE
# =========================
st.markdown('<div class="section-title">Portfolio Detail</div>', unsafe_allow_html=True)

detail_cols = [c for c in ["ticker", "market_value", "estimated_monthly_income", "estimated_annual_income", "payout_frequency", "day_change", "unrealized_gain"] if c in portfolio.columns]
detail_view = portfolio[detail_cols].copy()

st.dataframe(
    detail_view,
    use_container_width=True,
    hide_index=True,
    column_config={
        "ticker": st.column_config.TextColumn("Holding"),
        "market_value": st.column_config.NumberColumn("Value", format="$%0.0f"),
        "estimated_monthly_income": st.column_config.NumberColumn("Monthly Pay", format="$%0.0f"),
        "estimated_annual_income": st.column_config.NumberColumn("Yearly Pay", format="$%0.0f"),
        "payout_frequency": st.column_config.TextColumn("Frequency"),
        "day_change": st.column_config.NumberColumn("Today's Move", format="$%0.0f"),
        "unrealized_gain": st.column_config.NumberColumn("Gain/Loss", format="$%0.0f"),
    },
)

st.caption("Tip: if your numbers do not show correctly, your CSV column names may be slightly different. If that happens, send me a screenshot and I’ll make the next version even easier.")
