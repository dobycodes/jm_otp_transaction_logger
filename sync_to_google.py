import gspread
import json
from openpyxl import load_workbook
from pathlib import Path
from oauth2client.service_account import ServiceAccountCredentials
from logger import setup_logger

# Initialize logger
logger = setup_logger(name="sheets_sync")

CONFIG_PATH = Path("config.json")
if not CONFIG_PATH.exists():
    logger.error(f"❌ config.json not found at: {CONFIG_PATH.resolve()}")
    raise FileNotFoundError("Missing config.json")

with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

CREDENTIALS_PATH = Path(config["sheets_credentials_path"])
LOCAL_EXCEL_SHEET_PATH = Path(config["transaction_log_excel_path"])
SHEET_ID = config.get("spreadsheet_id", "your_google_spreadsheet_id_here")

# Tab mappings: Excel → Google Sheets
TAB_MAPPING = config["tab_mapping"]


def normalize(text):
    return str(text).strip().replace("\n", " ").replace("\r", "")

def push_tab(excel_tab, sheet_tab):
    try:
        # Authenticate with service account
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, scope)
        client = gspread.authorize(creds)

        # Open spreadsheet and ensure tab exists
        spreadsheet = client.open(config["spreadsheet_id"])
        try:
            sheet = spreadsheet.worksheet(sheet_tab)
            logger.info(f"🔍 Found existing tab: '{sheet_tab}'")
        except gspread.exceptions.WorksheetNotFound:
            logger.warning(f"⚠️ Tab '{sheet_tab}' not found. Creating new worksheet...")
            sheet = spreadsheet.add_worksheet(title=sheet_tab, rows="1000", cols="50")
            logger.info(f"✅ Created new tab: '{sheet_tab}'")

        sheet.clear()

        # Load Excel workbook and tab
        wb = load_workbook(LOCAL_EXCEL_SHEET_PATH, data_only=True)
        if excel_tab not in wb.sheetnames:
            logger.warning(f"⚠️ Excel tab '{excel_tab}' not found in workbook. Skipping sync.")
            return

        ws = wb[excel_tab]
        excel_headers = [normalize(cell.value) for cell in ws[1]]
        sheet.append_row(excel_headers)
        logger.info(f"📝 Headers pushed ({len(excel_headers)} columns) to '{sheet_tab}'")

        rows = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if any(cell is not None and str(cell).strip() for cell in row):
                cleaned_row = [str(cell) if cell is not None else "" for cell in row]
                rows.append(cleaned_row)

        if rows:
            sheet.append_rows(rows, value_input_option="USER_ENTERED")
            logger.info(f"✅ Synced {len(rows)} rows → '{sheet_tab}'")
        else:
            logger.info(f"ℹ️ No non-empty rows to sync for '{excel_tab}'")

    except Exception as e:
        logger.error(f"❌ Sync failed for '{excel_tab}': {e}")

def push_to_google_sheet():
    for excel_tab, sheet_tab in TAB_MAPPING.items():
        try:
            push_tab(excel_tab, sheet_tab)
        except Exception as e:
            logger.error(f"❌ Sync failed for '{excel_tab}': {type(e).__name__} - {e}")




