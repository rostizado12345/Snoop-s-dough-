import streamlit as st
import pandas as pd
import altair as alt

st.set_page_config(
    page_title="Richard's Retirement Paycheck",
    page_icon="💵",
    layout="st.markdown("## 📊 Portfolio Summary")

total_invested = 295090

try:
    current_value = int(round(df["Value"].sum()))
except:
    current_value = 299240

total_gain = current_value - total_invested
gain_pct = (total_gain / total_invested) * 100

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("💼 Invested", f"${total_invested:,.0f}")

with col2:
    st.metric("📈 Value", f"${current_value:,.0f}")

with col3:
    st.metric("💰 Gain", f"${total_gain:,.0f}", f"{gain_pct:.2f}%")

st.markdown("## 📊 Portfolio Summary")

st.markdown("""
**Invested:** $295,090  
**Gain:** +$4,150  
""")

# -------------------------
# STYLE
# -------------------------
st.markdown("""
<style>
.block-container { max-width: 1250px; padding-top: 1rem; padding-bottom: 1rem; }
.hero { font-size: 2.8rem; font-weight: 800; line-height: 1.05; }
.sub { color: #9ca3af; font-size: 1rem; }
.card {
    background: linear-gradient(135deg, #0f172a, #1e293b);
    border-radius: 18px;
    padding: 20px 22px;
    margin-bottom: 14px;
}
.kpi {
    background: #0b1220;
    border-radius: 16px;
    padding: 16px 18px;
    margin-bottom: 12px;
}
.kpi-label { color: #9ca3af; font-size: 0.9rem; margin-bottom: 6px; }
.kpi-value { color: white; font-size: 1.5rem; font-weight: 700; }
.section-title { font-size: 1.2rem; font-weight: 800; margin-top: 0.4rem; margin-bottom: 0.6rem; }
.small-note { color: #9ca3af; font-size: 0.9rem; }
.calendar-card {
    background: #111827;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 16px;
    padding: 14px 16px;
    min-height: 170px;
    margin-bottom: 12px;
}
.calendar-week {
    color: #93c5fd;
    font-size: 0.9rem;
    font-weight: 700;
    margin-bottom: 8px;
}
.calendar-pay {
    color: white;
    font-size: 1.7rem;
    font-weight: 800;
    margin-bottom: 10px;
}
.calendar-items {
    color: #d1d5db;
    font-size: 0.92rem;
    line-height: 1.45;
}
div[data-testid="stDataFrame"] * { font-size: 16px !important; }
</style>
""", unsafe_allow_html=True)

def money(x):
    return f"${float(x):,.0f}"

GOAL = 8000
CASH_BUFFER = 18000  # change this later if your FDRXX changes

# -------------------------
# LOAD CSV
# -------------------------
df = pd.read_csv("portfolio.csv")

required = ["Ticker", "Shares", "Price", "Yield"]
missing = [c for c in required if c not in df.columns]
if missing:
    st.error(f"portfolio.csv is missing these columns: {', '.join(missing)}")
    st.stop()

df["Shares"] = pd.to_numeric(df["Shares"], errors="coerce").fillna(0)
df["Price"] = pd.to_numeric(df["Price"], errors="coerce").fillna(0)
df["Yield"] = pd.to_numeric(df["Yield"], errors="coerce").fillna(0)

# -------------------------
# CALCULATIONS
# -------------------------
df["Value"] = df["Shares"] * df["Price"]

df["Annual_Optimistic"] = df["Value"] * df["Yield"]
df["Annual_Expected"] = df["Annual_Optimistic"] * 0.90
df["Annual_Conservative"] = df["Annual_Optimistic"] * 0.75

df["Monthly_Optimistic"] = df["Annual_Optimistic"] / 12
df["Monthly_Expected"] = df["Annual_Expected"] / 12
df["Monthly_Conservative"] = df["Annual_Conservative"] / 12

opt = df["Monthly_Optimistic"].sum()
exp = df["Monthly_Expected"].sum()
con = df["Monthly_Conservative"].sum()
total_value = df["Value"].sum()

# -------------------------
# NEW UPGRADE 1: CASH BUFFER COVER
# -------------------------
goal_weekly_need = GOAL / 4
expected_weekly_income = exp / 4
income_gap_per_week = max(goal_weekly_need - expected_weekly_income, 0)
weeks_of_gap_covered = CASH_BUFFER / income_gap_per_week if income_gap_per_week > 0 else 999

# -------------------------
# ESTIMATED PAY TIMING MAP
# -------------------------
pay_day_map = {
    "GDXY": 5,
    "CHPY": 8,
    "AIPI": 12,
    "DIVO": 15,
    "IYRI": 16,
    "IWMI": 17,
    "MLPI": 18,
    "TLTW": 22,
    "QQQI": 24,
    "SVOL": 25,
    "SPYI": 26,
    "FEPI": 27,
    "IAU": None
}

df["Pay_Day"] = df["Ticker"].map(pay_day_map)

def week_bucket(day):
    if pd.isna(day):
        return "No Payout"
    day = int(day)
    if day <= 7:
        return "Week 1"
    elif day <= 14:
        return "Week 2"
    elif day <= 21:
        return "Week 3"
    else:
        return "Week 4"

df["Pay_Week"] = df["Pay_Day"].apply(week_bucket)

# -------------------------
# NEW UPGRADE 2: INCOME % BY ETF
# -------------------------
df["Income_Share_%"] = (df["Monthly_Expected"] / exp * 100).fillna(0)

# -------------------------
# HEADER
# -------------------------
st.title("Richard’s Retirement Paycheck")
st.markdown("<div class='sub'>Real paycheck calendar view with estimated weekly deposit timing.</div>", unsafe_allow_html=True)

st.markdown(f"""
<div class="card">
    <div class="sub">Expected Monthly Income</div>
    <div class="hero">{money(exp)}</div>
    <div class="sub" style="margin-top:8px;">
        Goal progress: {exp / GOAL:.0%} &nbsp;&nbsp;•&nbsp;&nbsp;
        Income goal: {money(GOAL)} &nbsp;&nbsp;•&nbsp;&nbsp;
        Gap: {money(exp - GOAL)}
    </div>
</div>
""", unsafe_allow_html=True)

st.progress(min(exp / GOAL, 1.0), text=f"Monthly income progress toward {money(GOAL)}")

# -------------------------
# KPI ROWS
# -------------------------
c1, c2, c3 = st.columns(3)

with c1:
    st.markdown(f"""
    <div class="kpi">
        <div class="kpi-label">Conservative Monthly</div>
        <div class="kpi-value">{money(con)}</div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="kpi">
        <div class="kpi-label">Expected Monthly</div>
        <div class="kpi-value">{money(exp)}</div>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class="kpi">
        <div class="kpi-label">Optimistic Monthly</div>
        <div class="kpi-value">{money(opt)}</div>
    </div>
    """, unsafe_allow_html=True)

k1, k2, k3 = st.columns(3)

with k1:
    st.markdown(f"""
    <div class="kpi">
        <div class="kpi-label">Portfolio Value</div>
        <div class="kpi-value">{money(total_value)}</div>
    </div>
    """, unsafe_allow_html=True)

with k2:
    st.markdown(f"""
    <div class="kpi">
        <div class="kpi-label">Annual Expected Income</div>
        <div class="kpi-value">{money(exp * 12)}</div>
    </div>
    """, unsafe_allow_html=True)

with k3:
    st.markdown(f"""
    <div class="kpi">
        <div class="kpi-label">Number of Holdings</div>
        <div class="kpi-value">{len(df)}</div>
    </div>
    """, unsafe_allow_html=True)

# -------------------------
# NEW SECTION: CASH BUFFER COVER
# -------------------------
st.markdown('<div class="section-title">Cash Buffer Cover</div>', unsafe_allow_html=True)

b1, b2, b3 = st.columns(3)

with b1:
    st.markdown(f"""
    <div class="kpi">
        <div class="kpi-label">Cash Buffer</div>
        <div class="kpi-value">{money(CASH_BUFFER)}</div>
    </div>
    """, unsafe_allow_html=True)

with b2:
    st.markdown(f"""
    <div class="kpi">
        <div class="kpi-label">Weekly Goal Gap</div>
        <div class="kpi-value">{money(income_gap_per_week)}</div>
    </div>
    """, unsafe_allow_html=True)

with b3:
    weeks_text = f"{weeks_of_gap_covered:.1f} weeks" if weeks_of_gap_covered != 999 else "Fully covered"
    st.markdown(f"""
    <div class="kpi">
        <div class="kpi-label">Cash Covers</div>
        <div class="kpi-value">{weeks_text}</div>
    </div>
    """, unsafe_allow_html=True)

# -------------------------
# PAYCHECK CALENDAR
# -------------------------
st.markdown('<div class="section-title">Monthly Paycheck Calendar</div>', unsafe_allow_html=True)

week_order = ["Week 1", "Week 2", "Week 3", "Week 4"]

week_summary = (
    df[df["Pay_Week"] != "No Payout"]
    .groupby("Pay_Week")["Monthly_Expected"]
    .sum()
    .reindex(week_order, fill_value=0)
)

week_holdings = {}
for wk in week_order:
    temp = df[df["Pay_Week"] == wk].sort_values("Pay_Day")
    items = []
    for _, row in temp.iterrows():
        items.append(f'{row["Ticker"]} · day {int(row["Pay_Day"])} · {money(row["Monthly_Expected"])}')
    week_holdings[wk] = items

w1, w2, w3, w4 = st.columns(4)

for col, wk in zip([w1, w2, w3, w4], week_order):
    items_html = "<br>".join(week_holdings[wk]) if week_holdings[wk] else "No estimated payouts"
    col.markdown(f"""
    <div class="calendar-card">
        <div class="calendar-week">{wk}</div>
        <div class="calendar-pay">{money(week_summary[wk])}</div>
        <div class="calendar-items">{items_html}</div>
    </div>
    """, unsafe_allow_html=True)

# -------------------------
# WEEKLY CHART
# -------------------------
st.markdown('<div class="section-title">Weekly Income Flow</div>', unsafe_allow_html=True)

weekly_chart_df = pd.DataFrame({
    "Week": week_order,
    "Expected Income": [week_summary[w] for w in week_order]
})

weekly_chart = alt.Chart(weekly_chart_df).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
    x=alt.X("Week:N", sort=week_order, title=""),
    y=alt.Y("Expected Income:Q", title="Expected Income"),
    tooltip=[
        alt.Tooltip("Week:N"),
        alt.Tooltip("Expected Income:Q", format=",.0f")
    ]
).properties(height=280)

st.altair_chart(weekly_chart, use_container_width=True)

# -------------------------
# HOLDINGS TABLE
# -------------------------
st.markdown('<div class="section-title">Your Income Engine</div>', unsafe_allow_html=True)

income_view = df[[
    "Ticker", "Value", "Monthly_Conservative", "Monthly_Expected",
    "Monthly_Optimistic", "Income_Share_%", "Pay_Week", "Pay_Day"
]].copy()

income_view = income_view.sort_values(["Pay_Day", "Ticker"], na_position="last")

total_row = pd.DataFrame([{
    "Ticker": "TOTAL",
    "Value": df["Value"].sum(),
    "Monthly_Conservative": con,
    "Monthly_Expected": exp,
    "Monthly_Optimistic": opt,
    "Income_Share_%": 100.0,
    "Pay_Week": "",
    "Pay_Day": ""
}])

income_view = pd.concat([income_view, total_row], ignore_index=True)

st.dataframe(
    income_view,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Ticker": st.column_config.TextColumn("Holding"),
        "Value": st.column_config.NumberColumn("Value", format="$%0.0f"),
        "Monthly_Conservative": st.column_config.NumberColumn("Conservative", format="$%0.0f"),
        "Monthly_Expected": st.column_config.NumberColumn("Expected", format="$%0.0f"),
        "Monthly_Optimistic": st.column_config.NumberColumn("Optimistic", format="$%0.0f"),
        "Income_Share_%": st.column_config.NumberColumn("% of Income", format="%.1f%%"),
        "Pay_Week": st.column_config.TextColumn("Pay Week"),
        "Pay_Day": st.column_config.NumberColumn("Est. Day"),
    },
)

# -------------------------
# DEPOSIT SCHEDULE TABLE
# -------------------------
st.markdown('<div class="section-title">Estimated Deposit Schedule</div>', unsafe_allow_html=True)

schedule_list = df[["Ticker", "Pay_Week", "Pay_Day", "Monthly_Expected"]].copy()
schedule_list = schedule_list[schedule_list["Pay_Week"] != "No Payout"].sort_values(["Pay_Day", "Ticker"])

st.dataframe(
    schedule_list,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Ticker": st.column_config.TextColumn("Holding"),
        "Pay_Week": st.column_config.TextColumn("Week"),
        "Pay_Day": st.column_config.NumberColumn("Est. Day"),
        "Monthly_Expected": st.column_config.NumberColumn("Expected Deposit", format="$%0.0f"),
    },
)

# -------------------------
# INCOME SHARE CHART
# -------------------------
st.markdown('<div class="section-title">Income Share by ETF</div>', unsafe_allow_html=True)

share_chart_df = df[["Ticker", "Income_Share_%"]].copy().sort_values("Income_Share_%", ascending=False)

share_chart = alt.Chart(share_chart_df).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
    y=alt.Y("Ticker:N", sort="-x", title=""),
    x=alt.X("Income_Share_%:Q", title="% of Expected Income"),
    tooltip=[
        alt.Tooltip("Ticker:N"),
        alt.Tooltip("Income_Share_%:Q", format=".1f")
    ]
).properties(height=360)

st.altair_chart(share_chart, use_container_width=True)

st.markdown(
    "<div class='small-note'>This is a paycheck-style estimate, not exact brokerage payment dates. We can fine-tune fund-by-fund later.</div>",
    unsafe_allow_html=True
)
