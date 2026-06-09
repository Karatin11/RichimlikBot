from __future__ import annotations

import gspread
from google.oauth2.service_account import Credentials
from datetime import date

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

COL_TR    = 1  # T/R
COL_NAME  = 2  # Ism
COL_COUNT = 3  # Count

SETTINGS_SHEET     = "Sozlamalar"
REMINDER_TIME_CELL = "B1"   # Eslatma vaqti
ADMIN_ID_CELL      = "B2"   # Admin Telegram ID
DATA_SHEET         = "Ichimliklar"
HISTORY_SHEET      = "Tarix"


def get_client() -> gspread.Client:
    creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    return gspread.authorize(creds)


# ── People ────────────────────────────────────────────────────────────────────

def get_all_people(spreadsheet_id: str) -> list[dict]:
    client = get_client()
    sheet  = client.open_by_key(spreadsheet_id).worksheet(DATA_SHEET)
    rows   = sheet.get_all_values()
    people = []
    for i, row in enumerate(rows[1:], start=2):
        if len(row) >= 2 and row[COL_NAME - 1].strip():
            try:
                tr = int(row[COL_TR - 1])
            except (ValueError, IndexError):
                tr = i - 1
            try:
                count = int(row[COL_COUNT - 1]) if len(row) >= 3 and str(row[COL_COUNT - 1]).strip().isdigit() else 0
            except (ValueError, IndexError):
                count = 0
            people.append({"tr": tr, "name": row[COL_NAME - 1].strip(), "count": count, "row": i})
    people.sort(key=lambda x: x["tr"])
    return people


# ── Queue logic ───────────────────────────────────────────────────────────────

def get_next_person(people: list[dict], skip_trs: list[int] = None) -> dict | None:
    """
    Returns the person who should bring drinks next.
    Logic: pick the person with the LOWEST count.
    If tie — pick by smallest T/R.
    skip_trs: list of T/R values to exclude (already skipped today).
    """
    skip_trs = skip_trs or []
    candidates = [p for p in people if p["tr"] not in skip_trs]
    if not candidates:
        return None
    min_count = min(p["count"] for p in candidates)
    pool = [p for p in candidates if p["count"] == min_count]
    return min(pool, key=lambda x: x["tr"])


def get_person_by_tr(people: list[dict], tr: int) -> dict | None:
    for p in people:
        if p["tr"] == tr:
            return p
    return None


# ── Actions ───────────────────────────────────────────────────────────────────

def increment_count(spreadsheet_id: str, row: int):
    client = get_client()
    sheet  = client.open_by_key(spreadsheet_id).worksheet(DATA_SHEET)
    cur    = sheet.cell(row, COL_COUNT).value
    try:
        new_val = int(cur) + 1 if cur and str(cur).strip().isdigit() else 1
    except Exception:
        new_val = 1
    sheet.update_cell(row, COL_COUNT, new_val)


def add_history(spreadsheet_id: str, person_name: str, note: str = ""):
    client = get_client()
    sheet  = client.open_by_key(spreadsheet_id).worksheet(HISTORY_SHEET)
    today  = date.today().strftime("%d.%m.%Y")
    sheet.append_row([today, person_name, note])


# ── Settings ──────────────────────────────────────────────────────────────────

def get_reminder_time(spreadsheet_id: str) -> str:
    client = get_client()
    try:
        sheet = client.open_by_key(spreadsheet_id).worksheet(SETTINGS_SHEET)
        val   = sheet.acell(REMINDER_TIME_CELL).value
        return val.strip() if val else "12:00"
    except Exception:
        return "12:00"


def get_admin_id(spreadsheet_id: str) -> int:
    client = get_client()
    try:
        sheet = client.open_by_key(spreadsheet_id).worksheet(SETTINGS_SHEET)
        val   = sheet.acell(ADMIN_ID_CELL).value
        return int(val.strip()) if val and val.strip().isdigit() else 0
    except Exception:
        return 0
