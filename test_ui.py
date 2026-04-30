import json
import os
from datetime import datetime
from typing import Dict, List

import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except Exception:
    yf = None


# ============================================================
# SETTINGS
# ============================================================

st.set_page_config(page_title="Retirement Paycheck Dashboard", page_icon="💵", layout="wide")

GOAL_MONTHLY = 8000.0
REALISTIC_INCOME_FACTOR = 0.843
CONSERVATIVE_INCOME_FACTOR = 0.632


# ============================================================
# MOCK DATA (replace with your real state later)
# ============================================================

total_value = 404783.23
profit_loss = 38484.16
cash = 18690.64
contributions = total_value - profit_loss

actual_income = 3449.05
realistic_income = actual_income * REALISTIC_INCOME_FACTOR
conservative_income = actual_income * CONSERVATIVE_INCOME_FACTOR


# ============================================================
# UI COMPONENTS
# ============================================================

def hero_card(goal, realistic, conservative, actual):
    percent = realistic / goal * 100

    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #0f172a, #1e293b);
        padding: 28px;
        border-radius: 20px;
        margin-bottom: 20px;
        color: white;
    ">
        <div style="font-size:20px; opacity:0.85;">
            Monthly Income Goal
        </div>

        <div style="font-size:48px; font-weight:800; margin-top:5px;">
            ${goal:,.0f}
        </div>

        <div style="margin-top:10px; font-size:16px; opacity:0.85;">
            Realistic monthly income estimate • {percent:.1f}% of your goal
        </div>

        <div style="
            margin-top:16px;
            height:10px;
            background:#334155;
            border-radius:10px;
            overflow:hidden;
        ">
            <div style="
                width:{percent}%;
                height:100%;
                background:linear-gradient(90deg,#22c55e,#4ade80);
            "></div>
        </div>

        <div style="margin-top:14px; font-size:15px;">
            🛡 Conservative: ${conservative:,.0f} &nbsp;&nbsp; | &nbsp;&nbsp;
            📈 Actual: ${actual:,.0f}
        </div>
    </div>
    """, unsafe_allow_html=True)


def tier2_card(title, value, subtitle="", color="#f5f7fb"):
    st.markdown(f"""
    <div style="
        background: {color};
        padding: 20px;
        border-radius: 16px;
        margin-bottom: 14px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.06);
    ">
        <div style="font-size:18px; font-weight:600; margin-bottom:6px;">
            {title}
        </div>
        <div style="font-size:32px; font-weight:800;">
            {value}
        </div>
        <div style="font-size:14px; color:#555;">
            {subtitle}
        </div>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# LAYOUT
# ============================================================

# HERO
hero_card(
    GOAL_MONTHLY,
    realistic_income,
    conservative_income,
    actual_income
)

st.markdown("### 📊 Account Command Center")

# ROW 1
col1, col2 = st.columns(2)

with col1:
    tier2_card(
        "Total Account Value",
        f"${total_value:,.2f}",
        "Holdings + FDRXX cash",
        "#eef4ff"
    )

with col2:
    tier2_card(
        "Profit / Loss",
        f"${profit_loss:,.2f}",
        "Total value minus contributions",
        "#e9f7ef"
    )

# ROW 2
col3, col4 = st.columns(2)

with col3:
    tier2_card(
        "Invested Cost Basis",
        f"${contributions:,.2f}",
        "Total contributions invested",
        "#f3e8ff"
    )

with col4:
    tier2_card(
        "Available Cash (FDRXX)",
        f"${cash:,.2f}",
        "Ready to deploy",
        "#fff7ed"
    )


# ============================================================
# FOOTER / DEBUG (optional)
# ============================================================

with st.expander("Debug / Details"):
    st.write({
        "Goal": GOAL_MONTHLY,
        "Actual Income": actual_income,
        "Realistic": realistic_income,
        "Conservative": conservative_income
    })
