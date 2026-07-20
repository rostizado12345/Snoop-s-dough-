import base64
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd
import streamlit as st

try:
    import yfinance as yf
except Exception:
    yf = None


st.set_page_config(page_title="Retirement Paycheck Dashboard", layout="wide")

APP_BASELINE_VERSION = "2026-07-12-configured-branch-safe-save-v22"
STATE_SCHEMA_VERSION = 2

GOAL_MONTHLY = 8000.0
REALISTIC_INCOME_FACTOR = 0.843
CONSERVATIVE_INCOME_FACTOR = 0.632

APP_DIR = Path(__file__).resolve().parent
STATE_DIR = APP_DIR / ".retirement_dashboard_state"
STATE_DIR.mkdir(parents=True, exist_ok=True)

# App-folder copies are kept for compatibility with the existing dashboard.
STATE_FILE = STATE_DIR / "retirement_dashboard_state.json"
BACKUP_FILE = STATE_DIR / "retirement_dashboard_state_backup.json"
LAST_GOOD_FILE = STATE_DIR / "retirement_dashboard_state_last_good.json"

LEGACY_STATE_FILE = APP_DIR / "retirement_dashboard_state.json"
LEGACY_BACKUP_FILE = APP_DIR / "retirement_dashboard_state_backup.json"
LEGACY_LAST_GOOD_FILE = APP_DIR / "retirement_dashboard_state_last_good.json"

# Durable cloud state uses the repository branch already configured in Streamlit Secrets.
GITHUB_STATE_DEFAULT_PATH = "retirement_dashboard_state.json"

# Home-folder copies survive app filename changes, Downloads-folder copies, and most local reruns.
HOME_STATE_DIR = Path.home() / ".retirement_dashboard_state"
HOME_STATE_DIR.mkdir(parents=True, exist_ok=True)
HOME_STATE_FILE = HOME_STATE_DIR / "retirement_dashboard_state.json"
HOME_BACKUP_FILE = HOME_STATE_DIR / "retirement_dashboard_state_backup.json"
HOME_LAST_GOOD_FILE = HOME_STATE_DIR / "retirement_dashboard_state_last_good.json"

# Last-resort portable snapshot. This is refreshed on Save when the app file is writable.
EMBEDDED_SAVED_STATE_JSON = r'''{
  "state_schema_version": 2,
  "app_baseline_version": "2026-07-11-full-ui-resilient-save-v18",
  "portfolio_df": [
    {
      "ticker": "AIPI",
      "qty": 706.966,
      "avg_cost": 34.04685,
      "manual_price": 35.865,
      "target_weight": 5.0,
      "annual_yield": 0.124,
      "payout_frequency": "monthly",
      "payout_months": "all",
      "notes": ""
    },
    {
      "ticker": "CHPY",
      "qty": 474.719,
      "avg_cost": 56.06939,
      "manual_price": 81.9401,
      "target_weight": 6.0,
      "annual_yield": 0.05,
      "payout_frequency": "monthly",
      "payout_months": "all",
      "notes": ""
    },
    {
      "ticker": "DIVO",
      "qty": 1404.379,
      "avg_cost": 44.979583,
      "manual_price": 45.705,
      "target_weight": 10.0,
      "annual_yield": 0.048,
      "payout_frequency": "monthly",
      "payout_months": "all",
      "notes": ""
    },
    {
      "ticker": "FEPI",
      "qty": 929.65,
      "avg_cost": 39.99048,
      "manual_price": 41.95,
      "target_weight": 7.0,
      "annual_yield": 0.12,
      "payout_frequency": "monthly",
      "payout_months": "all",
      "notes": ""
    },
    {
      "ticker": "GDXY",
      "qty": 3619.685,
      "avg_cost": 13.10574,
      "manual_price": 10.2213,
      "target_weight": 15.0,
      "annual_yield": 0.18,
      "payout_frequency": "monthly",
      "payout_months": "all",
      "notes": ""
    },
    {
      "ticker": "IAU",
      "qty": 174.866,
      "avg_cost": 84.63566,
      "manual_price": 76.49,
      "target_weight": 4.0,
      "annual_yield": 0.0,
      "payout_frequency": "none",
      "payout_months": "none",
      "notes": ""
    },
    {
      "ticker": "IWMI",
      "qty": 318.115,
      "avg_cost": 48.21481,
      "manual_price": 53.005,
      "target_weight": 4.0,
      "annual_yield": 0.12,
      "payout_frequency": "monthly",
      "payout_months": "all",
      "notes": ""
    },
    {
      "ticker": "IYRI",
      "qty": 385.111,
      "avg_cost": 46.93339,
      "manual_price": 49.67,
      "target_weight": 5.0,
      "annual_yield": 0.08,
      "payout_frequency": "monthly",
      "payout_months": "all",
      "notes": ""
    },
    {
      "ticker": "MLPI",
      "qty": 337.131,
      "avg_cost": 56.78753,
      "manual_price": 55.99,
      "target_weight": 4.0,
      "annual_yield": 0.08,
      "payout_frequency": "quarterly",
      "payout_months": "3,6,9,12",
      "notes": ""
    },
    {
      "ticker": "QQQI",
      "qty": 727.773,
      "avg_cost": 50.46252,
      "manual_price": 55.05,
      "target_weight": 10.0,
      "annual_yield": 0.14,
      "payout_frequency": "monthly",
      "payout_months": "all",
      "notes": ""
    },
    {
      "ticker": "SPYI",
      "qty": 1370.585,
      "avg_cost": 49.669172,
      "manual_price": 52.19,
      "target_weight": 12.0,
      "annual_yield": 0.12,
      "payout_frequency": "monthly",
      "payout_months": "all",
      "notes": ""
    },
    {
      "ticker": "SVOL",
      "qty": 1721.341,
      "avg_cost": 15.515646,
      "manual_price": 15.7,
      "target_weight": 6.0,
      "annual_yield": 0.16,
      "payout_frequency": "monthly",
      "payout_months": "all",
      "notes": ""
    },
    {
      "ticker": "TLTW",
      "qty": 1031.331,
      "avg_cost": 22.295132,
      "manual_price": 22.515,
      "target_weight": 7.0,
      "annual_yield": 0.12,
      "payout_frequency": "monthly",
      "payout_months": "all",
      "notes": ""
    }
  ],
  "cash_fdrxx": 299160.66,
  "total_contributions": 652536.60,
  "protected_min_contributions": 652536.60,
  "use_live_prices": true,
  "auto_sync_prices": true,
  "last_price_sync": "2026-06-26 07:46:00 PM",
  "last_saved": "2026-07-11 08:30:00 PM",
  "last_deploy_message": "Updated full-feature baseline with verified July holdings and cash.",
  "last_cash_message": "FDRXX cash baseline: $207,923.13. The $3,112.29 test amount is intentionally excluded."
}'''

DEFAULT_CASH_FDRXX = 207923.13
DEFAULT_TOTAL_CONTRIBUTIONS = 561299.07
CURRENT_PROTECTED_BASELINE_CONTRIBUTIONS = 561299.07

DEFAULT_COLUMNS = [
    "ticker", "qty", "avg_cost", "manual_price", "target_weight",
    "annual_yield", "payout_frequency", "payout_months", "notes",
]

DEFAULT_ROWS = [
    ['AIPI', 706.966, 34.04685, 35.865, 5.0, 0.124, 'monthly', 'all', ''],
    ['CHPY', 474.719, 56.06939, 81.9401, 6.0, 0.05, 'monthly', 'all', ''],
    ['DIVO', 1404.379, 44.979583, 45.705, 10.0, 0.048, 'monthly', 'all', ''],
    ['FEPI', 929.65, 39.99048, 41.95, 7.0, 0.12, 'monthly', 'all', ''],
    ['GDXY', 3619.685, 13.10574, 10.2213, 15.0, 0.18, 'monthly', 'all', ''],
    ['IAU', 174.866, 84.63566, 76.49, 4.0, 0.0, 'none', 'none', ''],
    ['IWMI', 318.115, 48.21481, 53.005, 4.0, 0.12, 'monthly', 'all', ''],
    ['IYRI', 385.111, 46.93339, 49.67, 5.0, 0.08, 'monthly', 'all', ''],
    ['MLPI', 337.131, 56.78753, 55.99, 4.0, 0.08, 'quarterly', '3,6,9,12', ''],
    ['QQQI', 727.773, 50.46252, 55.05, 10.0, 0.14, 'monthly', 'all', ''],
    ['SPYI', 1370.585, 49.669172, 52.19, 12.0, 0.12, 'monthly', 'all', ''],
    ['SVOL', 1721.341, 15.515646, 15.7, 6.0, 0.16, 'monthly', 'all', ''],
    ['TLTW', 1031.331, 22.295132, 22.515, 7.0, 0.12, 'monthly', 'all', ''],
]

SMART_INCOME_TIERS = {
    "tier_1": ["SPYI", "DIVO"],
    "tier_2": ["QQQI", "FEPI"],
    "tier_3": ["SVOL", "IYRI", "TLTW"],
    "avoid": ["GDXY", "IAU"],
}

SMART_INCOME_SPLITS = {"tier_1": 0.75, "tier_2": 0.20, "tier_3": 0.05}


def to_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str):
            cleaned = value.replace("$", "").replace(",", "").replace("%", "").strip()
            return default if cleaned == "" else float(cleaned)
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def round_money(value: float) -> float:
    return round(float(value), 2)


def round_shares(value: float) -> float:
    return round(float(value), 6)


def format_dollars(value: float) -> str:
    return f"${float(value):,.2f}"


def format_percent(value: float) -> str:
    return f"{float(value):,.1f}%"


def parse_saved_time(value: str) -> datetime:
    for fmt in ["%Y-%m-%d %I:%M:%S %p", "%Y-%m-%d %H:%M:%S"]:
        try:
            return datetime.strptime(str(value), fmt)
        except Exception:
            pass
    return datetime.min


def normalize_portfolio_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    for col in DEFAULT_COLUMNS:
        if col not in out.columns:
            out[col] = 0.0 if col in ["qty", "avg_cost", "manual_price", "target_weight", "annual_yield"] else ""

    for col in ["qty", "avg_cost", "manual_price", "target_weight", "annual_yield"]:
        out[col] = out[col].apply(to_float)

    out["ticker"] = out["ticker"].astype(str).str.upper().str.strip()
    out["payout_frequency"] = out["payout_frequency"].astype(str).str.strip()
    out["payout_months"] = out["payout_months"].astype(str).str.strip()
    out["notes"] = out["notes"].astype(str)

    out.loc[out["payout_frequency"] == "", "payout_frequency"] = "monthly"
    out.loc[out["payout_months"] == "", "payout_months"] = "all"

    out = out[out["ticker"] != ""].reset_index(drop=True)
    return out[DEFAULT_COLUMNS]


def get_default_portfolio_df() -> pd.DataFrame:
    return normalize_portfolio_df(pd.DataFrame(DEFAULT_ROWS, columns=DEFAULT_COLUMNS))


def baseline_state_payload() -> dict:
    now = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    return {
        "state_schema_version": STATE_SCHEMA_VERSION,
        "app_baseline_version": APP_BASELINE_VERSION,
        "portfolio_df": get_default_portfolio_df(),
        "cash_fdrxx": DEFAULT_CASH_FDRXX,
        "total_contributions": DEFAULT_TOTAL_CONTRIBUTIONS,
        "protected_min_contributions": DEFAULT_TOTAL_CONTRIBUTIONS,
        "use_live_prices": True,
        "auto_sync_prices": True,
        "last_price_sync": "",
        "last_saved": now,
        "last_deploy_message": "Loaded current protected full-snapshot production baseline.",
        "last_cash_message": f"FDRXX cash baseline: {format_dollars(DEFAULT_CASH_FDRXX)}.",
    }


def normalize_state_payload(raw: dict) -> dict:
    records = raw.get("portfolio_df", raw.get("portfolio", []))
    portfolio_df = normalize_portfolio_df(pd.DataFrame(records)) if records else get_default_portfolio_df()

    schema_version = int(to_float(raw.get("state_schema_version", 1), 1))
    total_contributions = round_money(
        to_float(raw.get("total_contributions", DEFAULT_TOTAL_CONTRIBUTIONS), DEFAULT_TOTAL_CONTRIBUTIONS)
    )

    if "protected_min_contributions" in raw:
        protected_min = round_money(to_float(raw.get("protected_min_contributions"), total_contributions))
    else:
        protected_min = total_contributions

    return {
        "state_schema_version": schema_version,
        "app_baseline_version": raw.get("app_baseline_version", ""),
        "portfolio_df": portfolio_df,
        "cash_fdrxx": round_money(to_float(raw.get("cash_fdrxx", raw.get("cash", DEFAULT_CASH_FDRXX)), DEFAULT_CASH_FDRXX)),
        "total_contributions": total_contributions,
        "protected_min_contributions": protected_min,
        "use_live_prices": bool(raw.get("use_live_prices", True)),
        "auto_sync_prices": bool(raw.get("auto_sync_prices", True)),
        "last_price_sync": str(raw.get("last_price_sync", "")),
        "last_saved": str(raw.get("last_saved", "")),
        "last_deploy_message": str(raw.get("last_deploy_message", "")),
        "last_cash_message": str(raw.get("last_cash_message", "")),
    }


def read_json_file(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_file = path.with_suffix(path.suffix + ".tmp")
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    os.replace(temp_file, path)


def read_embedded_state_payload() -> dict:
    """Read the portable snapshot embedded in this app file, if one exists."""
    try:
        raw = EMBEDDED_SAVED_STATE_JSON.strip()
        if not raw or raw == "{}":
            return {}
        return json.loads(raw)
    except Exception:
        return {}


def write_embedded_state_payload(payload: dict) -> None:
    """Best-effort: refresh the portable snapshot inside this .py file.

    Normal JSON files are still the primary save system. This embedded copy is
    only a last-resort recovery layer for cases where sidecar JSON files vanish
    or the app is opened from a different folder/name. If the app file is
    read-only, this safely does nothing.
    """
    try:
        app_file = Path(__file__).resolve()
        source = app_file.read_text(encoding="utf-8")
        replacement = "EMBEDDED_SAVED_STATE_JSON = r'''" + json.dumps(payload, indent=2) + "'''"
        updated, count = re.subn(
            r"EMBEDDED_SAVED_STATE_JSON\s*=\s*r'''[\s\S]*?'''",
            replacement,
            source,
            count=1,
        )
        if count == 1 and updated != source:
            app_file.write_text(updated, encoding="utf-8")
    except Exception:
        pass



SUPABASE_URL = "https://mbhasjccrzrufpvlfpux.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_66CgdMf_G079jJ6b4TZcHA_9ZqJH7Ky"
SUPABASE_TABLE = "retirement_dashboard_state"
SUPABASE_ROW_ID = "main"


def get_supabase_persistence_config() -> dict:
    """Return the fixed Supabase configuration for this dashboard."""
    return {
        "configured": bool(SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY and SUPABASE_TABLE),
        "url": SUPABASE_URL.rstrip("/"),
        "key": SUPABASE_PUBLISHABLE_KEY,
        "table": SUPABASE_TABLE,
        "row_id": SUPABASE_ROW_ID,
    }


def supabase_persistence_summary() -> str:
    cfg = get_supabase_persistence_config()
    if not cfg["configured"]:
        return "not configured"
    return f"configured: {cfg['table']} at {cfg['url']}"


def supabase_api_json(
    cfg: dict,
    method: str,
    query: str = "",
    body=None,
    prefer: str = "return=representation",
):
    """Call Supabase REST without exposing the key in the dashboard."""
    endpoint = f"{cfg['url']}/rest/v1/{urllib.parse.quote(cfg['table'], safe='')}"
    if query:
        endpoint += "?" + query

    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {
        "apikey": cfg["key"],
        "Authorization": f"Bearer {cfg['key']}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "retirement-dashboard-streamlit",
    }
    if prefer:
        headers["Prefer"] = prefer

    req = urllib.request.Request(endpoint, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else []
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8")
        except Exception:
            detail = str(exc)
        raise RuntimeError(f"Supabase REST {method} failed with HTTP {exc.code}: {detail}") from exc


def _extract_supabase_payload(row: dict) -> dict:
    """Support the state column names used by common versions of our setup SQL."""
    for field in ("state", "state_json", "payload", "data"):
        value = row.get(field)
        if isinstance(value, dict):
            return value
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass

    # Also support a table where the state fields themselves are columns.
    if "portfolio_df" in row and "cash_fdrxx" in row:
        return row
    return {}


def _read_supabase_rows(cfg: dict) -> list:
    rows = supabase_api_json(cfg, "GET", "select=*&limit=10", body=None, prefer="")
    return rows if isinstance(rows, list) else []


def read_supabase_state_payload() -> tuple[dict, str]:
    cfg = get_supabase_persistence_config()
    if not cfg["configured"]:
        return {}, "Supabase persistence not configured"

    try:
        rows = _read_supabase_rows(cfg)
        if not rows:
            return {}, f"No Supabase state row yet in {cfg['table']}"

        # Prefer the named main/dashboard row when an identifier column exists.
        selected = rows[0]
        for row in rows:
            if any(str(row.get(field, "")) in (cfg["row_id"], "dashboard", "default") for field in ("id", "key", "name")):
                selected = row
                break

        payload = _extract_supabase_payload(selected)
        if not payload:
            return {}, f"Supabase row exists in {cfg['table']} but no JSON state column was recognized"
        return payload, f"Loaded Supabase state from {cfg['table']}"
    except Exception as exc:
        return {}, f"Supabase load failed: {exc}"


def payload_matches_expected(actual: dict, expected: dict) -> tuple[bool, str]:
    """Verify every durable money field and the complete holdings table."""
    try:
        actual_norm = normalize_state_payload(actual)
        expected_norm = normalize_state_payload(expected)

        for field in ("cash_fdrxx", "total_contributions", "protected_min_contributions"):
            if round_money(actual_norm.get(field, -1)) != round_money(expected_norm.get(field, -1)):
                return False, f"{field} did not match"

        if portfolio_save_signature(actual_norm.get("portfolio_df", [])) != portfolio_save_signature(expected_norm.get("portfolio_df", [])):
            return False, "holdings did not match"

        if str(actual_norm.get("last_saved", "")) != str(expected_norm.get("last_saved", "")):
            return False, "save timestamp did not match"

        return True, "verified"
    except Exception as exc:
        return False, f"verification could not be completed: {exc}"


def _write_existing_supabase_row(cfg: dict, row: dict, clean_payload: dict):
    payload_field = next((f for f in ("state", "state_json", "payload", "data") if f in row), None)
    id_field = next((f for f in ("id", "key", "name") if f in row), None)

    if payload_field and id_field:
        identifier = row.get(id_field)
        query = urllib.parse.urlencode({id_field: f"eq.{identifier}"})
        return supabase_api_json(cfg, "PATCH", query, {payload_field: clean_payload})

    if payload_field:
        return supabase_api_json(cfg, "PATCH", "", {payload_field: clean_payload})

    # Flat-column table fallback.
    flat = {k: v for k, v in clean_payload.items() if k not in ("state_schema_version", "app_baseline_version")}
    return supabase_api_json(cfg, "PATCH", "", flat)


def _insert_supabase_row(cfg: dict, clean_payload: dict):
    attempts = [
        {"id": cfg["row_id"], "state": clean_payload},
        {"id": cfg["row_id"], "state_json": clean_payload},
        {"key": cfg["row_id"], "payload": clean_payload},
        {"name": cfg["row_id"], "data": clean_payload},
    ]
    errors = []
    for body in attempts:
        try:
            return supabase_api_json(cfg, "POST", "", body)
        except Exception as exc:
            errors.append(str(exc))
    raise RuntimeError("Could not match the Supabase table columns. " + " | ".join(errors))


def write_supabase_state_payload(payload: dict) -> tuple[bool, str]:
    cfg = get_supabase_persistence_config()
    if not cfg["configured"]:
        return False, "Supabase persistence not configured"

    try:
        clean_payload = make_payload_from_state(payload, force_timestamp=False)
        rows = _read_supabase_rows(cfg)
        if rows:
            selected = rows[0]
            for row in rows:
                if any(str(row.get(field, "")) in (cfg["row_id"], "dashboard", "default") for field in ("id", "key", "name")):
                    selected = row
                    break
            _write_existing_supabase_row(cfg, selected, clean_payload)
        else:
            _insert_supabase_row(cfg, clean_payload)

        last_reason = "Supabase read-back did not return the saved state"
        for delay in (0.0, 0.5, 1.0):
            if delay:
                time.sleep(delay)
            readback, read_status = read_supabase_state_payload()
            if readback:
                matched, reason = payload_matches_expected(readback, clean_payload)
                if matched:
                    return True, f"Supabase cloud save read back and verified in {cfg['table']}"
                last_reason = reason
            else:
                last_reason = read_status

        return False, f"Supabase accepted the save but durable read-back verification failed: {last_reason}"
    except Exception as exc:
        return False, f"Supabase cloud save failed: {exc}"

def candidate_state_files() -> List[Path]:
    return [
        STATE_FILE,
        LAST_GOOD_FILE,
        BACKUP_FILE,
        HOME_STATE_FILE,
        HOME_LAST_GOOD_FILE,
        HOME_BACKUP_FILE,
        LEGACY_STATE_FILE,
        LEGACY_LAST_GOOD_FILE,
        LEGACY_BACKUP_FILE,
    ]


def make_payload_from_state(state: dict, force_timestamp: bool = False) -> dict:
    source_df = state["portfolio_df"]
    if isinstance(source_df, pd.DataFrame):
        df = normalize_portfolio_df(source_df)
    else:
        df = normalize_portfolio_df(pd.DataFrame(source_df))
    saved_time = str(state.get("last_saved", ""))
    if force_timestamp or saved_time.strip() == "":
        saved_time = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")

    total_contributions = round_money(state["total_contributions"])
    protected_min = round_money(
        state.get(
            "protected_min_contributions",
            max(total_contributions, CURRENT_PROTECTED_BASELINE_CONTRIBUTIONS),
        )
    )

    return {
        "state_schema_version": STATE_SCHEMA_VERSION,
        "app_baseline_version": APP_BASELINE_VERSION,
        "portfolio_df": df.to_dict(orient="records"),
        "cash_fdrxx": round_money(state["cash_fdrxx"]),
        "total_contributions": total_contributions,
        "protected_min_contributions": protected_min,
        "use_live_prices": bool(state.get("use_live_prices", True)),
        "auto_sync_prices": bool(state.get("auto_sync_prices", True)),
        "last_price_sync": str(state.get("last_price_sync", "")),
        "last_saved": saved_time,
        "last_deploy_message": str(state.get("last_deploy_message", "")),
        "last_cash_message": str(state.get("last_cash_message", "")),
    }


def candidate_protected_value(item: dict) -> float:
    """Money-protection score used by the smart loader.

    The loader must not let a stale file with a newer timestamp beat a better
    protected snapshot. New money raises Total Contributions and the protected
    floor, so those values are ranked before saved time.
    """
    state = item["state"]
    total = round_money(state.get("total_contributions", 0.0))
    protected_min = round_money(state.get("protected_min_contributions", total))
    return round_money(max(total, protected_min))


def candidate_sort_key(item: dict) -> tuple:
    state = item["state"]
    return (
        1 if state.get("state_schema_version", 1) >= STATE_SCHEMA_VERSION else 0,
        candidate_protected_value(item),
        round_money(state.get("total_contributions", 0.0)),
        item["last_saved_dt"],
    )


def is_candidate_valid(item: dict) -> bool:
    state = item["state"]
    schema_version = int(state.get("state_schema_version", 1))
    total = round_money(state.get("total_contributions", 0.0))
    protected_min = round_money(state.get("protected_min_contributions", total))

    if schema_version < STATE_SCHEMA_VERSION:
        return False

    if total < protected_min:
        return False

    return total >= CURRENT_PROTECTED_BASELINE_CONTRIBUTIONS


def write_payload_everywhere(payload: dict) -> None:
    # Keep all runtime writes outside APP_DIR. Streamlit watches the deployed app
    # tree, and changing JSON files there can restart the script during its Save
    # callback just like changing app.py. HOME copies are safe for immediate local
    # read-back; the Supabase table is the durable cloud copy.
    write_json_atomic(HOME_STATE_FILE, payload)
    write_json_atomic(HOME_BACKUP_FILE, payload)
    write_json_atomic(HOME_LAST_GOOD_FILE, payload)


def load_state() -> dict:
    """
    Load the safest saved full snapshot and auto-promote recovered snapshots after validation.

    Important protection:
    - The highest protected contribution snapshot wins before saved-time order.
    - Good snapshots from older app versions are accepted and normalized forward.
    - When recovery picks a backup/embedded snapshot, it is automatically promoted everywhere.
    """
    errors = []
    candidates = []
    rejected = []

    def load_candidate(path: Path):
        try:
            raw = read_json_file(path)
            loaded = normalize_state_payload(raw)
            item = {
                "path": path,
                "state": loaded,
                "last_saved_dt": parse_saved_time(loaded.get("last_saved", "")),
                "is_primary": path == STATE_FILE,
            }

            if is_candidate_valid(item):
                return item

            rejected.append(
                f"{path} | rejected stale/unsafe | contributions {format_dollars(loaded.get('total_contributions', 0.0))} | "
                f"protected floor {format_dollars(loaded.get('protected_min_contributions', 0.0))} | "
                f"schema {loaded.get('state_schema_version', 1)} | saved {loaded.get('last_saved', '') or 'unknown'}"
            )
            return None

        except Exception as exc:
            errors.append(f"{path}: {exc}")
            return None

    for path in candidate_state_files():
        if not path.exists():
            continue

        item = load_candidate(path)
        if item is not None:
            candidates.append(item)

    embedded_raw = read_embedded_state_payload()
    if embedded_raw:
        try:
            embedded_loaded = normalize_state_payload(embedded_raw)
            embedded_item = {
                "path": Path("EMBEDDED_APP_FILE_SNAPSHOT"),
                "state": embedded_loaded,
                "last_saved_dt": parse_saved_time(embedded_loaded.get("last_saved", "")),
                "is_primary": False,
            }
            if is_candidate_valid(embedded_item):
                candidates.append(embedded_item)
            else:
                rejected.append(
                    f"EMBEDDED_APP_FILE_SNAPSHOT | rejected stale/unsafe | contributions {format_dollars(embedded_loaded.get('total_contributions', 0.0))} | "
                    f"protected floor {format_dollars(embedded_loaded.get('protected_min_contributions', 0.0))} | "
                    f"schema {embedded_loaded.get('state_schema_version', 1)} | saved {embedded_loaded.get('last_saved', '') or 'unknown'}"
                )
        except Exception as exc:
            errors.append(f"EMBEDDED_APP_FILE_SNAPSHOT: {exc}")

    github_raw, github_status = read_supabase_state_payload()
    if github_raw:
        try:
            github_loaded = normalize_state_payload(github_raw)
            github_item = {
                "path": Path("SUPABASE_STATE"),
                "state": github_loaded,
                "last_saved_dt": parse_saved_time(github_loaded.get("last_saved", "")),
                "is_primary": False,
            }
            if is_candidate_valid(github_item):
                candidates.append(github_item)
            else:
                rejected.append(
                    f"SUPABASE_STATE | rejected stale/unsafe | contributions {format_dollars(github_loaded.get('total_contributions', 0.0))} | "
                    f"protected floor {format_dollars(github_loaded.get('protected_min_contributions', 0.0))} | "
                    f"schema {github_loaded.get('state_schema_version', 1)} | saved {github_loaded.get('last_saved', '') or 'unknown'}"
                )
        except Exception as exc:
            github_status = f"Supabase state normalization failed: {exc}"

    if candidates:
        primary = next((item for item in candidates if item["is_primary"]), None)
        ranked_candidates = sorted(candidates, key=candidate_sort_key, reverse=True)
        best = ranked_candidates[0]

        # Pick the strongest protected snapshot first, then the newest one.
        # Do not let a stale primary file win just because it was touched later.
        if primary is not None and candidate_sort_key(primary) == candidate_sort_key(best):
            best = primary
            loaded_from = f"PRIMARY ACTIVE FULL SNAPSHOT SELECTED: {primary['path']}"
        else:
            loaded_from = f"BEST PROTECTED FULL SNAPSHOT SELECTED: {best['path']}"

        loaded = best["state"]

        if int(loaded.get("state_schema_version", 1)) < STATE_SCHEMA_VERSION:
            loaded["protected_min_contributions"] = max(
                round_money(loaded.get("total_contributions", 0.0)),
                CURRENT_PROTECTED_BASELINE_CONTRIBUTIONS,
            )

        original_app_version = str(loaded.get("app_baseline_version", ""))
        original_schema_version = int(loaded.get("state_schema_version", 1))

        normalized_payload = make_payload_from_state(loaded, force_timestamp=False)
        loaded["app_baseline_version"] = APP_BASELINE_VERSION
        loaded["state_schema_version"] = STATE_SCHEMA_VERSION
        loaded["protected_min_contributions"] = normalized_payload["protected_min_contributions"]

        version_mismatch_fixed = (
            original_app_version != APP_BASELINE_VERSION
            or original_schema_version != STATE_SCHEMA_VERSION
        )
        auto_repair_performed = False
        auto_repair_error = ""

        should_promote = best["path"] != STATE_FILE or primary is None or version_mismatch_fixed
        if should_promote:
            try:
                promoted_payload = make_payload_from_state(loaded, force_timestamp=True)
                write_payload_everywhere(promoted_payload)
                loaded = normalize_state_payload(promoted_payload)
                loaded_from = f"{loaded_from} | AUTO-REPAIRED AND PROMOTED TO ALL SAVE LOCATIONS"
                auto_repair_performed = True
            except Exception as exc:
                auto_repair_error = str(exc)
                errors.append(f"Automatic promotion failed: {exc}")

        loaded["_loaded_from"] = loaded_from
        loaded["_version_mismatch_fixed"] = version_mismatch_fixed
        loaded["_auto_repair_performed"] = auto_repair_performed
        loaded["_auto_repair_error"] = auto_repair_error
        loaded["_github_load_status"] = github_status
        loaded["_active_state_file"] = str(STATE_FILE)
        loaded["_load_errors"] = errors
        loaded["_candidate_summary"] = [
            f"{c['path']} | {'SELECTED' if c is best else 'checked only'} | schema {c['state'].get('state_schema_version', 1)} | "
            f"contributions {format_dollars(c['state'].get('total_contributions', 0.0))} | "
            f"protected floor {format_dollars(c['state'].get('protected_min_contributions', 0.0))} | "
            f"cash {format_dollars(c['state'].get('cash_fdrxx', 0.0))} | "
            f"saved {c['state'].get('last_saved', '') or 'unknown'}"
            for c in sorted(candidates, key=candidate_sort_key, reverse=True)
        ]
        loaded["_rejected_summary"] = rejected
        loaded["_startup_write_blocked"] = not auto_repair_performed
        loaded["_needs_force_save_to_spread_snapshot"] = False
        return loaded

    state = baseline_state_payload()
    payload = make_payload_from_state(state, force_timestamp=True)

    # First-run only: no saved state exists. A read-only or temporary filesystem
    # must not take down the entire app; Supabase can still become the durable source.
    try:
        write_payload_everywhere(payload)
    except Exception as exc:
        errors.append(f"Initial local baseline write failed: {exc}")

    state["_loaded_from"] = "CURRENT PROTECTED FULL-SNAPSHOT BASELINE - no valid saved file found"
    state["_version_mismatch_fixed"] = False
    state["_active_state_file"] = str(STATE_FILE)
    state["_github_load_status"] = github_status
    state["_load_errors"] = errors
    state["_candidate_summary"] = []
    state["_rejected_summary"] = rejected
    state["_startup_write_blocked"] = False
    state["_needs_force_save_to_spread_snapshot"] = False
    state["last_saved"] = payload["last_saved"]
    return state

def make_state_payload() -> dict:
    df = normalize_portfolio_df(st.session_state.portfolio_df.copy())
    total_contributions = round_money(st.session_state.total_contributions)
    protected_min = round_money(
        st.session_state.get(
            "protected_min_contributions",
            max(total_contributions, CURRENT_PROTECTED_BASELINE_CONTRIBUTIONS),
        )
    )

    return {
        "state_schema_version": STATE_SCHEMA_VERSION,
        "app_baseline_version": APP_BASELINE_VERSION,
        "portfolio_df": df.to_dict(orient="records"),
        "cash_fdrxx": round_money(st.session_state.cash_fdrxx),
        "total_contributions": total_contributions,
        "protected_min_contributions": protected_min,
        "use_live_prices": bool(st.session_state.use_live_prices),
        "auto_sync_prices": bool(st.session_state.auto_sync_prices),
        "last_price_sync": str(st.session_state.last_price_sync),
        "last_saved": datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"),
        "last_deploy_message": str(st.session_state.get("last_deploy_message", "")),
        "last_cash_message": str(st.session_state.get("last_cash_message", "")),
    }


def portfolio_save_signature(df_or_records) -> list:
    """
    Stable holdings fingerprint used only to verify that saved holdings actually
    match the intended portfolio. This does not change portfolio math.
    """
    clean = normalize_portfolio_df(pd.DataFrame(df_or_records)).copy()

    for col in ["qty", "avg_cost", "manual_price", "target_weight", "annual_yield"]:
        clean[col] = clean[col].apply(lambda x: round(to_float(x), 6))

    clean["ticker"] = clean["ticker"].astype(str).str.upper().str.strip()
    clean["payout_frequency"] = clean["payout_frequency"].astype(str).str.strip()
    clean["payout_months"] = clean["payout_months"].astype(str).str.strip()
    clean["notes"] = clean["notes"].astype(str)

    return clean.to_dict(orient="records")


def get_existing_protected_floor() -> float:
    floors = [CURRENT_PROTECTED_BASELINE_CONTRIBUTIONS]

    for path in candidate_state_files():
        if not path.exists():
            continue
        try:
            existing_norm = normalize_state_payload(read_json_file(path))
            floors.append(round_money(existing_norm.get("protected_min_contributions", existing_norm.get("total_contributions", 0.0))))
            floors.append(round_money(existing_norm.get("total_contributions", 0.0)))
        except Exception:
            pass

    floors.append(round_money(st.session_state.get("protected_min_contributions", CURRENT_PROTECTED_BASELINE_CONTRIBUTIONS)))
    return round_money(max(floors))


def save_state() -> bool:
    try:
        payload = make_state_payload()

        existing_floor = get_existing_protected_floor()
        current_total = round_money(payload["total_contributions"])
        authorized_reduction = bool(st.session_state.get("authorize_contribution_reduction_once", False))

        if current_total < existing_floor and not authorized_reduction:
            # Auto-repair stale contribution totals caused by older saved state files.
            # This keeps holdings/cash edits saveable without weakening the intentional
            # reduction protection in the Total Contributions form.
            current_total = existing_floor
            st.session_state.total_contributions = current_total
            payload["total_contributions"] = current_total

        if authorized_reduction:
            payload["protected_min_contributions"] = current_total
            st.session_state.authorize_contribution_reduction_once = False
        else:
            payload["protected_min_contributions"] = round_money(max(existing_floor, current_total))

        write_payload_everywhere(payload)

        intended_holdings = portfolio_save_signature(payload["portfolio_df"])

        for verify_path in (HOME_STATE_FILE, HOME_BACKUP_FILE, HOME_LAST_GOOD_FILE):
            verify = normalize_state_payload(read_json_file(verify_path))
            if round_money(verify.get("cash_fdrxx", -1)) != round_money(payload["cash_fdrxx"]):
                raise RuntimeError(f"Save verification failed for {verify_path}: cash did not match after write.")
            if round_money(verify.get("total_contributions", -1)) != round_money(payload["total_contributions"]):
                raise RuntimeError(f"Save verification failed for {verify_path}: contributions did not match after write.")
            if round_money(verify.get("protected_min_contributions", -1)) != round_money(payload["protected_min_contributions"]):
                raise RuntimeError(f"Save verification failed for {verify_path}: protected floor did not match after write.")

            saved_holdings = portfolio_save_signature(verify.get("portfolio_df", []))
            if saved_holdings != intended_holdings:
                raise RuntimeError(f"Save verification failed for {verify_path}: holdings did not match after write.")

        github_ok, github_message = write_supabase_state_payload(payload)
        st.session_state.github_save_status = github_message

        # Streamlit Cloud's local filesystem is temporary. Never call the save
        # successful unless the durable Supabase copy was read back and matched.
        if not github_ok:
            raise RuntimeError(
                "The temporary local copies were written, but the permanent Supabase save was not verified. "
                + github_message
            )

        st.session_state.protected_min_contributions = payload["protected_min_contributions"]
        st.session_state.last_saved = payload["last_saved"]
        st.session_state.loaded_from = "CURRENT FULL SNAPSHOT - saved locally and read back from verified Supabase cloud state"
        st.session_state.last_save_error = ""
        return True

    except Exception as exc:
        st.session_state.last_save_error = str(exc)
        return False


def bump_editor_version() -> None:
    st.session_state.editor_version = int(st.session_state.get("editor_version", 0)) + 1


def sync_editor_from_portfolio() -> None:
    st.session_state.editor_df = normalize_portfolio_df(st.session_state.portfolio_df.copy())
    bump_editor_version()


def apply_state_dict(state: dict, message: str = "") -> None:
    st.session_state.portfolio_df = normalize_portfolio_df(state["portfolio_df"])
    st.session_state.editor_df = normalize_portfolio_df(state["portfolio_df"].copy())
    st.session_state.cash_fdrxx = round_money(state["cash_fdrxx"])
    st.session_state.total_contributions = round_money(state["total_contributions"])
    st.session_state.protected_min_contributions = round_money(
        state.get("protected_min_contributions", max(st.session_state.total_contributions, CURRENT_PROTECTED_BASELINE_CONTRIBUTIONS))
    )
    st.session_state.use_live_prices = bool(state.get("use_live_prices", True))
    st.session_state.auto_sync_prices = bool(state.get("auto_sync_prices", True))
    st.session_state.last_price_sync = state.get("last_price_sync", "")
    st.session_state.last_saved = state.get("last_saved", "")
    st.session_state.last_deploy_message = message or state.get("last_deploy_message", "")
    st.session_state.last_cash_message = state.get("last_cash_message", "")
    sync_editor_from_portfolio()


def build_session_start_payload_from_loaded_state() -> dict:
    return {
        "state_schema_version": STATE_SCHEMA_VERSION,
        "app_baseline_version": APP_BASELINE_VERSION,
        "portfolio_df": normalize_portfolio_df(st.session_state.portfolio_df).to_dict(orient="records"),
        "cash_fdrxx": round_money(st.session_state.cash_fdrxx),
        "total_contributions": round_money(st.session_state.total_contributions),
        "protected_min_contributions": round_money(st.session_state.protected_min_contributions),
        "use_live_prices": bool(st.session_state.use_live_prices),
        "auto_sync_prices": bool(st.session_state.auto_sync_prices),
        "last_price_sync": str(st.session_state.last_price_sync),
        "last_saved": str(st.session_state.last_saved),
        "last_deploy_message": str(st.session_state.last_deploy_message),
        "last_cash_message": str(st.session_state.last_cash_message),
    }


def init_state() -> None:
    if st.session_state.get("app_initialized", False):
        return

    loaded = load_state()

    st.session_state.portfolio_df = normalize_portfolio_df(loaded["portfolio_df"])
    st.session_state.editor_df = normalize_portfolio_df(loaded["portfolio_df"].copy())
    st.session_state.cash_fdrxx = round_money(loaded["cash_fdrxx"])
    st.session_state.total_contributions = round_money(loaded["total_contributions"])
    st.session_state.protected_min_contributions = round_money(
        loaded.get("protected_min_contributions", max(st.session_state.total_contributions, CURRENT_PROTECTED_BASELINE_CONTRIBUTIONS))
    )
    st.session_state.use_live_prices = bool(loaded.get("use_live_prices", True))
    st.session_state.auto_sync_prices = bool(loaded.get("auto_sync_prices", True))
    st.session_state.last_price_sync = loaded.get("last_price_sync", "")
    st.session_state.last_saved = loaded.get("last_saved", "")
    st.session_state.last_deploy_message = loaded.get("last_deploy_message", "")
    st.session_state.last_cash_message = loaded.get("last_cash_message", "")
    st.session_state.last_save_error = ""
    st.session_state.github_load_status = loaded.get("_github_load_status", "")
    st.session_state.github_save_status = ""
    st.session_state.authorize_contribution_reduction_once = False
    st.session_state.editor_version = 0
    st.session_state.app_initialized = True

    st.session_state.loaded_from = loaded.get("_loaded_from", "UNKNOWN")
    st.session_state.version_mismatch_fixed = bool(loaded.get("_version_mismatch_fixed", False))
    st.session_state.startup_write_blocked = bool(loaded.get("_startup_write_blocked", False))
    st.session_state.needs_force_save_to_spread_snapshot = bool(loaded.get("_needs_force_save_to_spread_snapshot", False))
    st.session_state.auto_repair_performed = bool(loaded.get("_auto_repair_performed", False))
    st.session_state.auto_repair_error = str(loaded.get("_auto_repair_error", ""))
    st.session_state.active_state_file = str(STATE_FILE)
    st.session_state.load_errors = loaded.get("_load_errors", [])
    st.session_state.candidate_summary = loaded.get("_candidate_summary", [])
    st.session_state.rejected_summary = loaded.get("_rejected_summary", [])
    st.session_state.session_start_payload = build_session_start_payload_from_loaded_state()


def is_valid_price(live_price: float, fallback_price: float) -> bool:
    try:
        if live_price is None or pd.isna(live_price) or float(live_price) <= 0:
            return False
        if fallback_price is not None and float(fallback_price) > 0:
            pct_diff = abs(float(live_price) - float(fallback_price)) / float(fallback_price)
            if pct_diff > 0.25:
                return False
        return True
    except Exception:
        return False


@st.cache_data(ttl=900, show_spinner=False)
def get_live_prices_cached(tickers_key: str) -> Dict[str, float]:
    if yf is None:
        return {}

    tickers = [t.strip().upper() for t in tickers_key.split(",") if t.strip()]
    if not tickers:
        return {}

    try:
        unique_tickers = sorted(set(tickers))
        data = yf.download(
            " ".join(unique_tickers),
            period="5d",
            interval="1d",
            auto_adjust=False,
            progress=False,
            group_by="ticker",
            threads=True,
        )

        prices: Dict[str, float] = {}
        if data is None or len(data) == 0:
            return prices

        if len(unique_tickers) == 1:
            ticker = unique_tickers[0]
            if "Close" in data:
                close = data["Close"].dropna()
                if len(close) > 0:
                    prices[ticker] = float(close.iloc[-1])
            return prices

        for ticker in unique_tickers:
            try:
                close = data[ticker]["Close"].dropna()
                if len(close) > 0:
                    prices[ticker] = float(close.iloc[-1])
            except Exception:
                continue

        return prices
    except Exception:
        return {}


def get_live_prices(tickers: List[str]) -> Dict[str, float]:
    cleaned = sorted(set([str(t).upper().strip() for t in tickers if str(t).strip()]))
    return get_live_prices_cached(",".join(cleaned))


def calculate_portfolio(df: pd.DataFrame, cash_fdrxx: float, use_live_prices: bool) -> dict:
    working = normalize_portfolio_df(df)
    tickers = working["ticker"].tolist()
    live_prices = get_live_prices(tickers) if use_live_prices else {}

    working["live_price"] = working["ticker"].map(live_prices).fillna(float("nan"))

    price_used = []
    price_source = []
    for _, row in working.iterrows():
        live = row["live_price"]
        manual = row["manual_price"]
        if is_valid_price(live, manual):
            price_used.append(float(live))
            price_source.append("LIVE")
        else:
            price_used.append(float(manual))
            price_source.append("MANUAL")

    working["price_used"] = price_used
    working["price_source"] = price_source
    working["cost_basis"] = working["qty"] * working["avg_cost"]
    working["market_value"] = working["qty"] * working["price_used"]
    working["gain_loss"] = working["market_value"] - working["cost_basis"]
    working["gain_loss_pct"] = working.apply(
        lambda r: (r["gain_loss"] / r["cost_basis"]) if r["cost_basis"] > 0 else 0.0,
        axis=1,
    )

    working["annual_income_est"] = working["market_value"] * working["annual_yield"]
    working["monthly_income_est"] = working["annual_income_est"] / 12.0

    holdings_market_value = float(working["market_value"].sum())
    holdings_basis = float(working["cost_basis"].sum())
    cash_fdrxx = round_money(cash_fdrxx)
    total_value = holdings_market_value + cash_fdrxx
    total_contributions = round_money(st.session_state.total_contributions)

    total_monthly_actual = float(working["monthly_income_est"].sum())
    total_monthly_realistic = total_monthly_actual * REALISTIC_INCOME_FACTOR
    total_monthly_conservative = total_monthly_actual * CONSERVATIVE_INCOME_FACTOR

    working["current_weight"] = working["market_value"] / holdings_market_value if holdings_market_value > 0 else 0.0
    working["target_weight_decimal"] = working["target_weight"] / 100.0
    working["target_value"] = working["target_weight_decimal"] * holdings_market_value
    working["drift_dollars"] = working["market_value"] - working["target_value"]
    working["drift_pct_points"] = (working["current_weight"] - working["target_weight_decimal"]) * 100.0

    return {
        "df": working,
        "holdings_market_value": holdings_market_value,
        "holdings_cost_basis": holdings_basis,
        "available_cash": cash_fdrxx,
        "total_portfolio_value": total_value,
        "total_contributions": total_contributions,
        "net_vs_contributions": total_value - total_contributions,
        "holdings_gain_loss": holdings_market_value - holdings_basis,
        "monthly_actual": total_monthly_actual,
        "monthly_realistic": total_monthly_realistic,
        "monthly_conservative": total_monthly_conservative,
        "goal_progress": total_monthly_realistic / GOAL_MONTHLY if GOAL_MONTHLY else 0.0,
    }


def refresh_saved_manual_prices(calc_df: pd.DataFrame, persist: bool = False) -> bool:
    """Refresh manual fallback prices from good live prices.

    Safety rule: normal page loading must not silently save the whole dashboard.
    A passive live-price refresh can touch prices, but it should only become
    permanent when the user presses Sync Prices Now or another explicit Save.
    """
    if not bool(st.session_state.auto_sync_prices):
        return False

    df = normalize_portfolio_df(st.session_state.portfolio_df.copy())
    changed = False

    for _, row in calc_df.iterrows():
        ticker = str(row["ticker"]).upper().strip()
        if str(row.get("price_source", "")) != "LIVE":
            continue

        price = to_float(row.get("price_used", 0.0))
        if price <= 0:
            continue

        mask = df["ticker"] == ticker
        if mask.any():
            old = to_float(df.loc[mask, "manual_price"].iloc[0])
            if abs(old - price) > 0.0001:
                df.loc[mask, "manual_price"] = round(price, 4)
                changed = True

    if changed:
        st.session_state.portfolio_df = normalize_portfolio_df(df)
        st.session_state.editor_df = normalize_portfolio_df(df.copy())
        st.session_state.last_price_sync = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        if persist:
            save_state()

    return changed


def add_new_money(amount: float) -> None:
    amount = round_money(amount)
    if amount <= 0:
        return

    st.session_state.cash_fdrxx = round_money(st.session_state.cash_fdrxx + amount)
    st.session_state.total_contributions = round_money(st.session_state.total_contributions + amount)
    st.session_state.protected_min_contributions = round_money(
        max(st.session_state.protected_min_contributions, st.session_state.total_contributions)
    )
    st.session_state.last_cash_message = f"Added new money: {format_dollars(amount)} to FDRXX."
    save_state()


def set_exact_cash(new_cash: float) -> None:
    old_cash = round_money(st.session_state.cash_fdrxx)
    new_cash = round_money(new_cash)
    difference = round_money(new_cash - old_cash)

    st.session_state.cash_fdrxx = new_cash
    st.session_state.last_cash_message = (
        f"FDRXX cash set exactly to {format_dollars(new_cash)}. "
        f"Adjustment: {format_dollars(difference)}."
    )
    save_state()


def deploy_cash_to_position(ticker: str, dollars: float, calc_df: pd.DataFrame) -> None:
    ticker = str(ticker).upper().strip()
    dollars = round_money(dollars)

    if ticker == "" or dollars <= 0:
        st.error("Enter a valid ticker and dollar amount.")
        return

    available_cash = round_money(st.session_state.cash_fdrxx)
    if dollars > available_cash:
        st.error(f"Not enough FDRXX cash. Available: {format_dollars(available_cash)}")
        return

    df = normalize_portfolio_df(st.session_state.portfolio_df.copy())

    price_lookup = {
        str(row["ticker"]).upper().strip(): to_float(row.get("price_used", 0.0))
        for _, row in calc_df.iterrows()
    }

    price_used = round(to_float(price_lookup.get(ticker, 0.0)), 6)

    if price_used <= 0:
        st.error(f"Could not determine a valid price for {ticker}.")
        return

    shares_added = round_shares(dollars / price_used)
    match_idx = df.index[df["ticker"] == ticker].tolist()

    if match_idx:
        idx = match_idx[0]
        old_qty = to_float(df.at[idx, "qty"])
        old_avg_cost = to_float(df.at[idx, "avg_cost"])
        old_cost_basis = old_qty * old_avg_cost

        new_qty = round_shares(old_qty + shares_added)
        new_cost_basis = old_cost_basis + dollars
        new_avg_cost = round(new_cost_basis / new_qty, 6) if new_qty > 0 else 0.0

        df.at[idx, "qty"] = new_qty
        df.at[idx, "avg_cost"] = new_avg_cost
        df.at[idx, "manual_price"] = round(price_used, 4)
    else:
        new_row = {
            "ticker": ticker,
            "qty": shares_added,
            "avg_cost": round(price_used, 6),
            "manual_price": round(price_used, 4),
            "target_weight": 0.0,
            "annual_yield": 0.0,
            "payout_frequency": "monthly",
            "payout_months": "all",
            "notes": "Added from cash deployment",
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    st.session_state.portfolio_df = normalize_portfolio_df(df)
    st.session_state.cash_fdrxx = round_money(available_cash - dollars)
    st.session_state.last_deploy_message = (
        f"Deployment saved: {format_dollars(dollars)} into {ticker} "
        f"at {format_dollars(price_used)}; added {shares_added:,.6f} shares."
    )

    sync_editor_from_portfolio()

    ok = save_state()
    if not ok:
        st.error(f"Deployment changed the screen but DID NOT SAVE. Error: {st.session_state.last_save_error}")


def build_smarter_income_suggestions(df: pd.DataFrame, available_cash: float) -> pd.DataFrame:
    if available_cash <= 0 or df.empty:
        return pd.DataFrame()

    working = df.copy()
    working["ticker"] = working["ticker"].astype(str).str.upper().str.strip()

    eligible_rows = []
    for _, row in working.iterrows():
        ticker = row["ticker"]
        if ticker in SMART_INCOME_TIERS["avoid"]:
            continue
        if to_float(row.get("price_used", 0.0)) <= 0:
            continue
        eligible_rows.append(row)

    if not eligible_rows:
        return pd.DataFrame()

    suggestions = []
    for tier_name, tier_tickers in SMART_INCOME_TIERS.items():
        if tier_name == "avoid":
            continue

        tier_budget = available_cash * SMART_INCOME_SPLITS.get(tier_name, 0.0)
        tier_rows = [r for r in eligible_rows if r["ticker"] in tier_tickers]
        if not tier_rows or tier_budget <= 0:
            continue

        each_budget = tier_budget / len(tier_rows)
        for row in tier_rows:
            ticker = row["ticker"]
            price = to_float(row["price_used"])
            annual_yield = to_float(row["annual_yield"])
            shares = each_budget / price if price > 0 else 0.0
            monthly_income = (each_budget * annual_yield) / 12.0
            suggestions.append(
                {
                    "Ticker": ticker,
                    "Tier": tier_name.replace("_", " ").title(),
                    "Suggested Buy $": each_budget,
                    "Approx Shares": shares,
                    "Price Used": price,
                    "Added Monthly Income": monthly_income,
                }
            )

    return pd.DataFrame(suggestions)


def inject_dashboard_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

        html, body, [class*="css"], .stApp {
            font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }

        .main .block-container {
            padding-top: 1.05rem;
            padding-bottom: 2rem;
            max-width: 1420px;
        }

        .dashboard-title {
            font-size: 2.25rem;
            font-weight: 900;
            margin-bottom: 0.1rem;
            color: #0f172a;
            letter-spacing: -0.04em;
        }

        .dashboard-subtitle {
            color: #64748b;
            font-size: 1.02rem;
            margin-bottom: 1.0rem;
            font-weight: 500;
        }

        .hero-card {
            border-radius: 28px;
            padding: 30px 32px;
            margin: 10px 0 16px 0;
            background:
                radial-gradient(circle at 92% 12%, rgba(34, 197, 94, 0.34) 0%, rgba(34, 197, 94, 0.04) 30%, transparent 48%),
                linear-gradient(135deg, #020617 0%, #0f172a 46%, #1e3a8a 100%);
            color: #ffffff !important;
            box-shadow: 0 24px 58px rgba(15, 23, 42, 0.30);
            border: 1px solid rgba(255,255,255,0.14);
            overflow: hidden;
        }

        .hero-card * {
            color: #ffffff !important;
        }

        .hero-label {
            font-size: 0.78rem;
            letter-spacing: 0.13em;
            text-transform: uppercase;
            opacity: 0.84;
            margin-bottom: 4px;
            font-weight: 900;
        }

        .hero-number {
            font-size: 3.05rem;
            font-weight: 950;
            margin: 2px 0 2px 0;
            letter-spacing: -0.06em;
        }

        .hero-small {
            opacity: 0.94;
            font-size: 1.0rem;
            margin-top: 5px;
            font-weight: 600;
        }

        .paycheck-bar-wrap {
            margin-top: 19px;
            background: rgba(255,255,255,0.18);
            border-radius: 999px;
            height: 24px;
            overflow: hidden;
            box-shadow: inset 0 1px 2px rgba(0,0,0,0.22);
        }

        .paycheck-bar-fill {
            height: 24px;
            background: linear-gradient(90deg, #22c55e, #bef264);
            border-radius: 999px;
            box-shadow: 0 0 22px rgba(34,197,94,0.45);
        }

        .funding-card {
            position: relative;
            border-radius: 30px;
            padding: 27px 31px 26px 31px;
            margin: 0 0 22px 0;
            background:
                radial-gradient(circle at 88% 18%, rgba(96,165,250,0.36) 0%, rgba(96,165,250,0.08) 34%, transparent 54%),
                linear-gradient(135deg, #020617 0%, #0f172a 46%, #1e3a8a 100%);
            color: #ffffff !important;
            border: 1px solid rgba(255,255,255,0.14);
            box-shadow: 0 26px 62px rgba(15, 23, 42, 0.30);
            overflow: hidden;
        }

        .funding-card:after {
            content: "";
            position: absolute;
            width: 220px;
            height: 220px;
            right: -88px;
            top: -98px;
            border-radius: 999px;
            background: rgba(255,255,255,0.08);
            pointer-events: none;
        }

        .funding-card * {
            color: #ffffff !important;
            position: relative;
            z-index: 2;
        }

        .funding-topline {
            display: flex;
            justify-content: space-between;
            gap: 16px;
            align-items: flex-start;
            flex-wrap: wrap;
        }

        .funding-label {
            color: #ffffff !important;
            font-size: 0.78rem;
            font-weight: 950;
            letter-spacing: 0.13em;
            text-transform: uppercase;
            opacity: 0.84;
        }

        .funding-number {
            color: #ffffff !important;
            font-size: 2.35rem;
            font-weight: 950;
            line-height: 1.04;
            letter-spacing: -0.06em;
            margin-top: 7px;
        }

        .funding-pill {
            background: rgba(255,255,255,0.14);
            color: #ffffff !important;
            border: 1px solid rgba(255,255,255,0.18);
            border-radius: 999px;
            padding: 8px 13px;
            font-size: 0.88rem;
            font-weight: 950;
            box-shadow: 0 10px 22px rgba(0,0,0,0.16);
            backdrop-filter: blur(10px);
        }

        .funding-note {
            color: #ffffff !important;
            font-size: 0.95rem;
            margin-top: 12px;
            line-height: 1.38;
            font-weight: 650;
            opacity: 0.88;
        }

        .funding-bar-wrap {
            margin-top: 16px;
            background: rgba(255,255,255,0.18);
            border-radius: 999px;
            height: 18px;
            overflow: hidden;
            box-shadow: inset 0 1px 2px rgba(0,0,0,0.22);
        }

        .funding-bar-fill {
            height: 18px;
            background: linear-gradient(90deg, #22c55e, #bef264);
            border-radius: 999px;
            box-shadow: 0 0 22px rgba(34,197,94,0.45);
        }

        .main-value-card {
            position: relative;
            border-radius: 30px;
            padding: 31px 34px;
            margin: 10px 0 18px 0;
            background:
                radial-gradient(circle at 88% 18%, rgba(96,165,250,0.36) 0%, rgba(96,165,250,0.08) 34%, transparent 54%),
                linear-gradient(135deg, #020617 0%, #0f172a 46%, #1e3a8a 100%);
            color: #ffffff !important;
            box-shadow: 0 26px 62px rgba(15, 23, 42, 0.30);
            border: 1px solid rgba(255,255,255,0.14);
            display: flex;
            justify-content: space-between;
            align-items: center;
            overflow: hidden;
        }

        .main-value-card:after {
            content: "";
            position: absolute;
            width: 240px;
            height: 240px;
            right: -90px;
            top: -100px;
            border-radius: 999px;
            background: rgba(255,255,255,0.08);
            pointer-events: none;
        }

        .main-value-left {
            position: relative;
            z-index: 2;
        }

        .main-value-label {
            color: #ffffff !important;
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.13em;
            font-weight: 950;
            opacity: 0.84;
        }

        .main-value-number {
            color: #ffffff !important;
            font-size: 3.55rem;
            font-weight: 950;
            letter-spacing: -0.065em;
            line-height: 1.0;
            margin-top: 8px;
        }

        .main-value-note {
            color: #ffffff !important;
            font-size: 1rem;
            opacity: 0.88;
            margin-top: 9px;
            font-weight: 650;
        }

        .main-value-icon {
            position: relative;
            z-index: 2;
            width: 82px;
            height: 82px;
            min-width: 82px;
            border-radius: 28px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: rgba(255,255,255,0.14);
            border: 1px solid rgba(255,255,255,0.18);
            box-shadow: 0 14px 30px rgba(0,0,0,0.18);
            font-size: 3.25rem;
        }

        .premium-metric-card {
            position: relative;
            border-radius: 24px;
            padding: 22px 24px 21px 25px;
            min-height: 150px;
            margin-bottom: 18px;
            background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
            color: #0f172a !important;
            box-shadow: 0 14px 34px rgba(15, 23, 42, 0.12);
            border: 1px solid rgba(148,163,184,0.28);
            overflow: hidden;
        }

        .premium-metric-card * {
            color: inherit !important;
        }

        .premium-metric-card:after {
            content: "";
            position: absolute;
            width: 190px;
            height: 190px;
            right: -84px;
            top: -92px;
            border-radius: 999px;
            background: rgba(59,130,246,0.07);
            pointer-events: none;
        }

        .premium-accent {
            position: absolute;
            left: 0;
            top: 0;
            width: 7px;
            height: 100%;
        }

        .premium-accent.blue { background: linear-gradient(180deg, #60a5fa, #2563eb); }
        .premium-accent.green { background: linear-gradient(180deg, #4ade80, #16a34a); }
        .premium-accent.purple { background: linear-gradient(180deg, #c084fc, #7c3aed); }
        .premium-accent.amber { background: linear-gradient(180deg, #fbbf24, #d97706); }
        .premium-accent.gray { background: linear-gradient(180deg, #94a3b8, #475569); }

        .metric-blue {
            background: linear-gradient(180deg, #ffffff 0%, #eff6ff 100%);
        }

        .metric-green {
            background: linear-gradient(180deg, #ffffff 0%, #ecfdf5 100%);
        }

        .metric-purple {
            background: linear-gradient(180deg, #ffffff 0%, #faf5ff 100%);
        }

        .metric-amber {
            background: linear-gradient(180deg, #ffffff 0%, #fffbeb 100%);
        }

        .metric-gray {
            background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
        }

        .premium-card-top {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 18px;
            position: relative;
            z-index: 2;
        }

        .premium-label {
            color: #475569 !important;
            font-size: 0.76rem;
            font-weight: 950;
            text-transform: uppercase;
            letter-spacing: 0.12em;
        }

        .premium-value {
            color: #0f172a !important;
            font-size: 2.05rem;
            font-weight: 950;
            letter-spacing: -0.055em;
            line-height: 1.05;
            margin-top: 10px;
            white-space: nowrap;
        }

        .premium-percent {
            display: inline-flex;
            align-items: center;
            width: fit-content;
            margin-top: 11px;
            padding: 5px 10px;
            border-radius: 999px;
            background: rgba(15,23,42,0.06);
            border: 1px solid rgba(148,163,184,0.24);
            color: #334155 !important;
            font-size: 0.82rem;
            font-weight: 850;
            line-height: 1.1;
            letter-spacing: -0.01em;
        }

        .premium-note {
            color: #64748b !important;
            font-size: 0.92rem;
            font-weight: 650;
            margin-top: 13px;
            line-height: 1.35;
            position: relative;
            z-index: 2;
        }

        .premium-icon {
            width: 54px;
            height: 54px;
            min-width: 54px;
            border-radius: 19px;
            background: rgba(15,23,42,0.06);
            border: 1px solid rgba(148,163,184,0.26);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.95rem;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.85);
        }

        .section-title {
            font-size: 1.34rem;
            font-weight: 900;
            margin-bottom: 2px;
            color: #0f172a;
            letter-spacing: -0.035em;
        }

        .section-subtitle {
            color: #64748b;
            font-size: 0.95rem;
            margin-bottom: 13px;
            font-weight: 500;
        }

        .status-pill {
            display: inline-block;
            border-radius: 999px;
            padding: 6px 12px;
            font-size: 0.82rem;
            font-weight: 800;
            background: #ecfdf5;
            color: #047857 !important;
            border: 1px solid #bbf7d0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_card(icon: str, label: str, value: str, percent_text: str = "", note: str = "") -> None:
    label_lower = label.lower()

    if any(word in label_lower for word in ["cash", "fdrxx", "deploy"]):
        tone = "metric-green"
        accent = "green"
        default_icon = "&#128181;"
    elif any(word in label_lower for word in ["gain", "profit", "loss"]):
        tone = "metric-amber"
        accent = "amber"
        default_icon = "&#128200;"
    elif any(word in label_lower for word in ["basis", "cost"]):
        tone = "metric-purple"
        accent = "purple"
        default_icon = "&#127919;"
    elif any(word in label_lower for word in ["holdings"]):
        tone = "metric-blue"
        accent = "blue"
        default_icon = "&#128202;"
    elif any(word in label_lower for word in ["value", "contribution", "net"]):
        tone = "metric-blue"
        accent = "blue"
        default_icon = "&#127974;"
    else:
        tone = "metric-gray"
        accent = "gray"
        default_icon = "&#8226;"

    display_icon = icon or default_icon
    percent_html = f'<div class="premium-percent">{percent_text}</div>' if percent_text else ""

    st.markdown(
        f"""
        <div class="premium-metric-card {tone}">
            <div class="premium-accent {accent}"></div>
            <div class="premium-card-top">
                <div>
                    <div class="premium-label">{label}</div>
                    <div class="premium-value">{value}</div>
                    {percent_html}
                </div>
                <div class="premium-icon">{display_icon}</div>
            </div>
            <div class="premium-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_section_header(title: str, subtitle: str = "") -> None:
    st.markdown(
        f"""
        <div class="section-title">{title}</div>
        <div class="section-subtitle">{subtitle}</div>
        """,
        unsafe_allow_html=True,
    )


def render_state_health_box() -> None:
    loaded_from = st.session_state.get("loaded_from", "UNKNOWN")
    cash = st.session_state.get("cash_fdrxx", 0.0)
    contributions = st.session_state.get("total_contributions", 0.0)
    protected_floor = st.session_state.get("protected_min_contributions", 0.0)
    last_saved = st.session_state.get("last_saved", "") or "not saved yet"

    state_exists = STATE_FILE.exists()
    backup_exists = BACKUP_FILE.exists()
    last_good_exists = LAST_GOOD_FILE.exists()
    legacy_exists = LEGACY_STATE_FILE.exists()
    legacy_backup_exists = LEGACY_BACKUP_FILE.exists()

    good_loader = (
        "PRIMARY ACTIVE FULL SNAPSHOT" in loaded_from
        or "BEST VALID FULL SNAPSHOT" in loaded_from
        or "BEST PROTECTED FULL SNAPSHOT" in loaded_from
        or "SUPABASE_STATE" in loaded_from
        or "BACKUP RECOVERY FULL SNAPSHOT" in loaded_from
        or "CURRENT FULL SNAPSHOT" in loaded_from
        or "UPLOADED SNAPSHOT" in loaded_from
        or "CURRENT PROTECTED FULL-SNAPSHOT BASELINE" in loaded_from
    )

    message = (
        f"State loaded from: {loaded_from}\n\n"
        f"Cash: {format_dollars(cash)} | "
        f"Contributions: {format_dollars(contributions)} | "
        f"Protected floor: {format_dollars(protected_floor)} | "
        f"Last saved: {last_saved}"
    )

    if good_loader:
        st.success(message)
    else:
        st.error(message)

    if round_money(contributions) < round_money(protected_floor):
        st.error(
            f"Contributions are below the protected floor. "
            f"Loaded: {format_dollars(contributions)} | Protected floor: {format_dollars(protected_floor)}. "
            f"Do not save unless this was an intentional contribution reduction."
        )
    else:
        st.info(
            f"Full-snapshot protection passed: contributions {format_dollars(contributions)} "
            f"are at or above the protected floor {format_dollars(protected_floor)}."
        )

    st.caption(f"Active save file: {STATE_FILE}")
    st.caption(
        f"Hidden save: {state_exists} | Hidden backup: {backup_exists} | Hidden last-good: {last_good_exists} | "
        f"Root save: {legacy_exists} | Root backup: {legacy_backup_exists}"
    )
    st.caption(f"Supabase cloud persistence: {supabase_persistence_summary()}")
    if st.session_state.get("github_load_status"):
        st.caption(f"Supabase load status: {st.session_state.github_load_status}")
    if st.session_state.get("github_save_status"):
        st.caption(f"Supabase save status: {st.session_state.github_save_status}")

    if st.session_state.get("auto_repair_performed", False):
        st.success("Automatic recovery ran: the best protected snapshot was promoted to every save and backup location.")

    if st.session_state.get("auto_repair_error", ""):
        st.error(f"Automatic recovery could not write everywhere: {st.session_state.auto_repair_error}")

    if st.session_state.get("startup_write_blocked", False):
        st.info("Startup protection checked saved files without promoting anything because the active file already matched the best protected snapshot.")

    if st.session_state.get("needs_force_save_to_spread_snapshot", False):
        st.warning("A newer protected snapshot was loaded. Automatic recovery should normally promote it everywhere; use Force Save State Now only if this warning remains.")

    if st.session_state.get("version_mismatch_fixed", False):
        st.info("State was normalized to the current app version and automatic recovery will preserve it.")

    if st.session_state.get("candidate_summary"):
        with st.expander("Valid full snapshots checked by smart loader"):
            for item in st.session_state.candidate_summary:
                st.write(item)

    if st.session_state.get("rejected_summary"):
        with st.expander("Rejected stale or unsafe saved files"):
            for item in st.session_state.rejected_summary:
                st.write(item)

    if st.session_state.get("load_errors"):
        with st.expander("Load errors found"):
            for err in st.session_state.load_errors:
                st.write(err)


def render_paycheck_hero(calc: dict) -> None:
    realistic = calc["monthly_realistic"]
    conservative = calc["monthly_conservative"]
    actual = calc["monthly_actual"]
    progress_pct = max(0.0, min(calc["goal_progress"] * 100.0, 100.0))

    st.markdown(
        f"""
        <div class="hero-card">
            <div class="hero-label">Regular Production App</div>
            <div class="hero-number">{format_dollars(realistic)} / {format_dollars(GOAL_MONTHLY)}</div>
            <div class="hero-small">
                Realistic monthly income estimate &#8226; {format_percent(progress_pct)} of your goal
            </div>
            <div class="paycheck-bar-wrap">
                <div class="paycheck-bar-fill" style="width: {progress_pct:.1f}%;"></div>
            </div>
            <div class="hero-small" style="margin-top: 14px;">
                Conservative: {format_dollars(conservative)} &nbsp;&nbsp;|&nbsp;&nbsp;
                Actual estimate: {format_dollars(actual)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_funding_goal_card(calc: dict) -> None:
    holdings_value = float(calc.get("holdings_market_value", 0.0))
    realistic_income = float(calc.get("monthly_realistic", 0.0))

    if holdings_value > 0 and realistic_income > 0:
        realistic_income_rate = realistic_income / holdings_value
        estimated_needed = GOAL_MONTHLY / realistic_income_rate if realistic_income_rate > 0 else 0.0
        funded_pct = holdings_value / estimated_needed if estimated_needed > 0 else 0.0
    else:
        estimated_needed = 0.0
        funded_pct = 0.0

    progress_pct = max(0.0, min(funded_pct * 100.0, 100.0))

    if estimated_needed > 0:
        needed_text = format_dollars(estimated_needed)
        main_text = f"{format_dollars(holdings_value)} / {needed_text}"
    else:
        main_text = f"{format_dollars(holdings_value)} / calculating..."

    st.markdown(
        f"""
        <div class="funding-card">
            <div class="funding-topline">
                <div>
                    <div class="funding-label">Income Machine Funding Goal</div>
                    <div class="funding-number">{main_text}</div>
                </div>
                <div class="funding-pill">{format_percent(progress_pct)} funded</div>
            </div>
            <div class="funding-bar-wrap">
                <div class="funding-bar-fill" style="width: {progress_pct:.1f}%;"></div>
            </div>
            <div class="funding-note">
                Estimated invested holdings needed to generate {format_dollars(GOAL_MONTHLY)}/month at the current realistic income rate. Based on invested holdings only; deploying FDRXX cash increases progress.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metrics(calc: dict) -> None:
    render_paycheck_hero(calc)
    render_funding_goal_card(calc)

    render_section_header(
        "Account Overview",
        "Cash, total value, cost basis, and gains are separated clearly."
    )

    total_value = float(calc["total_portfolio_value"])
    holdings_value = float(calc["holdings_market_value"])
    cash_value = float(calc["available_cash"])
    holdings_basis = float(calc["holdings_cost_basis"])
    holdings_gain_loss = float(calc["holdings_gain_loss"])
    total_contributions = float(calc["total_contributions"])

    invested_pct = (holdings_value / total_value * 100.0) if total_value > 0 else 0.0
    cash_pct = (cash_value / total_value * 100.0) if total_value > 0 else 0.0
    basis_pct = (holdings_basis / total_value * 100.0) if total_value > 0 else 0.0
    gain_loss_pct = (holdings_gain_loss / holdings_basis * 100.0) if holdings_basis > 0 else 0.0

    row1_col1, row1_col2 = st.columns(2)
    with row1_col1:
        render_card(
            "&#127974;",
            "Total Account Value",
            format_dollars(total_value),
            "100.0% of account",
            f"Holdings + FDRXX cash | Contributions: {format_dollars(total_contributions)}",
        )
    with row1_col2:
        render_card(
            "&#128202;",
            "Holdings Value",
            format_dollars(holdings_value),
            f"{format_percent(invested_pct)} of account",
            "Currently invested holdings only",
        )

    row2_col1, row2_col2 = st.columns(2)
    with row2_col1:
        render_card(
            "&#128181;",
            "Cash Ready (FDRXX)",
            format_dollars(cash_value),
            f"{format_percent(cash_pct)} of account",
            "Available dry powder",
        )
    with row2_col2:
        render_card(
            "&#127919;",
            "Invested Cost Basis",
            format_dollars(holdings_basis),
            f"{format_percent(basis_pct)} of account",
            "Cost basis currently in holdings",
        )

    row3_col1, row3_col2 = st.columns(2)
    with row3_col1:
        render_card(
            "&#128200;",
            "Holdings Gain / Loss",
            format_dollars(holdings_gain_loss),
            f"{format_percent(gain_loss_pct)} vs invested basis",
            "Holdings gain/loss only",
        )
    with row3_col2:
        st.empty()

def render_top_controls(calc: dict) -> None:
    render_section_header(
        "Cash Command Center",
        "Use this area to match Fidelity cash, update total contributions, or add new money."
    )

    st.markdown("#### Set Exact FDRXX Cash")
    with st.form("exact_cash_form"):
        exact_cash = st.number_input(
            "Exact Fidelity FDRXX Cash",
            min_value=0.0,
            value=float(st.session_state.cash_fdrxx),
            step=100.0,
            format="%.2f",
        )
        set_cash_pressed = st.form_submit_button("Set Exact FDRXX Cash", use_container_width=True)

    if set_cash_pressed:
        set_exact_cash(float(exact_cash))
        if st.session_state.get("last_save_error"):
            st.error(f"Could not save exact cash: {st.session_state.last_save_error}")
        else:
            st.success("Exact FDRXX cash saved.")
        st.rerun()

    if st.session_state.get("last_cash_message"):
        st.info(st.session_state.last_cash_message)

    st.markdown("#### Total Contributions")
    with st.form("contribution_form"):
        current_floor = round_money(st.session_state.get("protected_min_contributions", CURRENT_PROTECTED_BASELINE_CONTRIBUTIONS))

        new_total = st.number_input(
            "Total Contributions",
            min_value=0.0,
            value=float(st.session_state.total_contributions),
            step=1000.0,
            format="%.2f",
            help="Deploying cash does NOT change this. Lowering this below the protected floor requires authorization.",
        )

        authorize_reduction = False
        if round_money(new_total) < current_floor:
            st.warning(
                f"You are lowering Total Contributions below the protected floor of {format_dollars(current_floor)}. "
                "Only do this if money was actually removed from the account/contribution base."
            )
            authorize_reduction = st.checkbox(
                "Authorize this intentional contribution reduction and reset the protected floor.",
                value=False,
            )

        saved = st.form_submit_button("Save Total Contributions", use_container_width=True)

    if saved:
        st.session_state.total_contributions = round_money(new_total)
        st.session_state.authorize_contribution_reduction_once = bool(authorize_reduction)

        if save_state():
            st.success("Total contributions saved.")
        else:
            st.error(f"Could not save: {st.session_state.last_save_error}")
        st.rerun()

    st.markdown("#### Add New Money to FDRXX")
    cols = st.columns(5)
    quick_amounts = [1000, 5000, 10000, 16000, 32000]
    for i, amt in enumerate(quick_amounts):
        if cols[i].button(f"+ ${amt:,.0f}", use_container_width=True):
            add_new_money(float(amt))
            st.rerun()

    with st.form("custom_cash_form"):
        custom_cash = st.number_input("Custom cash deposit to FDRXX", min_value=0.0, step=500.0, value=0.0, format="%.2f")
        add_custom = st.form_submit_button("Add Custom Deposit", use_container_width=True)

    if add_custom and custom_cash > 0:
        add_new_money(float(custom_cash))
        st.rerun()


def render_deploy_cash(calc: dict) -> None:
    render_section_header(
        "Deploy Cash Into a Position",
        "Deploying lowers FDRXX cash and raises the selected holding. Total contributions do not change."
    )

    calc_df = calc["df"].copy()
    available_cash = round_money(st.session_state.cash_fdrxx)
    ticker_options = sorted(calc_df["ticker"].astype(str).str.upper().tolist())

    with st.form("deploy_cash_form", clear_on_submit=True):
        c1, c2, c3 = st.columns([1.3, 1.0, 0.9])
        with c1:
            deploy_ticker = st.selectbox("Ticker", options=ticker_options)
        with c2:
            deploy_amount = st.number_input(
                "Amount to Deploy",
                min_value=0.0,
                max_value=available_cash if available_cash > 0 else 0.0,
                value=0.0,
                step=100.0,
                format="%.2f",
            )
        with c3:
            st.write("")
            deploy_pressed = st.form_submit_button("Deploy Cash", use_container_width=True, disabled=available_cash <= 0)

    if deploy_pressed:
        deploy_cash_to_position(deploy_ticker, float(deploy_amount), calc_df)
        st.rerun()

    if st.session_state.get("last_deploy_message"):
        st.success(st.session_state.last_deploy_message)


def render_holdings_editor() -> None:
    render_section_header(
        "Portfolio Holdings Editor",
        "Manual share edits do NOT move cash. Use Set Exact FDRXX Cash if Fidelity cash needs to match exactly."
    )

    editor_key = f"portfolio_editor_v{st.session_state.get('editor_version', 0)}"

    with st.form(f"holdings_editor_form_v{st.session_state.get('editor_version', 0)}"):
        edited_df = st.data_editor(
            st.session_state.editor_df,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key=editor_key,
            column_config={
                "ticker": st.column_config.TextColumn("Ticker"),
                "qty": st.column_config.NumberColumn("Qty / Shares", format="%.6f"),
                "avg_cost": st.column_config.NumberColumn("Avg Cost", format="$%.6f"),
                "manual_price": st.column_config.NumberColumn("Manual / Fallback Price", format="$%.4f"),
                "target_weight": st.column_config.NumberColumn("Target Weight %", format="%.2f"),
                "annual_yield": st.column_config.NumberColumn("Annual Yield", format="%.4f"),
                "payout_frequency": st.column_config.TextColumn("Payout Frequency"),
                "payout_months": st.column_config.TextColumn("Payout Months"),
                "notes": st.column_config.TextColumn("Notes"),
            },
        )

        save_holdings_pressed = st.form_submit_button("Save Holdings Changes", use_container_width=True)

    if save_holdings_pressed:
        cleaned = normalize_portfolio_df(edited_df)
        st.session_state.portfolio_df = cleaned.copy()
        st.session_state.editor_df = cleaned.copy()
        st.session_state.last_deploy_message = "Holdings table saved from latest visible editor values."

        ok = save_state()
        sync_editor_from_portfolio()

        if ok:
            st.success("Holdings saved and verified in the full protected snapshot.")
        else:
            st.error(f"Could not save holdings. Error: {st.session_state.last_save_error}")

        st.rerun()


def render_breakdowns(calc: dict) -> None:
    df = calc["df"].copy()

    render_section_header(
        "Holdings Breakdown",
        "Detailed position values, gain/loss, income estimate, and target drift."
    )

    display_df = df[
        [
            "ticker", "qty", "avg_cost", "manual_price", "live_price", "price_used",
            "price_source", "cost_basis", "market_value", "gain_loss", "gain_loss_pct",
            "annual_yield", "monthly_income_est", "current_weight", "target_weight", "drift_dollars",
        ]
    ].copy()

    display_df.columns = [
        "Ticker", "Qty", "Avg Cost", "Manual Price", "Live Price", "Price Used", "Source",
        "Cost Basis", "Market Value", "Gain/Loss", "Gain/Loss %",
        "Annual Yield", "Monthly Income", "Current Weight", "Target Weight %", "Drift $",
    ]

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Qty": st.column_config.NumberColumn("Qty", format="%.6f"),
            "Avg Cost": st.column_config.NumberColumn("Avg Cost", format="$%.4f"),
            "Manual Price": st.column_config.NumberColumn("Manual Price", format="$%.4f"),
            "Live Price": st.column_config.NumberColumn("Live Price", format="$%.4f"),
            "Price Used": st.column_config.NumberColumn("Price Used", format="$%.4f"),
            "Cost Basis": st.column_config.NumberColumn("Cost Basis", format="$%.2f"),
            "Market Value": st.column_config.NumberColumn("Market Value", format="$%.2f"),
            "Gain/Loss": st.column_config.NumberColumn("Gain/Loss", format="$%.2f"),
            "Gain/Loss %": st.column_config.NumberColumn("Gain/Loss %", format="%.2%"),
            "Annual Yield": st.column_config.NumberColumn("Annual Yield", format="%.4f"),
            "Monthly Income": st.column_config.NumberColumn("Monthly Income", format="$%.2f"),
            "Current Weight": st.column_config.NumberColumn("Current Weight", format="%.2%"),
            "Target Weight %": st.column_config.NumberColumn("Target Weight %", format="%.2f"),
            "Drift $": st.column_config.NumberColumn("Drift $", format="$%.2f"),
        },
    )

    render_section_header(
        "Income Breakdown",
        "Estimated monthly and annual income by position."
    )

    income_df = df[["ticker", "market_value", "annual_yield", "monthly_income_est", "annual_income_est"]].copy()
    income_df = income_df.sort_values("monthly_income_est", ascending=False)
    income_df.columns = ["Ticker", "Market Value", "Annual Yield", "Monthly Income", "Annual Income"]

    st.dataframe(
        income_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Market Value": st.column_config.NumberColumn("Market Value", format="$%.2f"),
            "Annual Yield": st.column_config.NumberColumn("Annual Yield", format="%.4f"),
            "Monthly Income": st.column_config.NumberColumn("Monthly Income", format="$%.2f"),
            "Annual Income": st.column_config.NumberColumn("Annual Income", format="$%.2f"),
        },
    )


def render_income_helper(calc: dict) -> None:
    render_section_header(
        "Suggested Use of Available Cash",
        "Priority rules: SPYI/DIVO first, then QQQI/FEPI, then smaller add-ons."
    )

    suggestions = build_smarter_income_suggestions(calc["df"], calc["available_cash"])

    if suggestions.empty:
        st.info("No cash suggestions right now.")
        return

    st.dataframe(
        suggestions,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Suggested Buy $": st.column_config.NumberColumn("Suggested Buy $", format="$%.2f"),
            "Approx Shares": st.column_config.NumberColumn("Approx Shares", format="%.6f"),
            "Price Used": st.column_config.NumberColumn("Price Used", format="$%.4f"),
            "Added Monthly Income": st.column_config.NumberColumn("Added Monthly Income", format="$%.2f"),
        },
    )


def render_system_tools() -> None:
    render_section_header(
        "System Tools",
        "Backup, restore, reload, and safety tools."
    )

    st.warning("Every Save button now writes local backups AND the Supabase cloud state file. Use Download Snapshot Backup only when you want an outside copy before big changes.")

    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("Reverse This Session", use_container_width=True):
            try:
                raw = st.session_state.get("session_start_payload", {})
                state = normalize_state_payload(raw)
                current_floor = round_money(st.session_state.get("protected_min_contributions", CURRENT_PROTECTED_BASELINE_CONTRIBUTIONS))

                if round_money(state.get("total_contributions", 0.0)) < current_floor:
                    st.error(
                        f"Reverse blocked because the session-start snapshot is below the protected floor "
                        f"of {format_dollars(current_floor)}."
                    )
                else:
                    apply_state_dict(state, "Reversed this session back to the state from when the app opened.")
                    save_state()
                    st.success("Session reversed.")
                    st.rerun()
            except Exception as exc:
                st.error(f"Could not reverse session: {exc}")

    with c2:
        if st.button("Reload Best Saved File", use_container_width=True):
            loaded = load_state()
            apply_state_dict(loaded, "Reloaded from best valid full snapshot.")
            st.session_state.loaded_from = loaded.get("_loaded_from", "UNKNOWN")
            st.session_state.version_mismatch_fixed = bool(loaded.get("_version_mismatch_fixed", False))
            st.session_state.startup_write_blocked = bool(loaded.get("_startup_write_blocked", False))
            st.session_state.needs_force_save_to_spread_snapshot = bool(loaded.get("_needs_force_save_to_spread_snapshot", False))
            st.session_state.candidate_summary = loaded.get("_candidate_summary", [])
            st.session_state.rejected_summary = loaded.get("_rejected_summary", [])
            st.rerun()

    with c3:
        if st.button("Force Save State Now", use_container_width=True):
            if save_state():
                st.success("Saved and verified current full dashboard snapshot.")
            else:
                st.error(f"Save failed: {st.session_state.last_save_error}")

    st.markdown("#### Snapshot Backup / Restore")

    payload = make_state_payload()
    st.download_button(
        "Download Snapshot Backup",
        data=json.dumps(payload, indent=2),
        file_name=f"retirement_dashboard_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
        use_container_width=True,
    )

    session_payload = st.session_state.get("session_start_payload", {})
    st.download_button(
        "Download Session-Start Backup",
        data=json.dumps(session_payload, indent=2),
        file_name=f"retirement_dashboard_session_start_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
        use_container_width=True,
    )

    uploaded_file = st.file_uploader("Upload Snapshot Backup", type=["json"], key="snapshot_upload")

    if uploaded_file is not None:
        try:
            uploaded_raw = json.loads(uploaded_file.getvalue().decode("utf-8"))
            uploaded_state = normalize_state_payload(uploaded_raw)
            current_floor = round_money(st.session_state.get("protected_min_contributions", CURRENT_PROTECTED_BASELINE_CONTRIBUTIONS))
            uploaded_total = round_money(uploaded_state["total_contributions"])

            st.info(
                "Uploaded snapshot ready: "
                f"Cash {format_dollars(uploaded_state['cash_fdrxx'])}, "
                f"Total Contributions {format_dollars(uploaded_total)}, "
                f"Protected Floor {format_dollars(uploaded_state.get('protected_min_contributions', uploaded_total))}."
            )

            restore_allowed = True
            authorize_lower_restore = False

            if uploaded_total < current_floor:
                restore_allowed = False
                st.error(
                    f"This uploaded backup is below the current protected floor of {format_dollars(current_floor)}. "
                    "Restore is blocked unless you authorize it as an intentional contribution reduction."
                )
                authorize_lower_restore = st.checkbox(
                    "Authorize restoring this lower contribution snapshot and reset the protected floor.",
                    value=False,
                )
                restore_allowed = bool(authorize_lower_restore)

            if st.button("Restore Uploaded Snapshot And Make It Active", use_container_width=True, disabled=not restore_allowed):
                if authorize_lower_restore:
                    uploaded_state["protected_min_contributions"] = uploaded_total
                    st.session_state.authorize_contribution_reduction_once = True
                else:
                    uploaded_state["protected_min_contributions"] = max(uploaded_total, current_floor)

                apply_state_dict(uploaded_state, "Restored from uploaded snapshot backup.")
                st.session_state.loaded_from = "UPLOADED SNAPSHOT - restored and made active"
                payload_to_save = make_payload_from_state(uploaded_state, force_timestamp=True)
                write_payload_everywhere(payload_to_save)
                st.session_state.last_saved = payload_to_save.get("last_saved", "")
                st.session_state.protected_min_contributions = payload_to_save.get("protected_min_contributions", uploaded_total)
                save_state()
                st.success("Uploaded snapshot restored, saved, backed up in all locations, and made active.")
                st.rerun()

        except Exception as exc:
            st.error(f"That file could not be restored. Error: {exc}")

    st.markdown("#### Save Diagnostics")
    st.caption(f"App version: {APP_BASELINE_VERSION}")
    st.caption(f"State schema version: {STATE_SCHEMA_VERSION}")
    st.caption(f"Supabase cloud persistence: {supabase_persistence_summary()}")
    st.caption(f"Supabase load status: {st.session_state.get('github_load_status', '')}")
    st.caption(f"Supabase save status: {st.session_state.get('github_save_status', '')}")
    st.caption(f"Current working directory: {Path.cwd()}")
    st.caption(f"App directory: {APP_DIR}")
    st.caption(f"Hidden active state file: {STATE_FILE}")
    st.caption(f"Hidden backup file: {BACKUP_FILE}")
    st.caption(f"Hidden last-good file: {LAST_GOOD_FILE}")
    st.caption(f"Root state file: {LEGACY_STATE_FILE}")
    st.caption(f"Root backup file: {LEGACY_BACKUP_FILE}")
    st.caption(f"Root last-good file: {LEGACY_LAST_GOOD_FILE}")
    st.caption(f"Home state file: {HOME_STATE_FILE}")
    st.caption(f"Home backup file: {HOME_BACKUP_FILE}")
    st.caption(f"Home last-good file: {HOME_LAST_GOOD_FILE}")
    st.caption(f"Embedded app-file snapshot exists: {bool(read_embedded_state_payload())}")
    st.caption(f"Hidden state exists: {STATE_FILE.exists()}")
    st.caption(f"Hidden backup exists: {BACKUP_FILE.exists()}")
    st.caption(f"Hidden last-good exists: {LAST_GOOD_FILE.exists()}")
    st.caption(f"Root state exists: {LEGACY_STATE_FILE.exists()}")
    st.caption(f"Root backup exists: {LEGACY_BACKUP_FILE.exists()}")
    st.caption(f"Root last-good exists: {LEGACY_LAST_GOOD_FILE.exists()}")
    st.caption(f"Home state exists: {HOME_STATE_FILE.exists()}")
    st.caption(f"Home backup exists: {HOME_BACKUP_FILE.exists()}")
    st.caption(f"Home last-good exists: {HOME_LAST_GOOD_FILE.exists()}")
    st.caption(f"Last saved: {st.session_state.get('last_saved', 'not yet') or 'not yet'}")
    st.caption(f"Loaded from: {st.session_state.get('loaded_from', 'UNKNOWN')}")
    st.caption(f"Protected floor: {format_dollars(st.session_state.get('protected_min_contributions', 0.0))}")

    if st.session_state.get("last_save_error"):
        st.error(f"Last save error: {st.session_state.last_save_error}")

    st.markdown("#### Dangerous Reset")

    with st.expander("Reset to Current Protected Full-Snapshot Baseline"):
        st.error("Only use this if you want to wipe current numbers back to the current protected baseline.")
        confirm_reset = st.checkbox("I understand this will reset to the current protected full-snapshot baseline.")
        if st.button("Reset to Protected Baseline", use_container_width=True, disabled=not confirm_reset):
            baseline = baseline_state_payload()
            apply_state_dict(baseline, "Reset to current protected full-snapshot baseline complete.")
            st.session_state.loaded_from = "CURRENT PROTECTED FULL-SNAPSHOT BASELINE - manual reset"
            save_state()
            st.rerun()


def main() -> None:
    init_state()
    inject_dashboard_css()

    st.markdown('<div class="dashboard-title">Retirement Paycheck Dashboard</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="dashboard-subtitle">Regular production app &#8226; Supabase cloud save &#8226; protected recovery &#8226; stale-save rejection.</div>',
        unsafe_allow_html=True,
    )

    with st.expander("Save Protection / State Details", expanded=False):
        render_state_health_box()

    settings_cols = st.columns(3)
    with settings_cols[0]:
        new_use_live = st.checkbox("Use Yahoo Finance live prices", value=bool(st.session_state.use_live_prices))
        if new_use_live != st.session_state.use_live_prices:
            st.session_state.use_live_prices = new_use_live
            save_state()
            st.rerun()

    with settings_cols[1]:
        new_auto_sync = st.checkbox("Refresh good live prices on screen", value=bool(st.session_state.auto_sync_prices))
        if new_auto_sync != st.session_state.auto_sync_prices:
            st.session_state.auto_sync_prices = new_auto_sync
            save_state()
            st.rerun()

    with settings_cols[2]:
        if st.button("Sync Prices Now", use_container_width=True):
            get_live_prices_cached.clear()
            sync_calc = calculate_portfolio(
                st.session_state.portfolio_df,
                cash_fdrxx=st.session_state.cash_fdrxx,
                use_live_prices=bool(st.session_state.use_live_prices),
            )
            refresh_saved_manual_prices(sync_calc["df"], persist=True)
            st.session_state.last_price_sync = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
            save_state()
            st.rerun()

    calc = calculate_portfolio(
        st.session_state.portfolio_df,
        cash_fdrxx=st.session_state.cash_fdrxx,
        use_live_prices=bool(st.session_state.use_live_prices),
    )

    # Passive page loads may refresh the on-screen fallback prices, but they do not
    # write a new full snapshot. This prevents a stale state from being preserved
    # just because Yahoo live prices changed.
    refresh_saved_manual_prices(calc["df"], persist=False)

    calc = calculate_portfolio(
        st.session_state.portfolio_df,
        cash_fdrxx=st.session_state.cash_fdrxx,
        use_live_prices=bool(st.session_state.use_live_prices),
    )

    st.markdown(
        f'<span class="status-pill">Last price sync: {st.session_state.last_price_sync or "not yet"}</span>',
        unsafe_allow_html=True,
    )

    render_metrics(calc)

    with st.expander("Open to Edit / Update Holdings, Cash, Backups, and Details", expanded=False):
        st.caption("Viewing mode stays protected while this is closed. Open only when you want to edit holdings, deploy cash, update cash/contributions, view detailed tables, or use backup/restore tools.")

        render_top_controls(calc)
        st.divider()

        render_deploy_cash(calc)
        st.divider()

        render_holdings_editor()
        st.divider()

        render_breakdowns(calc)
        st.divider()

        render_income_helper(calc)
        st.divider()

        render_system_tools()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        st.error("The dashboard stopped safely instead of entering a blank crash screen.")
        st.exception(exc)
