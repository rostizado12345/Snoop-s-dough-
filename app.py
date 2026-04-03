import streamlit as st
import pandas as pd
import altair as alt

st.set_page_config(
    page_title="Richard's Retirement Paycheck",
    page_icon="💵",
    layout="wide"
)

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

def money(x):
    return f"${float(x):,.0f}"

GOAL_MONTHLY = 8000

try:
    df = pd.read_csv("portfolio.csv")
except Exception as e:
    st.error(f"Could not open portfolio.csv: {e}")
    st.stop()

required = ["Ticker", "Shares", "Price", "Yield"]
missing = [c for c in required if c not in df.columns]

if missing:
    st.error(f"portfolio.csv is missing these columns: {', '.join(missing)}")
    st.stop()

df["Shares"] = pd.to_numeric(df["Shares"], errors="coerce").fillna(0)
df["Price"] = pd.to_numeric(df["Price"], errors="coerce").fillna(0)
df["Yield"] = pd.to_numeric(df["Yield"], errors="coerce").fillna(0)

df["Value"] = df["Shares"] * df["Price"]
df["Annual Income"] = df["Value"] * df["Yield"]
df["Monthly Income"] = df["Annual Income"] / 12

monthly_income = float(df["Monthly Income"].sum())
annual_income = float(df["Annual Income"].sum())
total_value = float(df["Value"].sum())
progress = monthly_income / GOAL_MONTHLY if GOAL_MONTHLY else 0

st.markdown('<div class="main-title">Richard’s Retirement Paycheck</div>', unsafe_allow_html=True)
st.markdown('<div class="subtle-text">Clean, simple, and easy to read.</div>', unsafe_allow_html=True)

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

k1, k2, k3 = st.columns(3)

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
        <div class="kpi-label">Annual Income</div>
        <div class="kpi-value">{money(annual_income)}</div>
    </div>
    """, unsafe_allow_html=True)

with k3:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Number of Holdings</div>
        <div class="kpi-value">{len(df)}</div>
    </div>
    """, unsafe_allow_html=True)

left, right = st.columns([1.25, 1])

with left:
    st.markdown('<div class="section-title">Your Income Engine</div>', unsafe_allow_html=True)

    income_view = df[["Ticker", "Monthly Income", "Annual Income", "Value"]].copy()
    income_view = income_view.sort_values("Monthly Income", ascending=False)

    total_row = pd.DataFrame([{
        "Ticker": "TOTAL",
        "Monthly Income": df["Monthly Income"].sum(),
        "Annual Income": df["Annual Income"].sum(),
        "Value": df["Value"].sum()
    }])

    income_view = pd.concat([income_view, total_row], ignore_index=True)

    st.dataframe(
        income_view,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Ticker": st.column_config.TextColumn("Holding"),
            "Monthly Income": st.column_config.NumberColumn("Monthly Pay", format="$%0.0f"),
            "Annual Income": st.column_config.NumberColumn("Yearly Pay", format="$%0.0f"),
            "Value": st.column_config.NumberColumn("Value", format="$%0.0f"),
        },
    )

with right:
    st.markdown('<div class="section-title">Monthly Paycheck Outlook</div>', unsafe_allow_html=True)

    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    cal = pd.DataFrame({
        "Month": months,
        "Estimated Paycheck": [monthly_income] * 12
    })

    chart = alt.Chart(cal).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
        x=alt.X("Month:N", sort=months, title=""),
        y=alt.Y("Estimated Paycheck:Q", title="Income"),
        tooltip=["Month", alt.Tooltip("Estimated Paycheck:Q", format=",.0f")]
    ).properties(height=330)

    st.altair_chart(chart, use_container_width=True)
    st.markdown(
        f'<div class="small-note">Projected monthly paycheck: <b>{money(monthly_income)}</b></div>',
        unsafe_allow_html=True
    )

st.markdown('<div class="section-title">Portfolio Detail</div>', unsafe_allow_html=True)

detail = df[["Ticker", "Shares", "Price", "Yield", "Value", "Monthly Income", "Annual Income"]].copy()

st.dataframe(
    detail,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Ticker": st.column_config.TextColumn("Holding"),
        "Shares": st.column_config.NumberColumn("Shares", format="%0.0f"),
        "Price": st.column_config.NumberColumn("Price", format="$%0.2f"),
        "Yield": st.column_config.NumberColumn("Yield", format="%0.2f"),
        "Value": st.column_config.NumberColumn("Value", format="$%0.0f"),
        "Monthly Income": st.column_config.NumberColumn("Monthly Pay", format="$%0.0f"),
        "Annual Income": st.column_config.NumberColumn("Yearly Pay", format="$%0.0f"),
    },
)
