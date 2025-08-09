import tkinter as tk
import re
from gmail_parser import fetch_latest_otps
from config_loader import load_config, load_transaction_types
from logger import setup_logger
from excel_logger import log_otp_to_excel
from datetime import datetime
from duplication_check import is_recent_duplicate_transaction
from sync_to_google import push_to_google_sheet
from downsync_from_google import refresh_transaction_types, pull_from_google_sheet
from pathlib import Path
import threading

# Setup
config = load_config()
logger = setup_logger("otp_ui")
MASTER_SHEET_PATH = Path(config["transaction_log_excel_path"])

# Globals
root = None
fields = {}
payment_var = None
dropdown = None
otp_label = None

# OTP matching logic
def match_amount(email_amount, expected_amount, tolerance):
    try:
        logger.info(f"Comparing email amount {email_amount} with bank amount {expected_amount} (tolerance {tolerance})")
        return abs(email_amount - float(expected_amount)) <= tolerance
    except Exception as e:
        logger.warning(f"Amount matching failed: {e}")
        return False

def get_latest_valid_otp(vehicle_reg, chassis_number, owner_name, payment_type, rto_amount, bank_amount, employee_name):
    try:
        otp_entries = fetch_latest_otps()
        for entry in otp_entries:
            if match_amount(entry["amount"], bank_amount, config["amount_tolerance"]):
                logger.info(f"OTP matched for {vehicle_reg} by {employee_name}: {entry['otp']}")
                return {
                    "otp": entry["otp"],
                    "timestamp": entry["timestamp"],
                    "vehicle_reg": vehicle_reg,
                    "chassis_number": chassis_number,
                    "owner_name": owner_name,
                    "payment_type": payment_type,
                    "rto_amount": rto_amount,
                    "bank_amount": bank_amount,
                    "employee_name": employee_name,
                    "gmail_id": entry["gmail_id"],
                    "raw": entry["raw"]
                }
        logger.warning(f"No matching OTP found for {vehicle_reg}")
        return None
    except Exception as e:
        logger.error(f"OTP fetch failed: {e}")
        return None

# Build input fields
def build_input_fields(root, labels):
    global payment_var, dropdown
    fields = {}

    payment_options = load_transaction_types()
    payment_options.insert(0, "Select Payment Type")
    payment_var = tk.StringVar(value=payment_options[0])

    for label in labels:
        tk.Label(root, text=f"{label}:").pack(pady=(10, 0))
        if label == "Payment Type":
            dropdown = tk.OptionMenu(root, payment_var, *payment_options)
            dropdown.config(
                width=37,
                bg="white",
                fg="black",
                highlightthickness=1,
                relief="solid"
            )
            dropdown.pack()
            fields[label] = payment_var
        else:
            entry = tk.Entry(root, width=40)
            entry.pack()
            fields[label] = entry

    return fields

# OTP fetch logic
def get_otp():
    global otp_label

    payment_type = fields["Payment Type"].get().strip()
    if payment_type == "Select Payment Type":
        otp_label.config(text="❌ Please select a valid payment type.")
        logger.warning("Payment type not selected.")
        return

    vehicle_number = fields["Vehicle Reg. Number"].get().strip()
    chassis_number = fields["Chassis Number"].get().strip()    
    rto_amount = fields["Transaction Amount - RTO Portal"].get().strip()
    bank_amount = fields["Transaction Amount including Bank Charges"].get().strip()

    if not vehicle_number and not chassis_number:
        otp_label.config(text="❌ Please enter either Vehicle Number or Chassis Number.")
        logger.warning("Both Vehicle Number and Chassis Number are empty.")
        return

    excel_path = config["transaction_log_excel_path"]
    if is_recent_duplicate_transaction(
        excel_path,
        vehicle_number,
        chassis_number,
        payment_type,
        rto_amount,
        bank_amount
    ):
        otp_label.config(text="⚠️ Duplicate transaction detected.\nPlease check Vehicle Number / Payment Type.")
        logger.warning(f"Duplicate transaction detected for Vehicle: {vehicle_number} or Chassis: {chassis_number}")
        return

    data = get_latest_valid_otp(
        vehicle_number,
        chassis_number,
        fields["Owner Name"].get(),
        payment_type,
        rto_amount,
        bank_amount,
        fields["Employee Name"].get()
    )

    if data:
        otp_label.config(text=f"✅ OTP: {data['otp']}")
        logger.info(f"OTP displayed for {data['vehicle_reg']}")
        log_otp_to_excel(data)
        push_to_google_sheet()
        logger.info("OTP logged and synced to Google Sheets")
    else:
        otp_entries = fetch_latest_otps()
        if otp_entries:
            otp_label.config(text="⚠️ No OTP matched: Amount mismatch")
            logger.warning("OTP(s) found, but none matched the bank amount")
        else:
            otp_label.config(text="❌ No OTP found in inbox")
            logger.warning("No OTP emails found in inbox")

def threaded_get_otp():
    fetch_button.config(state="disabled")
    otp_label.config(text="⏳ Fetching OTP...")

    def wrapped():
        get_otp()
        fetch_button.config(state="normal")

    threading.Thread(target=wrapped, daemon=True).start()


# Rebuild UI
def rebuild_ui(root):
    global fields, otp_label, fetch_button

    for widget in root.winfo_children():
        widget.destroy()

    labels = [
        "Vehicle Reg. Number",
        "Chassis Number",
        "Owner Name",
        "Payment Type",
        "Transaction Amount - RTO Portal",
        "Transaction Amount including Bank Charges",
        "Employee Name"
    ]

    fields = build_input_fields(root, labels)

    otp_label = tk.Label(root, text="OTP: ---", font=("Helvetica", 10), fg="blue")
    otp_label.pack(pady=20)

    fetch_button = tk.Button(root, text="Fetch OTP", command=threaded_get_otp)
    fetch_button.pack()
    tk.Button(root, text="Start New Entry", command=clear_form).pack(pady=10)

# Clear form and refresh config
def clear_form():
    try:
        pull_from_google_sheet()
        refresh_transaction_types(
            excel_path=MASTER_SHEET_PATH,
            tab_name="Transaction_Types",
            json_path=Path("transaction_types.json")
        )
        logger.info("✅ Config refreshed from Google Sheets")
    except Exception as e:
        logger.warning(f"⚠️ Failed to refresh config: {e}")

    rebuild_ui(root)

# Launch UI
def launch_ui():
    global root
    root = tk.Tk()
    root.title("Secure OTP Utility")
    root.geometry("420x500")
    root.resizable(False, False)

    rebuild_ui(root)
    root.mainloop()
