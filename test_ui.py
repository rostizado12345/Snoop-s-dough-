import streamlit as st

st.set_page_config(page_title="Retirement Paycheck Dashboard", layout="wide")

# ---------- STYLE FIX (FORCES TEXT VISIBILITY) ----------
st.markdown("""
<style>
.big-card {
    padding: 24px;
    border-radius: 18px;
    margin-bottom: 18px;
}
.card-title {
    font-size: 18px;
    color: #333333;
    margin-bottom: 10px;
}
.card-value {
    font-size: 38px;
    font-weight: 700;
    color: #111111;
}
.card-sub {
    font-size: 14px;
    color: #444444;
    margin-top: 6px;
}
</style>
""", unsafe_allow_html=True)

# ---------- SAMPLE VALUES (YOUR DATA STILL WORKS HERE) ----------
profit_loss = 38484.16
cost_basis = 366299.07
cash = 18690.64
total_value = 404783.23

# ---------- ACCOUNT COMMAND CENTER ----------
st.markdown("## 📊 Account Command Center")

# Total Value
st.markdown(f"""
<div class="big-card" style="background:#E6EBF2;">
    <div class="card-title">Total Account Value</div>
    <div class="card-value">${total_value:,.2f}</div>
    <div class="card-sub">Holdings + FDRXX cash</div>
</div>
""", unsafe_allow_html=True)

# Profit / Loss
st.markdown(f"""
<div class="big-card" style="background:#DDEBE5;">
    <div class="card-title">Profit / Loss</div>
    <div class="card-value">${profit_loss:,.2f}</div>
    <div class="card-sub">Total value minus contributions</div>
</div>
""", unsafe_allow_html=True)

# Cost Basis
st.markdown(f"""
<div class="big-card" style="background:#E6DDF0;">
    <div class="card-title">Invested Cost Basis</div>
    <div class="card-value">${cost_basis:,.2f}</div>
    <div class="card-sub">Total contributions invested</div>
</div>
""", unsafe_allow_html=True)

# Cash
st.markdown(f"""
<div class="big-card" style="background:#EDE4D8;">
    <div class="card-title">Available Cash (FDRXX)</div>
    <div class="card-value">${cash:,.2f}</div>
    <div class="card-sub">Ready to deploy</div>
</div>
""", unsafe_allow_html=True)

# ---------- MONTHLY INCOME SECTION (FIXED HTML RENDERING) ----------
st.markdown("## Monthly Income Goal")

goal = 8000
conservative = 2180
actual = 3449

progress = (actual / goal) * 100

st.markdown(f"""
<div class="big-card" style="background:#1B2A44; color:white;">
    <div style="font-size:48px; font-weight:700;">${goal:,}</div>
    <div style="margin-top:10px;">Realistic monthly income estimate</div>

    <div style="
        margin-top:16px;
        height:10px;
        background:#334155;
        border-radius:10px;
        overflow:hidden;">
        <div style="
            width:{progress}%;
            height:100%;
            background:linear-gradient(90deg,#22c55e,#4ade80);">
        </div>
    </div>

    <div style="margin-top:14px;">
        🛡 Conservative: ${conservative:,} &nbsp;&nbsp;
        📈 Actual: ${actual:,}
    </div>
</div>
""", unsafe_allow_html=True)
