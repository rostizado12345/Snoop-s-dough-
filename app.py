import io
import json
import math
from datetime import datetime
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except Exception:
    yf = None


# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Retirement Paycheck Dashboard",
    page_icon="💵",
    layout="wide",
)

# ============================================================
# CONSTANTS
# ============================================================
GOAL_MONTHLY = 8000.0

# Income tier multipliers
REALISTIC_INCOME_FACTOR = 0.843
CONSERVATIVE_INCOME_FACTOR = 0.632

CASH_TICKER = "FDRXX"
CASH_PRICE = 1.00

DEFAULT_STARTING_CONTRIBUTIONS = 369000.00
DEFAULT_STARTING_CASH = 18690.50

DEFAULT_COLUMNS = [
    "ticker",
    "qty",
    "avg_cost",
    "manual_price",
    "target_weight",
    "annual_yield",
    "payout_frequency",
    "payout_months",
    "notes",
]

DEFAULT_ROWS = [
    ["AIPI", 0.0, 0.0, 0.0, 5.0, 0.3500, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", ""],
    ["CHPY", 0.0, 0.0, 0.0, 6.0, 0.1800, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", ""],
    ["DIVO", 0.0, 0.0, 0.0, 10.0, 0.0450, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", ""],
    ["FEPI", 0.0, 0.0, 0.0, 7.0, 0.2400, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", ""],
    ["GDXY", 0.0, 0.0, 0.0, 15.0, 0.3200, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", ""],
    ["IAU", 0.0, 0.0, 0.0, 4.0, 0.0000, "none", "", ""],
    ["IYRI", 0.0, 0.0, 0.0, 5.0, 0.0800, "quarterly", "3,6,9,12", ""],
    ["IWMI", 0.0, 0.0, 0.0, 4.0, 0.1200, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", ""],
    ["MLPI", 0.0, 0.0, 0.0, 4.0, 0.0800, "quarterly", "2,5,8,11", ""],
    ["QQQI", 0.0, 0.0, 0.0, 10.0, 0.1450, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", ""],
    ["SPYI", 0.0, 0.0, 0.0, 12.0, 0.1200, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", ""],
    ["SVOL", 0.0, 0.0, 0.0, 6.0, 0.1600, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", ""],
    ["TLTW", 0.0, 0.0, 0.0, 7.0, 0.1500, "monthly", "1,2,3,4,5,6,7,8,9,10,11,12", ""],
]

TX_COLUMNS = [
    "date",
    "type",
    "amount",
    "ticker",
    "price",
    "notes",
]

ALLOWED_TX_TYPES = [
    "contribution",   # money added from outside the tracked account
    "withdrawal",     # money removed from the tracked account
    "deploy_cash",    # cash used to buy a holding
    "sell_to_cash",   # sell a holding and move proceeds to cash
]

MONTH_NAMES = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}


# ============================================================
# HELPERS
# ============================================================
def safe_float(value, default=0.0) -> float:
    try:
        if value is None or (isinstance(value, str) and value.strip() == ""):
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def clean_ticker(value: str) -> str:
    if value is None:
        return ""
    return str(value).strip().upper()


def parse_months(value: str) -> List[int]:
    if value is None:
        return []
    text = str(value).strip()
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


def format_money(value: float) -> str:
    return f"${value:,.2f}"


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def normalize_holdings_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        df = pd.DataFrame(DEFAULT_ROWS, columns=DEFAULT_COLUMNS)

    for col in DEFAULT_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[DEFAULT_COLUMNS].copy()

    # normalize data
    df["ticker"] = df["ticker"].apply(clean_ticker)
    df = df[df["ticker"] != ""].copy()
    df = df[df["ticker"] != CASH_TICKER].copy()

    numeric_cols = ["qty", "avg_cost", "manual_price", "target_weight", "annual_yield"]
    for col in numeric_cols:
        df[col] = df[col].apply(safe_float)

    text_cols = ["payout_frequency", "payout_months", "notes"]
    for col in text_cols:
        df[col] = df[col].fillna("").astype(str)

    df = df.drop_duplicates(subset=["ticker"], keep="first").reset_index(drop=True)
    return df


def normalize_tx_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=TX_COLUMNS)

    for col in TX_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[TX_COLUMNS].copy()
    df["date"] = df["date"].fillna("").astype(str)
    df["type"] = df["type"].fillna("").astype(str)
    df["ticker"] = df["ticker"].fillna("").astype(str).apply(clean_ticker)
    df["notes"] = df["notes"].fillna("").astype(str)
    df["amount"] = df["amount"].apply(safe_float)
    df["price"] = df["price"].apply(safe_float)

    df = df[df["type"].isin(ALLOWED_TX_TYPES)].reset_index(drop=True)
    return df


@st.cache_data(show_spinner=False, ttl=900)
def fetch_prices(tickers: Tuple[str, ...]) -> Dict[str, float]:
    prices: Dict[str, float] = {}
    if not tickers:
        return prices
    if yf is None:
        return prices

    try:
        data = yf.download(
            tickers=list(tickers),
            period="5d",
            interval="1d",
            auto_adjust=False,
            progress=False,
            group_by="ticker",
            threads=True,
        )
    except Exception:
        return prices

    try:
        # Multi-ticker
        if isinstance(data.columns, pd.MultiIndex):
            for t in tickers:
                try:
                    if t in data.columns.get_level_values(0):
                        close_series = data[t]["Close"].dropna()
                        if not close_series.empty:
                            prices[t] = float(close_series.iloc[-1])
                except Exception:
                    pass
        else:
            # Single ticker
            close_series = data["Close"].dropna()
            if not close_series.empty and len(tickers) == 1:
                prices[tickers[0]] = float(close_series.iloc[-1])
    except Exception:
        pass

    return prices


def get_effective_price(row: pd.Series, live_prices: Dict[str, float]) -> float:
    manual_price = safe_float(row.get("manual_price", 0.0))
    ticker = clean_ticker(row.get("ticker", ""))
    if manual_price > 0:
        return manual_price
    return safe_float(live_prices.get(ticker, 0.0))


def build_valuation_df(holdings_df: pd.DataFrame) -> pd.DataFrame:
    tickers = tuple(sorted([t for t in holdings_df["ticker"].astype(str).tolist() if t]))
    live_prices = fetch_prices(tickers)

    df = holdings_df.copy()

    df["ticker"] = df["ticker"].apply(clean_ticker)
    df["qty"] = df["qty"].apply(safe_float)
    df["avg_cost"] = df["avg_cost"].apply(safe_float)
    df["manual_price"] = df["manual_price"].apply(safe_float)
    df["target_weight"] = df["target_weight"].apply(safe_float)
    df["annual_yield"] = df["annual_yield"].apply(safe_float)

    df["price"] = df.apply(lambda row: get_effective_price(row, live_prices), axis=1)
    df["cost_basis"] = df["qty"] * df["avg_cost"]
    df["market_value"] = df["qty"] * df["price"]
    df["position_gain_loss"] = df["market_value"] - df["cost_basis"]
    return df


def compute_cash_and_contributions(
    starting_cash: float,
    starting_contributions: float,
    tx_df: pd.DataFrame,
) -> Tuple[float, float]:
    cash = safe_float(starting_cash)
    net_contributions = safe_float(starting_contributions)

    if tx_df.empty:
        return cash, net_contributions

    for _, row in tx_df.iterrows():
        tx_type = str(row["type"]).strip()
        amount = safe_float(row["amount"])

        if amount < 0:
            amount = abs(amount)

        if tx_type == "contribution":
            cash += amount
            net_contributions += amount

        elif tx_type == "withdrawal":
            cash -= amount
            net_contributions -= amount

        elif tx_type == "deploy_cash":
            cash -= amount

        elif tx_type == "sell_to_cash":
            cash += amount

    return cash, net_contributions


def monthly_income_from_row(row: pd.Series) -> float:
    annual_yield = safe_float(row.get("annual_yield", 0.0))
    market_value = safe_float(row.get("market_value", 0.0))
    if annual_yield <= 0 or market_value <= 0:
        return 0.0
    annual_income = market_value * annual_yield
    return annual_income / 12.0


def annual_income_from_row(row: pd.Series) -> float:
    annual_yield = safe_float(row.get("annual_yield", 0.0))
    market_value = safe_float(row.get("market_value", 0.0))
    if annual_yield <= 0 or market_value <= 0:
        return 0.0
    return market_value * annual_yield


def build_monthly_schedule(df: pd.DataFrame) -> pd.DataFrame:
    schedule = []
    for month in range(1, 13):
        actual = 0.0
        realistic = 0.0
        conservative = 0.0

        for _, row in df.iterrows():
            annual_income = annual_income_from_row(row)
            freq = str(row.get("payout_frequency", "")).strip().lower()
            payout_months = parse_months(row.get("payout_months", ""))

            if annual_income <= 0:
                continue

            if freq == "monthly":
                month_income = annual_income / 12.0
            elif freq == "quarterly":
                if month in payout_months:
                    month_income = annual_income / max(len(payout_months), 1)
                else:
                    month_income = 0.0
            elif freq == "semiannual":
                if month in payout_months:
                    month_income = annual_income / max(len(payout_months), 1)
                else:
                    month_income = 0.0
            elif freq == "annual":
                if month in payout_months:
                    month_income = annual_income / max(len(payout_months), 1)
                else:
                    month_income = 0.0
            else:
                month_income = 0.0

            actual += month_income
            realistic += month_income * REALISTIC_INCOME_FACTOR
            conservative += month_income * CONSERVATIVE_INCOME_FACTOR

        schedule.append(
            {
                "Month": MONTH_NAMES[month],
                "Conservative": conservative,
                "Realistic": realistic,
                "Actual": actual,
            }
        )

    return pd.DataFrame(schedule)


def validate_state(
    valuation_df: pd.DataFrame,
    cash_value: float,
    total_account_value: float,
    total_contributions: float,
    profit_loss: float,
) -> List[str]:
    errors = []

    holdings_value = valuation_df["market_value"].sum() if not valuation_df.empty else 0.0
    recomputed_total = holdings_value + cash_value
    recomputed_profit = recomputed_total - total_contributions

    if cash_value < -0.005:
        errors.append("Available cash went negative. A deploy or withdrawal is larger than available cash.")

    if abs(total_account_value - recomputed_total) > 0.01:
        errors.append("Total account value does not equal holdings value plus cash.")

    if abs(profit_loss - recomputed_profit) > 0.01:
        errors.append("Profit/loss does not equal total account value minus total contributions.")

    if not valuation_df.empty:
        if (valuation_df["qty"] < -0.000001).any():
            errors.append("One or more holdings have negative quantity.")
        if (valuation_df["avg_cost"] < -0.000001).any():
            errors.append("One or more holdings have negative average cost.")
        if (valuation_df["price"] < -0.000001).any():
            errors.append("One or more holdings have negative price.")
        if (valuation_df["annual_yield"] < -0.000001).any():
            errors.append("One or more holdings have negative annual yield.")

    return errors


def add_transaction(tx_type: str, amount: float, ticker: str = "", price: float = 0.0, notes: str = ""):
    amount = safe_float(amount)
    price = safe_float(price)

    if amount <= 0:
        st.error("Amount must be greater than zero.")
        return

    row = {
        "date": today_str(),
        "type": tx_type,
        "amount": amount,
        "ticker": clean_ticker(ticker),
        "price": price,
        "notes": notes,
    }

    st.session_state["transactions_df"] = pd.concat(
        [st.session_state["transactions_df"], pd.DataFrame([row])],
        ignore_index=True,
    )
    st.success(f"Added transaction: {tx_type} {format_money(amount)}")


def upsert_holding_purchase(ticker: str, amount: float, price: float):
    ticker = clean_ticker(ticker)
    amount = safe_float(amount)
    price = safe_float(price)

    if not ticker:
        st.error("Ticker is required.")
        return False

    if amount <= 0 or price <= 0:
        st.error("Deploy amount and price must both be greater than zero.")
        return False

    shares_bought = amount / price
    df = st.session_state["holdings_df"].copy()

    if ticker not in df["ticker"].tolist():
        new_row = {
            "ticker": ticker,
            "qty": shares_bought,
            "avg_cost": price,
            "manual_price": 0.0,
            "target_weight": 0.0,
            "annual_yield": 0.0,
            "payout_frequency": "monthly",
            "payout_months": "1,2,3,4,5,6,7,8,9,10,11,12",
            "notes": "",
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    else:
        idx = df.index[df["ticker"] == ticker][0]
        old_qty = safe_float(df.at[idx, "qty"])
        old_avg = safe_float(df.at[idx, "avg_cost"])
        new_qty = old_qty + shares_bought
        new_avg = ((old_qty * old_avg) + amount) / new_qty if new_qty > 0 else price
        df.at[idx, "qty"] = new_qty
        df.at[idx, "avg_cost"] = new_avg

    st.session_state["holdings_df"] = normalize_holdings_df(df)
    return True


def reduce_holding_sale(ticker: str, amount: float, price: float):
    ticker = clean_ticker(ticker)
    amount = safe_float(amount)
    price = safe_float(price)

    if not ticker:
        st.error("Ticker is required.")
        return False

    if amount <= 0 or price <= 0:
        st.error("Sale amount and price must both be greater than zero.")
        return False

    shares_to_sell = amount / price
    df = st.session_state["holdings_df"].copy()

    if ticker not in df["ticker"].tolist():
        st.error(f"{ticker} is not in holdings.")
        return False

    idx = df.index[df["ticker"] == ticker][0]
    old_qty = safe_float(df.at[idx, "qty"])

    if shares_to_sell > old_qty + 1e-9:
        st.error(f"Cannot sell more {ticker} than you hold.")
        return False

    new_qty = old_qty - shares_to_sell
    df.at[idx, "qty"] = max(new_qty, 0.0)

    st.session_state["holdings_df"] = normalize_holdings_df(df)
    return True


def build_snapshot_json() -> str:
    payload = {
        "starting_cash": safe_float(st.session_state["starting_cash"]),
        "starting_contributions": safe_float(st.session_state["starting_contributions"]),
        "holdings": st.session_state["holdings_df"].to_dict(orient="records"),
        "transactions": st.session_state["transactions_df"].to_dict(orient="records"),
        "exported_at": datetime.now().isoformat(),
        "version": 1,
    }
    return json.dumps(payload, indent=2)


def load_snapshot_json(uploaded_bytes: bytes):
    payload = json.loads(uploaded_bytes.decode("utf-8"))

    holdings = pd.DataFrame(payload.get("holdings", []))
    transactions = pd.DataFrame(payload.get("transactions", []))
    starting_cash = safe_float(payload.get("starting_cash", DEFAULT_STARTING_CASH))
    starting_contributions = safe_float(payload.get("starting_contributions", DEFAULT_STARTING_CONTRIBUTIONS))

    st.session_state["starting_cash"] = starting_cash
    st.session_state["starting_contributions"] = starting_contributions
    st.session_state["holdings_df"] = normalize_holdings_df(holdings)
    st.session_state["transactions_df"] = normalize_tx_df(transactions)


# ============================================================
# SESSION STATE INIT
# ============================================================
if "starting_cash" not in st.session_state:
    st.session_state["starting_cash"] = DEFAULT_STARTING_CASH

if "starting_contributions" not in st.session_state:
    st.session_state["starting_contributions"] = DEFAULT_STARTING_CONTRIBUTIONS

if "holdings_df" not in st.session_state:
    st.session_state["holdings_df"] = normalize_holdings_df(pd.DataFrame(DEFAULT_ROWS, columns=DEFAULT_COLUMNS))

if "transactions_df" not in st.session_state:
    st.session_state["transactions_df"] = normalize_tx_df(pd.DataFrame(columns=TX_COLUMNS))


# ============================================================
# HEADER
# ============================================================
st.title("💵 Retirement Paycheck Dashboard")
st.caption("Locked cash logic • ledger-driven contributions • FDRXX handled as dedicated cash, not a normal holding")


# ============================================================
# SIDEBAR - SNAPSHOT / SYSTEM TOOLS
# ============================================================
with st.sidebar:
    st.header("System Tools")

    snapshot_json = build_snapshot_json()
    st.download_button(
        "Download Snapshot Backup",
        data=snapshot_json,
        file_name=f"retirement_dashboard_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
        use_container_width=True,
    )

    uploaded_snapshot = st.file_uploader("Restore Snapshot Backup", type=["json"])
    if uploaded_snapshot is not None:
        try:
            load_snapshot_json(uploaded_snapshot.read())
            st.success("Snapshot restored.")
        except Exception as e:
            st.error(f"Could not restore snapshot: {e}")

    st.divider()

    st.subheader("Tracked Account Starting Values")
    st.session_state["starting_contributions"] = st.number_input(
        "Starting Total Contributions",
        min_value=0.0,
        value=safe_float(st.session_state["starting_contributions"]),
        step=1000.0,
        format="%.2f",
        help="This is the starting net amount contributed to the tracked account before any new ledger events below.",
    )
    st.session_state["starting_cash"] = st.number_input(
        f"Starting Available Cash ({CASH_TICKER})",
        min_value=0.0,
        value=safe_float(st.session_state["starting_cash"]),
        step=1000.0,
        format="%.2f",
        help=f"This is the starting cash sweep value for {CASH_TICKER} before any new ledger events below.",
    )

    st.divider()
    st.info(
        "Rule of thumb:\n\n"
        "- Add New Money = outside money enters account\n"
        "- Deploy Cash = existing cash buys a holding\n"
        "- Sell to Cash = holding becomes cash\n"
        "- Withdrawal = money leaves account"
    )


# ============================================================
# ACTION PANEL
# ============================================================
st.subheader("Cash Flow Actions")

action_tab1, action_tab2, action_tab3, action_tab4 = st.tabs(
    ["Add New Money", "Deploy Cash", "Sell To Cash", "Withdraw Money"]
)

with action_tab1:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("+ $1,000", use_container_width=True):
            add_transaction("contribution", 1000.0, notes="Quick add")
    with c2:
        if st.button("+ $5,000", use_container_width=True):
            add_transaction("contribution", 5000.0, notes="Quick add")
    with c3:
        if st.button("+ $10,000", use_container_width=True):
            add_transaction("contribution", 10000.0, notes="Quick add")
    with c4:
        if st.button("+ $32,000", use_container_width=True):
            add_transaction("contribution", 32000.0, notes="Quick add")

    with st.form("custom_contribution_form"):
        add_amount = st.number_input("Custom New Money Amount", min_value=0.0, value=0.0, step=1000.0, format="%.2f")
        add_notes = st.text_input("Notes", value="")
        submitted = st.form_submit_button("Add New Money")
        if submitted:
            add_transaction("contribution", add_amount, notes=add_notes)

with action_tab2:
    current_cash_preview, current_contrib_preview = compute_cash_and_contributions(
        st.session_state["starting_cash"],
        st.session_state["starting_contributions"],
        st.session_state["transactions_df"],
    )
    st.write(f"Available cash right now: **{format_money(current_cash_preview)}**")

    deploy_ticker = st.selectbox(
        "Deploy cash into ticker",
        options=sorted(st.session_state["holdings_df"]["ticker"].tolist()),
        index=0 if not st.session_state["holdings_df"].empty else None,
    ) if not st.session_state["holdings_df"].empty else st.text_input("Ticker", value="")

    with st.form("deploy_cash_form"):
        deploy_amount = st.number_input("Deploy Amount", min_value=0.0, value=0.0, step=1000.0, format="%.2f")
        deploy_price = st.number_input("Execution Price", min_value=0.0, value=0.0, step=0.01, format="%.4f")
        deploy_notes = st.text_input("Notes ", value="")
        deploy_submit = st.form_submit_button("Deploy Cash")
        if deploy_submit:
            if deploy_amount > current_cash_preview + 1e-9:
                st.error("Cannot deploy more cash than is available.")
            else:
                if upsert_holding_purchase(str(deploy_ticker), deploy_amount, deploy_price):
                    add_transaction(
                        "deploy_cash",
                        deploy_amount,
                        ticker=str(deploy_ticker),
                        price=deploy_price,
                        notes=deploy_notes,
                    )

with action_tab3:
    if st.session_state["holdings_df"].empty:
        st.info("No holdings available to sell.")
    else:
        sell_ticker = st.selectbox(
            "Sell ticker into cash",
            options=sorted(st.session_state["holdings_df"]["ticker"].tolist()),
            key="sell_ticker_select",
        )
        with st.form("sell_to_cash_form"):
            sell_amount = st.number_input("Sale Amount", min_value=0.0, value=0.0, step=1000.0, format="%.2f")
            sell_price = st.number_input("Sale Price", min_value=0.0, value=0.0, step=0.01, format="%.4f")
            sell_notes = st.text_input("Sale Notes", value="")
            sell_submit = st.form_submit_button("Sell To Cash")
            if sell_submit:
                if reduce_holding_sale(str(sell_ticker), sell_amount, sell_price):
                    add_transaction(
                        "sell_to_cash",
                        sell_amount,
                        ticker=str(sell_ticker),
                        price=sell_price,
                        notes=sell_notes,
                    )

with action_tab4:
    current_cash_preview_2, _ = compute_cash_and_contributions(
        st.session_state["starting_cash"],
        st.session_state["starting_contributions"],
        st.session_state["transactions_df"],
    )
    st.write(f"Available cash right now: **{format_money(current_cash_preview_2)}**")

    with st.form("withdrawal_form"):
        withdrawal_amount = st.number_input("Withdrawal Amount", min_value=0.0, value=0.0, step=1000.0, format="%.2f")
        withdrawal_notes = st.text_input("Withdrawal Notes", value="")
        withdrawal_submit = st.form_submit_button("Withdraw Money")
        if withdrawal_submit:
            if withdrawal_amount > current_cash_preview_2 + 1e-9:
                st.error("Cannot withdraw more cash than is available.")
            else:
                add_transaction("withdrawal", withdrawal_amount, notes=withdrawal_notes)


# ============================================================
# HOLDINGS EDITOR
# ============================================================
st.divider()
st.subheader("Portfolio Holdings")
st.caption(f"{CASH_TICKER} is handled separately as cash and is not part of this table.")

edited_holdings = st.data_editor(
    st.session_state["holdings_df"],
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    key="holdings_editor",
    column_config={
        "ticker": st.column_config.TextColumn("Ticker"),
        "qty": st.column_config.NumberColumn("Qty", format="%.6f"),
        "avg_cost": st.column_config.NumberColumn("Avg Cost", format="%.4f"),
        "manual_price": st.column_config.NumberColumn("Manual Price", format="%.4f"),
        "target_weight": st.column_config.NumberColumn("Target Weight %", format="%.2f"),
        "annual_yield": st.column_config.NumberColumn("Annual Yield", format="%.4f"),
        "payout_frequency": st.column_config.SelectboxColumn(
            "Payout Frequency",
            options=["none", "monthly", "quarterly", "semiannual", "annual"],
        ),
        "payout_months": st.column_config.TextColumn("Payout Months"),
        "notes": st.column_config.TextColumn("Notes"),
    },
)

if st.button("Save Holdings Table", use_container_width=True):
    st.session_state["holdings_df"] = normalize_holdings_df(edited_holdings)
    st.success("Holdings saved.")


# ============================================================
# TRANSACTION LEDGER
# ============================================================
st.divider()
st.subheader("Transaction Ledger")
st.caption("This is the source of truth for cash movement and contributions.")

edited_tx = st.data_editor(
    st.session_state["transactions_df"],
    num_rows="dynamic",
    use_container_width=True,
    hide_index=True,
    key="tx_editor",
    column_config={
        "date": st.column_config.TextColumn("Date"),
        "type": st.column_config.SelectboxColumn("Type", options=ALLOWED_TX_TYPES),
        "amount": st.column_config.NumberColumn("Amount", format="%.2f"),
        "ticker": st.column_config.TextColumn("Ticker"),
        "price": st.column_config.NumberColumn("Price", format="%.4f"),
        "notes": st.column_config.TextColumn("Notes"),
    },
)

c_tx1, c_tx2 = st.columns(2)
with c_tx1:
    if st.button("Save Ledger", use_container_width=True):
        st.session_state["transactions_df"] = normalize_tx_df(edited_tx)
        st.success("Ledger saved.")
with c_tx2:
    if st.button("Clear Ledger", use_container_width=True):
        st.session_state["transactions_df"] = pd.DataFrame(columns=TX_COLUMNS)
        st.success("Ledger cleared.")


# ============================================================
# CALCULATIONS
# ============================================================
holdings_df = normalize_holdings_df(st.session_state["holdings_df"])
tx_df = normalize_tx_df(st.session_state["transactions_df"])

valuation_df = build_valuation_df(holdings_df)

cash_value, total_contributions = compute_cash_and_contributions(
    st.session_state["starting_cash"],
    st.session_state["starting_contributions"],
    tx_df,
)

holdings_value = valuation_df["market_value"].sum() if not valuation_df.empty else 0.0
invested_cost_basis = valuation_df["cost_basis"].sum() if not valuation_df.empty else 0.0
position_gain_loss = valuation_df["position_gain_loss"].sum() if not valuation_df.empty else 0.0

total_account_value = holdings_value + cash_value
profit_loss = total_account_value - total_contributions

actual_monthly_income = sum(monthly_income_from_row(row) for _, row in valuation_df.iterrows())
realistic_monthly_income = actual_monthly_income * REALISTIC_INCOME_FACTOR
conservative_monthly_income = actual_monthly_income * CONSERVATIVE_INCOME_FACTOR

actual_annual_income = actual_monthly_income * 12.0
realistic_annual_income = realistic_monthly_income * 12.0
conservative_annual_income = conservative_monthly_income * 12.0

goal_progress = min(max(realistic_monthly_income / GOAL_MONTHLY, 0.0), 1.0) if GOAL_MONTHLY > 0 else 0.0

validation_errors = validate_state(
    valuation_df=valuation_df,
    cash_value=cash_value,
    total_account_value=total_account_value,
    total_contributions=total_contributions,
    profit_loss=profit_loss,
)

# ============================================================
# RECONCILIATION STATUS
# ============================================================
st.divider()
st.subheader("Reconciliation Status")

if validation_errors:
    st.error("Reconciliation FAILED")
    for err in validation_errors:
        st.write(f"- {err}")
else:
    st.success("Reconciliation PASSED")

r1, r2 = st.columns(2)
with r1:
    st.write(f"**Holdings + Cash** = {format_money(holdings_value)} + {format_money(cash_value)} = **{format_money(total_account_value)}**")
with r2:
    st.write(f"**Total - Contributions** = {format_money(total_account_value)} - {format_money(total_contributions)} = **{format_money(profit_loss)}**")


# ============================================================
# TOP METRICS
# ============================================================
st.divider()
m1, m2, m3, m4, m5 = st.columns(5)

m1.metric("Total Account Value", format_money(total_account_value))
m2.metric("Profit / Loss", format_money(profit_loss))
m3.metric("Holdings Value", format_money(holdings_value))
m4.metric(f"Available Cash ({CASH_TICKER})", format_money(cash_value))
m5.metric("Total Contributions", format_money(total_contributions))

m6, m7, m8, m9 = st.columns(4)
m6.metric("Invested Cost Basis", format_money(invested_cost_basis))
m7.metric("Holdings Gain / Loss", format_money(position_gain_loss))
m8.metric("Goal Monthly", format_money(GOAL_MONTHLY))
m9.metric("Goal Progress", f"{goal_progress * 100:.1f}%")

st.progress(goal_progress)


# ============================================================
# INCOME METRICS
# ============================================================
st.divider()
st.subheader("Monthly Income")

i1, i2, i3 = st.columns(3)
i1.metric("Conservative", format_money(conservative_monthly_income))
i2.metric("Realistic", format_money(realistic_monthly_income))
i3.metric("Actual", format_money(actual_monthly_income))

st.subheader("Annual Income")
a1, a2, a3 = st.columns(3)
a1.metric("Conservative", format_money(conservative_annual_income))
a2.metric("Realistic", format_money(realistic_annual_income))
a3.metric("Actual", format_money(actual_annual_income))


# ============================================================
# HOLDINGS DETAIL
# ============================================================
st.divider()
st.subheader("Holdings Detail")

if valuation_df.empty:
    st.info("No holdings yet.")
else:
    detail_df = valuation_df.copy()
    total_for_pct = detail_df["market_value"].sum()
    detail_df["% of Holdings"] = detail_df["market_value"].apply(
        lambda x: (x / total_for_pct * 100.0) if total_for_pct > 0 else 0.0
    )
    detail_df["Target $"] = detail_df["target_weight"].apply(
        lambda w: holdings_value * (safe_float(w) / 100.0)
    )
    detail_df["Dollar Gap"] = detail_df["Target $"] - detail_df["market_value"]
    detail_df["Monthly Income"] = detail_df["market_value"] * detail_df["annual_yield"] / 12.0
    detail_df["Annual Income"] = detail_df["market_value"] * detail_df["annual_yield"]

    display_cols = [
        "ticker",
        "qty",
        "avg_cost",
        "price",
        "cost_basis",
        "market_value",
        "position_gain_loss",
        "% of Holdings",
        "target_weight",
        "Target $",
        "Dollar Gap",
        "annual_yield",
        "Monthly Income",
        "Annual Income",
        "payout_frequency",
        "payout_months",
        "notes",
    ]

    st.dataframe(
        detail_df[display_cols],
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# MONTHLY PAYOUT SCHEDULE
# ============================================================
st.divider()
st.subheader("Estimated Monthly Payout Schedule")

schedule_df = build_monthly_schedule(valuation_df)

if not schedule_df.empty:
    st.dataframe(schedule_df, use_container_width=True, hide_index=True)
else:
    st.info("No schedule available yet.")


# ============================================================
# RAW LEDGER VIEW
# ============================================================
st.divider()
st.subheader("Ledger Summary")

if tx_df.empty:
    st.write("No ledger events yet.")
else:
    summary = tx_df.groupby("type", dropna=False)["amount"].sum().reset_index()
    st.dataframe(summary, use_container_width=True, hide_index=True)

    st.dataframe(
        tx_df.sort_values(by=["date"]).reset_index(drop=True),
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# FOOTER NOTES
# ============================================================
st.divider()
st.caption(
    f"{CASH_TICKER} is excluded from holdings value and excluded from income calculations. "
    "All totals are derived fresh on each run. The ledger controls cash and contribution math."
)
