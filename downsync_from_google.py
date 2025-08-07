import json
from pathlib import Path
from openpyxl import load_workbook
from google.oauth2 import service_account
from googleapiclient.discovery import build
from logger import setup_logger

logger = setup_logger(name="sheets_downsync")

# 🔧 Load configuration
CONFIG_PATH = Path("config.json")
if not CONFIG_PATH.exists():
    logger.error(f"❌ config.json not found at: {CONFIG_PATH.resolve()}")
    raise FileNotFoundError("Missing config.json")

with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

CREDENTIALS_PATH = Path(config["sheets_credentials_path"])
LOCAL_EXCEL_SHEET_PATH = Path(config["transaction_log_excel_path"])
SHEET_ID = config["spreadsheet_id"]
TAB_MAPPING = config["tab_mapping"]

def pull_tab(sheet_tab, local_tab):
    if not CREDENTIALS_PATH.exists():
        logger.error(f"❌ Credential file not found: {CREDENTIALS_PATH.resolve()}")
        return

    try:
        creds = service_account.Credentials.from_service_account_file(
            str(CREDENTIALS_PATH),
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        service = build("sheets", "v4", credentials=creds)
    except Exception as e:
        logger.error(f"❌ Failed to initialize Google Sheets service: {e}")
        return

    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range=sheet_tab
        ).execute()
        rows = result.get("values", [])
    except Exception as e:
        logger.error(f"❌ Failed to fetch data from tab '{sheet_tab}': {e}")
        return

    # 🧩 Step 1: Handle empty Sheets tab
    if not rows:
        logger.info(f"🆕 First-time setup: No data found in Sheets tab '{sheet_tab}' — initializing empty sync.")
        rows = []

    try:
        wb = load_workbook(LOCAL_EXCEL_SHEET_PATH)
        if local_tab not in wb.sheetnames:
            logger.warning(f"⚠️ Excel tab '{local_tab}' not found in workbook. Creating it...")
            wb.create_sheet(local_tab)
        ws = wb[local_tab]
    except Exception as e:
        logger.error(f"❌ Failed to access workbook or tab '{local_tab}': {e}")
        return

    # 🧩 Step 2: Create headers if Excel tab is empty
    if ws.max_row == 0 and rows:
        logger.info(f"📝 Initializing Excel tab '{local_tab}' with headers from Sheets.")
        ws.append(rows[0])
        rows = rows[1:]

    # 🧩 Step 3: Skip sync if both sides are empty
    if not rows and ws.max_row <= 1:
        logger.info(f"⏭️ Skipping sync for '{local_tab}' — both Sheets and Excel are empty.")
        return

    ws.delete_rows(2, ws.max_row)  # Keep headers if present

    for i, row in enumerate(rows, start=2):  # Start from row 2 if headers exist
        for j, value in enumerate(row, start=1):
            ws.cell(row=i, column=j).value = value

    wb.save(LOCAL_EXCEL_SHEET_PATH)
    logger.info(f"✅ Reverse sync completed for '{local_tab}'. {len(rows)} rows copied.")


def pull_from_google_sheet():
    logger.info("🔄 Starting full reverse sync from Google Sheets to local Excel...")
    for sheet_tab, local_tab in TAB_MAPPING.items():
        pull_tab(sheet_tab, local_tab)