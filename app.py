import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except Exception:
    yf = None


st.set_page_config(page_title="Retirement Paycheck Dashboard", layout="wide")

APP_BASELINE_VERSION = "2026-07-10-blank-screen-repair-v15"
STATE_SCHEMA_VERSION = 2

GOAL_MONTHLY = 8000.0
REALISTIC_INCOME_FACTOR = 0.843
CONSERVATIVE_INCOME_FACTOR = 0.632

STATE_DIR = Path.home() / ".retirement_dashboard_state"
STATE_FILE = STATE_DIR / "retirement_dashboard_state.json"
BACKUP_FILE = STATE_DIR / "retirement_dashboard_state_backup.json"
LAST_GOOD_FILE = STATE_DIR / "retirement_dashboard_state_last_good.json"
GITHUB_STATE_DEFAULT_PATH = "retirement_dashboard_state.json"

DEFAULT_COLUMNS = [
    "ticker", "qty", "avg_cost", "manual_price", "target_weight",
    "annual_yield", "payout_frequency", "payout_months", "notes",
]

DEFAULT_ROWS = [
    ["AIPI", 706.966000, 34.046850, 35.8650, 5.0, 0.124, "monthly", "all", ""],
    ["CHPY", 474.719000, 56.069390, 81.9401, 6.0, 0.050, "monthly", "all", ""],
    ["DIVO", 1404.379000, 44.979583, 45.7050, 10.0, 0.048, "monthly", "all", ""],
    ["FEPI", 929.650000, 39.990480, 41.9500, 7.0, 0.120, "monthly", "all", ""],
    ["GDXY", 3619.685000, 13.105740, 10.2213, 15.0, 0.180, "monthly", "all", ""],
    ["IAU", 174.866000, 84.635660, 76.4900, 4.0, 0.000, "none", "none", ""],
    ["IWMI", 318.115000, 48.214810, 53.0050, 4.0, 0.120, "monthly", "all", ""],
    ["IYRI", 385.111000, 46.933390, 49.6700, 5.0, 0.080, "monthly", "all", ""],
    ["MLPI", 337.131000, 56.787530, 55.9900, 4.0, 0.080, "quarterly", "3,6,9,12", ""],
    ["QQQI", 727.773000, 50.462520, 55.0500, 10.0, 0.140, "monthly", "all", ""],
    ["SPYI", 1370.585000, 49.669172, 52.1900, 12.0, 0.120, "monthly", "all", ""],
    ["SVOL", 1721.341000, 15.515646, 15.7000, 6.0, 0.160, "monthly", "all", ""],
    ["TLTW", 1031.331000, 22.295132, 22.5150, 7.0, 0.120, "monthly", "all", ""],
]

DEFAULT_CASH_FDRXX = 207923.13
DEFAULT_TOTAL_CONTRIBUTIONS = 561299.07
DEFAULT_PROTECTED_MIN = 561299.07

SMART_INCOME_TIERS = {
    "Tier 1": ["SPYI", "DIVO"],
    "Tier 2": ["QQQI", "FEPI"],
    "Tier 3": ["SVOL", "IYRI", "TLTW"],
}
SMART_INCOME_SPLITS = {"Tier 1": 0.75, "Tier 2": 0.20, "Tier 3": 0.05}


def now_text():
    return datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")


def to_float(value, default=0.0):
    try:
        if value is None or pd.isna(value):
            return float(default)
        if isinstance(value, str):
            value = value.replace("$", "").replace(",", "").replace("%", "").strip()
            if not value:
                return float(default)
        return float(value)
    except Exception:
        return float(default)


def money(value):
    return f"${to_float(value):,.2f}"


def normalize_df(value):
    df = value.copy() if isinstance(value, pd.DataFrame) else pd.DataFrame(value or [])
    for col in DEFAULT_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0 if col in {"qty", "avg_cost", "manual_price", "target_weight", "annual_yield"} else ""
    for col in ["qty", "avg_cost", "manual_price", "target_weight", "annual_yield"]:
        df[col] = df[col].apply(to_float)
    df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
    df["payout_frequency"] = df["payout_frequency"].astype(str).str.strip().replace("", "monthly")
    df["payout_months"] = df["payout_months"].astype(str).str.strip().replace("", "all")
    df["notes"] = df["notes"].astype(str)
    return df[df["ticker"] != ""][DEFAULT_COLUMNS].reset_index(drop=True)


def default_state():
    return {
        "state_schema_version": STATE_SCHEMA_VERSION,
        "app_baseline_version": APP_BASELINE_VERSION,
        "portfolio_df": normalize_df(pd.DataFrame(DEFAULT_ROWS, columns=DEFAULT_COLUMNS)),
        "cash_fdrxx": DEFAULT_CASH_FDRXX,
        "total_contributions": DEFAULT_TOTAL_CONTRIBUTIONS,
        "protected_min_contributions": DEFAULT_PROTECTED_MIN,
        "use_live_prices": True,
        "auto_sync_prices": True,
        "last_price_sync": "",
        "last_saved": now_text(),
        "last_saved_epoch": time.time_ns(),
        "last_deploy_message": "Loaded protected July 10 portfolio baseline.",
        "last_cash_message": f"FDRXX cash baseline: {money(DEFAULT_CASH_FDRXX)}.",
    }


def normalize_state(raw):
    base = default_state()
    raw = raw or {}
    records = raw.get("portfolio_df", raw.get("portfolio", []))
    if records:
        base["portfolio_df"] = normalize_df(records)
    for key in ["cash_fdrxx", "total_contributions", "protected_min_contributions"]:
        base[key] = round(to_float(raw.get(key, base[key]), base[key]), 2)
    base["protected_min_contributions"] = max(
        base["protected_min_contributions"], DEFAULT_PROTECTED_MIN
    )
    base["use_live_prices"] = bool(raw.get("use_live_prices", base["use_live_prices"]))
    base["auto_sync_prices"] = bool(raw.get("auto_sync_prices", base["auto_sync_prices"]))
    for key in ["last_price_sync", "last_saved", "last_deploy_message", "last_cash_message"]:
        base[key] = str(raw.get(key, base[key]))
    base["last_saved_epoch"] = int(to_float(raw.get("last_saved_epoch", 0), 0))
    base["app_baseline_version"] = APP_BASELINE_VERSION
    base["state_schema_version"] = STATE_SCHEMA_VERSION
    return base


def serializable_state(state, refresh_timestamp=False):
    df = normalize_df(state["portfolio_df"])
    saved = now_text() if refresh_timestamp else str(state.get("last_saved", "") or now_text())
    epoch = time.time_ns() if refresh_timestamp else int(state.get("last_saved_epoch", 0) or time.time_ns())
    return {
        "state_schema_version": STATE_SCHEMA_VERSION,
        "app_baseline_version": APP_BASELINE_VERSION,
        "portfolio_df": df.to_dict(orient="records"),
        "cash_fdrxx": round(to_float(state["cash_fdrxx"]), 2),
        "total_contributions": round(to_float(state["total_contributions"]), 2),
        "protected_min_contributions": round(
            max(to_float(state.get("protected_min_contributions")), DEFAULT_PROTECTED_MIN), 2
        ),
        "use_live_prices": bool(state.get("use_live_prices", True)),
        "auto_sync_prices": bool(state.get("auto_sync_prices", True)),
        "last_price_sync": str(state.get("last_price_sync", "")),
        "last_saved": saved,
        "last_saved_epoch": epoch,
        "last_deploy_message": str(state.get("last_deploy_message", "")),
        "last_cash_message": str(state.get("last_cash_message", "")),
    }


def atomic_write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.{time.time_ns()}.tmp")
    try:
        with open(temp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        try:
            if temp.exists():
                temp.unlink()
        except Exception:
            pass


def read_local_state():
    # No network activity occurs here. Startup can therefore never be held up by GitHub.
    candidates = []
    for path in [STATE_FILE, LAST_GOOD_FILE, BACKUP_FILE]:
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as handle:
                    state = normalize_state(json.load(handle))
                if state["total_contributions"] >= state["protected_min_contributions"]:
                    candidates.append((state["last_saved_epoch"], path, state))
        except Exception:
            continue
    if candidates:
        _, path, state = max(candidates, key=lambda item: item[0])
        return state, f"Loaded local protected snapshot: {path}"
    return default_state(), "Loaded protected built-in baseline."


def save_local_state():
    state = {
        "portfolio_df": st.session_state.portfolio_df,
        "cash_fdrxx": st.session_state.cash_fdrxx,
        "total_contributions": st.session_state.total_contributions,
        "protected_min_contributions": st.session_state.protected_min_contributions,
        "use_live_prices": st.session_state.use_live_prices,
        "auto_sync_prices": st.session_state.auto_sync_prices,
        "last_price_sync": st.session_state.last_price_sync,
        "last_deploy_message": st.session_state.last_deploy_message,
        "last_cash_message": st.session_state.last_cash_message,
    }
    payload = serializable_state(state, refresh_timestamp=True)
    for path in [STATE_FILE, BACKUP_FILE, LAST_GOOD_FILE]:
        atomic_write(path, payload)
    st.session_state.last_saved = payload["last_saved"]
    st.session_state.last_saved_epoch = payload["last_saved_epoch"]
    return payload


def get_secret(name, default=""):
    try:
        value = st.secrets.get(name, default)
    except Exception:
        value = default
    return str(value or "").strip()


def github_config():
    cfg = {
        "token": get_secret("GITHUB_TOKEN"),
        "repo": get_secret("GITHUB_REPO"),
        "branch": get_secret("GITHUB_BRANCH", "main"),
        "state_path": get_secret("GITHUB_STATE_PATH", GITHUB_STATE_DEFAULT_PATH),
    }
    cfg["configured"] = bool(cfg["token"] and "/" in cfg["repo"] and cfg["branch"] and cfg["state_path"])
    return cfg


def github_url(cfg, include_ref=False):
    path = urllib.parse.quote(cfg["state_path"], safe="/")
    url = f"https://api.github.com/repos/{cfg['repo']}/contents/{path}"
    if include_ref:
        url += "?ref=" + urllib.parse.quote(cfg["branch"], safe="")
    return url


def github_request(cfg, method, url, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {cfg['token']}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "retirement-dashboard-streamlit",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub returned HTTP {exc.code}: {detail}") from exc


def github_metadata(cfg):
    try:
        return github_request(cfg, "GET", github_url(cfg, include_ref=True))
    except RuntimeError as exc:
        if "HTTP 404" in str(exc):
            return None
        raise


def save_to_github(payload):
    cfg = github_config()
    if not cfg["configured"]:
        return False, "GitHub persistence is not configured in Streamlit Secrets."
    try:
        meta = github_metadata(cfg)
        content = base64.b64encode(json.dumps(payload, indent=2).encode("utf-8")).decode("utf-8")
        body = {
            "message": f"Save retirement dashboard state {payload['last_saved']}",
            "content": content,
            "branch": cfg["branch"],
        }
        if meta and meta.get("sha"):
            body["sha"] = meta["sha"]
        github_request(cfg, "PUT", github_url(cfg), body)
        return True, "GitHub cloud save completed."
    except Exception as exc:
        return False, f"GitHub cloud save failed: {exc}"


def load_from_github():
    cfg = github_config()
    if not cfg["configured"]:
        return None, "GitHub persistence is not configured in Streamlit Secrets."
    try:
        meta = github_metadata(cfg)
        if not meta or not meta.get("content"):
            return None, "No GitHub state file was found."
        decoded = base64.b64decode(meta["content"].replace("\n", "")).decode("utf-8")
        state = normalize_state(json.loads(decoded))
        if state["total_contributions"] < state["protected_min_contributions"]:
            return None, "GitHub state was rejected because it is below its protected contribution floor."
        return state, "GitHub state loaded successfully."
    except Exception as exc:
        return None, f"GitHub load failed: {exc}"


def init_state():
    if st.session_state.get("_initialized"):
        return
    state, loaded_from = read_local_state()
    for key, value in state.items():
        st.session_state[key] = value
    st.session_state.loaded_from = loaded_from
    st.session_state.status_message = ""
    st.session_state._initialized = True


@st.cache_data(ttl=900, show_spinner=False)
def fetch_live_prices(tickers):
    if yf is None:
        return {}
    prices = {}
    for ticker in tickers:
        try:
            history = yf.Ticker(ticker).history(period="5d", auto_adjust=False)
            if not history.empty:
                prices[ticker] = float(history["Close"].dropna().iloc[-1])
        except Exception:
            pass
    return prices


def calculate(df, cash, use_live):
    out = normalize_df(df)
    live = fetch_live_prices(tuple(out["ticker"])) if use_live else {}
    out["price"] = [
        to_float(live.get(row.ticker, row.manual_price), row.manual_price)
        for row in out.itertuples()
    ]
    out["market_value"] = out["qty"] * out["price"]
    out["cost_basis"] = out["qty"] * out["avg_cost"]
    out["gain_loss"] = out["market_value"] - out["cost_basis"]
    out["annual_income"] = out["market_value"] * out["annual_yield"]
    invested = float(out["market_value"].sum())
    total = invested + to_float(cash)
    out["portfolio_weight"] = out["market_value"] / total * 100 if total else 0.0
    annual = float(out["annual_income"].sum())
    return {
        "df": out,
        "invested": invested,
        "cash": to_float(cash),
        "total": total,
        "cost_basis": float(out["cost_basis"].sum()),
        "gain_loss": float(out["gain_loss"].sum()),
        "monthly_actual": annual / 12.0,
        "monthly_realistic": annual / 12.0 * REALISTIC_INCOME_FACTOR,
        "monthly_conservative": annual / 12.0 * CONSERVATIVE_INCOME_FACTOR,
    }


def apply_state(state, message):
    state = normalize_state(state)
    for key, value in state.items():
        st.session_state[key] = value
    st.session_state.loaded_from = message


def inject_css():
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.2rem; padding-bottom: 3rem;}
        .dashboard-title {font-size: 2rem; font-weight: 750; margin-bottom: .1rem;}
        .dashboard-subtitle {color: #6b7280; margin-bottom: 1rem;}
        div[data-testid="stMetric"] {border: 1px solid rgba(128,128,128,.25); border-radius: 12px; padding: .75rem;}
        .status-box {border: 1px solid rgba(128,128,128,.28); border-radius: 10px; padding: .7rem .9rem; margin-bottom: .8rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def main():
    init_state()
    inject_css()

    st.markdown('<div class="dashboard-title">Retirement Paycheck Dashboard</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="dashboard-subtitle">Protected local startup â¢ GitHub only runs when you press a cloud button</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="status-box"><b>Loaded from:</b> {st.session_state.loaded_from}<br>'
        f'<b>Last saved:</b> {st.session_state.last_saved or "not yet"}<br>'
        f'<b>App version:</b> {APP_BASELINE_VERSION}</div>',
        unsafe_allow_html=True,
    )

    if st.session_state.status_message:
        st.info(st.session_state.status_message)

    top = st.columns(3)
    with top[0]:
        st.session_state.use_live_prices = st.checkbox(
            "Use Yahoo Finance live prices",
            value=bool(st.session_state.use_live_prices),
        )
    with top[1]:
        st.session_state.auto_sync_prices = st.checkbox(
            "Save good live prices as manual fallback",
            value=bool(st.session_state.auto_sync_prices),
        )
    with top[2]:
        if st.button("Sync Prices Now", use_container_width=True):
            fetch_live_prices.clear()
            st.session_state.last_price_sync = now_text()
            st.session_state.status_message = "Price cache cleared and refreshed."
            st.rerun()

    calc = calculate(
        st.session_state.portfolio_df,
        st.session_state.cash_fdrxx,
        st.session_state.use_live_prices,
    )

    if st.session_state.auto_sync_prices and st.session_state.use_live_prices:
        updated = normalize_df(st.session_state.portfolio_df)
        price_map = dict(zip(calc["df"]["ticker"], calc["df"]["price"]))
        updated["manual_price"] = [to_float(price_map.get(t, p), p) for t, p in zip(updated["ticker"], updated["manual_price"])]
        st.session_state.portfolio_df = updated

    metrics = st.columns(4)
    metrics[0].metric("Invested Holdings", money(calc["invested"]))
    metrics[1].metric("Cash Ready (FDRXX)", money(calc["cash"]))
    metrics[2].metric("Total Portfolio", money(calc["total"]))
    metrics[3].metric("Total Contributions", money(st.session_state.total_contributions))

    metrics2 = st.columns(4)
    metrics2[0].metric("Monthly Income", money(calc["monthly_actual"]))
    metrics2[1].metric("Realistic Monthly", money(calc["monthly_realistic"]))
    metrics2[2].metric("Conservative Monthly", money(calc["monthly_conservative"]))
    metrics2[3].metric("Goal Remaining", money(max(0, GOAL_MONTHLY - calc["monthly_realistic"])))

    st.divider()
    st.subheader("Cash and Contributions")
    c1, c2, c3 = st.columns(3)
    with c1:
        new_cash = st.number_input(
            "Available Cash (FDRXX)",
            min_value=0.0,
            value=float(st.session_state.cash_fdrxx),
            step=100.0,
            format="%.2f",
        )
    with c2:
        new_contributions = st.number_input(
            "Total Contributions / Deposits",
            min_value=float(st.session_state.protected_min_contributions),
            value=float(st.session_state.total_contributions),
            step=100.0,
            format="%.2f",
        )
    with c3:
        st.number_input(
            "Protected Contribution Floor",
            value=float(st.session_state.protected_min_contributions),
            disabled=True,
            format="%.2f",
        )

    if st.button("Apply Cash and Contribution Changes", use_container_width=True):
        st.session_state.cash_fdrxx = round(float(new_cash), 2)
        st.session_state.total_contributions = round(float(new_contributions), 2)
        st.session_state.protected_min_contributions = max(
            st.session_state.protected_min_contributions,
            st.session_state.total_contributions,
        )
        st.session_state.last_cash_message = f"FDRXX cash updated to {money(new_cash)}."
        st.session_state.status_message = "Cash and contribution changes applied. Press Save Current Dashboard to make them durable."
        st.rerun()

    st.divider()
    with st.expander("Holdings and Prices", expanded=False):
        edited = st.data_editor(
            normalize_df(st.session_state.portfolio_df),
            use_container_width=True,
            hide_index=True,
            num_rows="dynamic",
            column_config={
                "qty": st.column_config.NumberColumn("Shares", format="%.6f"),
                "avg_cost": st.column_config.NumberColumn("Average Cost", format="$%.4f"),
                "manual_price": st.column_config.NumberColumn("Manual Price", format="$%.4f"),
                "target_weight": st.column_config.NumberColumn("Target %", format="%.1f%%"),
                "annual_yield": st.column_config.NumberColumn("Annual Yield", format="%.4f"),
            },
            key="holdings_editor",
        )
        if st.button("Apply Holdings Changes", use_container_width=True):
            st.session_state.portfolio_df = normalize_df(edited)
            st.session_state.status_message = "Holdings changes applied. Press Save Current Dashboard to make them durable."
            st.rerun()

    st.divider()
    st.subheader("Current Holdings")
    display = calc["df"].copy()
    display["Market Value"] = display["market_value"].map(money)
    display["Cost Basis"] = display["cost_basis"].map(money)
    display["Gain / Loss"] = display["gain_loss"].map(money)
    display["Portfolio %"] = display["portfolio_weight"].map(lambda x: f"{x:.2f}%")
    display["Monthly Income"] = (display["annual_income"] / 12).map(money)
    st.dataframe(
        display[["ticker", "qty", "price", "Market Value", "Cost Basis", "Gain / Loss", "Portfolio %", "Monthly Income"]],
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    with st.expander("Smart Income Deployment", expanded=False):
        deploy_amount = st.number_input(
            "Amount of cash to deploy",
            min_value=0.0,
            max_value=float(st.session_state.cash_fdrxx),
            value=0.0,
            step=500.0,
            format="%.2f",
        )
        preview = []
        for tier, tickers in SMART_INCOME_TIERS.items():
            tier_amount = deploy_amount * SMART_INCOME_SPLITS[tier]
            each = tier_amount / len(tickers)
            for ticker in tickers:
                preview.append({"Tier": tier, "Ticker": ticker, "Amount": each})
        if deploy_amount > 0:
            preview_df = pd.DataFrame(preview)
            preview_df["Amount"] = preview_df["Amount"].map(money)
            st.dataframe(preview_df, use_container_width=True, hide_index=True)

        if st.button("Deploy Cash Using Smart Income Tiers", use_container_width=True, disabled=deploy_amount <= 0):
            df = normalize_df(st.session_state.portfolio_df)
            for item in preview:
                idx = df.index[df["ticker"] == item["Ticker"]]
                if len(idx) == 0:
                    continue
                row = idx[0]
                price = max(to_float(df.at[row, "manual_price"]), 0.000001)
                old_qty = to_float(df.at[row, "qty"])
                old_cost = old_qty * to_float(df.at[row, "avg_cost"])
                add_qty = item["Amount"] / price
                new_qty = old_qty + add_qty
                df.at[row, "qty"] = new_qty
                df.at[row, "avg_cost"] = (old_cost + item["Amount"]) / new_qty if new_qty else 0.0
            st.session_state.portfolio_df = normalize_df(df)
            st.session_state.cash_fdrxx = round(st.session_state.cash_fdrxx - deploy_amount, 2)
            st.session_state.last_deploy_message = f"Deployed {money(deploy_amount)} using the approved tier allocation."
            st.session_state.status_message = st.session_state.last_deploy_message + " Press Save Current Dashboard."
            st.rerun()

    st.divider()
    st.subheader("Save and Recovery")
    save_cols = st.columns(3)
    with save_cols[0]:
        if st.button("Save Current Dashboard", type="primary", use_container_width=True):
            try:
                payload = save_local_state()
                st.session_state.status_message = (
                    f"Local save verified at {payload['last_saved']}. "
                    "No GitHub call was made."
                )
            except Exception as exc:
                st.session_state.status_message = f"Local save failed: {exc}"
            st.rerun()

    with save_cols[1]:
        payload = serializable_state(
            {
                "portfolio_df": st.session_state.portfolio_df,
                "cash_fdrxx": st.session_state.cash_fdrxx,
                "total_contributions": st.session_state.total_contributions,
                "protected_min_contributions": st.session_state.protected_min_contributions,
                "use_live_prices": st.session_state.use_live_prices,
                "auto_sync_prices": st.session_state.auto_sync_prices,
                "last_price_sync": st.session_state.last_price_sync,
                "last_saved": st.session_state.last_saved,
                "last_saved_epoch": st.session_state.last_saved_epoch,
                "last_deploy_message": st.session_state.last_deploy_message,
                "last_cash_message": st.session_state.last_cash_message,
            },
            refresh_timestamp=False,
        )
        st.download_button(
            "Download Snapshot Backup",
            data=json.dumps(payload, indent=2),
            file_name=f"retirement_dashboard_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
        )

    with save_cols[2]:
        if st.button("Save Local + GitHub Cloud", use_container_width=True):
            try:
                payload = save_local_state()
                ok, message = save_to_github(payload)
                st.session_state.status_message = message
            except Exception as exc:
                st.session_state.status_message = f"Save failed: {exc}"
            st.rerun()

    cloud_cols = st.columns(2)
    with cloud_cols[0]:
        if st.button("Load GitHub Snapshot Manually", use_container_width=True):
            with st.spinner("Loading GitHub snapshot..."):
                state, message = load_from_github()
            if state is not None:
                apply_state(state, "Manually loaded GitHub snapshot.")
                save_local_state()
            st.session_state.status_message = message
            st.rerun()

    with cloud_cols[1]:
        if st.button("Reload Best Local Snapshot", use_container_width=True):
            state, message = read_local_state()
            apply_state(state, message)
            st.session_state.status_message = message
            st.rerun()

    uploaded = st.file_uploader("Restore a snapshot backup", type=["json"])
    if uploaded is not None:
        try:
            restored = normalize_state(json.load(uploaded))
            if restored["total_contributions"] < restored["protected_min_contributions"]:
                st.error("That backup is below its protected contribution floor and was not restored.")
            elif st.button("Restore Uploaded Snapshot", use_container_width=True):
                apply_state(restored, "Restored uploaded snapshot.")
                save_local_state()
                st.session_state.status_message = "Uploaded snapshot restored and saved locally."
                st.rerun()
        except Exception as exc:
            st.error(f"That backup could not be read: {exc}")

    with st.expander("Diagnostics", expanded=False):
        st.write(f"State directory: `{STATE_DIR}`")
        st.write(f"Primary state exists: `{STATE_FILE.exists()}`")
        st.write(f"Backup exists: `{BACKUP_FILE.exists()}`")
        st.write(f"Last-good exists: `{LAST_GOOD_FILE.exists()}`")
        st.write(f"GitHub configured: `{github_config()['configured']}`")
        st.write("Startup network calls: `disabled`")
        st.write("Cloud calls occur only after pressing a GitHub button.")

    with st.expander("Dangerous Reset", expanded=False):
        st.warning("This resets the dashboard to the protected July 10 baseline.")
        confirm = st.checkbox("I understand this will replace the current unsaved dashboard values.")
        if st.button("Reset to Protected Baseline", disabled=not confirm, use_container_width=True):
            apply_state(default_state(), "Reset to protected built-in baseline.")
            save_local_state()
            st.session_state.status_message = "Protected baseline restored and saved locally."
            st.rerun()


if __name__ == "__main__":
    main()
