import streamlit as st
import pandas as pd
import altair as alt

st.set_page_config(
    page_title="Richard's Retirement Paycheck",
    page_icon="💵",
    layout="wide"
)

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
div[data-testid="stDataFrame"] * { font-size: 16px !important; }
</style>
""", unsafe_allow_html=True)

def money(x):
    return f"${float(x):,.0f}"

GOAL = 8000

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

# realistic scaling
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
# ESTIMATED PAY TIMING
# this is a starter timing map you can tweak later
# -------------------------
pay_window_map = {
    "GDXY": "Early",
    "QQQI": "Late",
    "SPYI": "Late",
    "DIVO": "Mid",
    "FEPI": "Late",
    "AIPI": "Mid",
    "SVOL": "Late",
    "IYRI": "Mid",
    "IWMI": "Mid",
    "MLPI": "Mid",
    "IAU": "None",
    "TLTW": "Late",
}

pay_day_map = {
    "GDXY": 5,
    "QQQI": 24,
    "SPYI": 26,
    "DIVO": 15,
    "FEPI": 27,
    "AIPI": 14,
    "SVOL": 25,
    "IYRI": 16,
    "IWMI": 17,
    "MLPI": 18,
    "IAU": None,
    "TLTW": 23,
}

df["Pay_Window"] = df["Ticker"].map(pay_window_map).fillna("Mid")
df["Pay_Day"] = df["Ticker"].map(pay_day_map)

# monthly schedule buckets
schedule = (
    df.groupby("Pay_Window", dropna=False)["Monthly_Expected"]
      .sum()
      .reindex(["Early", "Mid", "Late", "None"], fill_value=0)
      .reset_index()
)
schedule.columns = ["Window", "Expected Monthly Income"]

# cleaner detail
income_view = df[[
    "Ticker", "Value", "Monthly_Conservative", "Monthly_Expected",
    "Monthly_Optimistic", "Pay_Window", "Pay_Day"
]].copy()

income_view = income_view.sort_values("Monthly_Expected", ascending=False)

total_row = pd.DataFrame([{
    "Ticker": "TOTAL",
    "Value": df["Value"].sum(),
    "Monthly_Conservative": con,
    "Monthly_Expected": exp,
    "Monthly_Optimistic": opt,
    "Pay_Window": "",
    "Pay_Day": ""
}])

income_view = pd.concat([income_view, total_row], ignore_index=True)

# -------------------------
# HEADER
# -------------------------
st.title("Richard’s Retirement Paycheck")
st.markdown("<div class='sub'>Now with estimated payout timing.</div>", unsafe_allow_html=True)

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
# KPI ROW
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
# MAIN SECTIONS
# -------------------------
left, right = st.columns([1.35, 1])

with left:
    st.markdown('<div class="section-title">Your Income Engine</div>', unsafe_allow_html=True)
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
            "Pay_Window": st.column_config.TextColumn("Pay Window"),
            "Pay_Day": st.column_config.NumberColumn("Est. Day"),
        },
    )

with right:
    st.markdown('<div class="section-title">Estimated Payout Timing</div>', unsafe_allow_html=True)

    chart = alt.Chart(schedule).mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6).encode(
        x=alt.X("Window:N", sort=["Early", "Mid", "Late", "None"], title=""),
        y=alt.Y("Expected Monthly Income:Q", title="Expected Income"),
        tooltip=[
            alt.Tooltip("Window:N"),
            alt.Tooltip("Expected Monthly Income:Q", format=",.0f")
        ]
    ).properties(height=320)

    st.altair_chart(chart, use_container_width=True)
    st.markdown(
        "<div class='small-note'>This is an estimated timing map. We can fine-tune individual funds later if you want exacter payout windows.</div>",
        unsafe_allow_html=True
    )

# -------------------------
# UPCOMING LIST
# -------------------------
st.markdown('<div class="section-title">Estimated Monthly Pay Schedule</div>', unsafe_allow_html=True)

schedule_list = df[["Ticker", "Pay_Window", "Pay_Day", "Monthly_Expected"]].copy()
schedule_list = schedule_list[schedule_list["Pay_Window"] != "None"].sort_values(["Pay_Day", "Ticker"])

st.dataframe(
    schedule_list,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Ticker": st.column_config.TextColumn("Holding"),
        "Pay_Window": st.column_config.TextColumn("Window"),
        "Pay_Day": st.column_config.NumberColumn("Est. Day"),
        "Monthly_Expected": st.column_config.NumberColumn("Expected Monthly Pay", format="$%0.0f"),
    },
)
