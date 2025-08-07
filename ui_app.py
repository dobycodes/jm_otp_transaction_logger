import tkinter as tk
import re
from gmail_parser import fetch_latest_otps
from config_loader import load_config
from logger import setup_logger
from excel_logger import log_otp_to_excel
from datetime import datetime
from duplication_check import is_recent_duplicate_transaction


# Setup
config = load_config()
logger = setup_logger("otp_ui")

# OTP matching logic
def match_amount(email_amount, expected_amount, tolerance):
    try:
        logger.info(f"Comparing email amount {email_amount} with bank amount {expected_amount} (tolerance {tolerance})")
        return abs(email_amount - float(expected_amount)) <= tolerance
    except Exception as e:
        logger.warning(f"Amount matching failed: {e}")
        return False

def get_latest_valid_otp(vehicle_reg,chassis_number, owner_name, payment_type, rto_amount, bank_amount, employee_name):
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

# GUI setup
def launch_ui():
    root = tk.Tk()
    root.title("Secure OTP Utility")
    root.geometry("400x480")
    root.resizable(False, False)

    # Input fields
    fields = {}
    labels = [
        "Vehicle Reg. Number",
        "Chassis Number",
        "Owner Name",
        "Payment Type",
        "Transaction Amount - RTO Portal",
        "Transaction Amount including Bank Charges",
        "Employee Name"
    ]

    for label in labels:
        tk.Label(root, text=f"{label}:").pack(pady=(10, 0))
        entry = tk.Entry(root, width=40)
        entry.pack()
        fields[label] = entry

    # OTP display
    otp_label = tk.Label(root, text="OTP: ---", font=("Helvetica", 10), fg="blue")
    otp_label.pack(pady=20)

    def get_otp():
        

        # Duplicate check before OTP fetch
        vehicle_number = fields["Vehicle Reg. Number"].get().strip()
        chassis_number = fields["Chassis Number"].get().strip()  # Ensure this field exists in your UI
        payment_type = fields["Payment Type"].get().strip()
        rto_amount = fields["Transaction Amount - RTO Portal"].get().strip()
        bank_amount = fields["Transaction Amount including Bank Charges"].get().strip()

        excel_path = "OTP_transaction_list.xlsx"
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


        # Proceed with OTP fetch
        data = get_latest_valid_otp(
            fields["Vehicle Reg. Number"].get(),
            fields["Chassis Number"].get(),
            fields["Owner Name"].get(),
            fields["Payment Type"].get(),
            fields["Transaction Amount - RTO Portal"].get(),
            fields["Transaction Amount including Bank Charges"].get(),
            fields["Employee Name"].get()
        )

        if data:
            otp_label.config(text=f"✅ OTP: {data['otp']}")
            logger.info(f"OTP displayed for {data['vehicle_reg']}")
            log_otp_to_excel(data)
            logger.info("OTP logged to Excel")
        else:
            # Check if any OTPs were fetched at all
            otp_entries = fetch_latest_otps()
            if otp_entries:
                otp_label.config(text="⚠️ No OTP matched: Amount mismatch")
                logger.warning("OTP(s) found, but none matched the bank amount")
            else:
                otp_label.config(text="❌ No OTP found in inbox")
                logger.warning("No OTP emails found at all")


    def clear_form():
        for entry in fields.values():
            entry.delete(0, tk.END)
        otp_label.config(text="OTP: ---")

    # Buttons
    tk.Button(root, text="Fetch OTP", command=get_otp).pack()
    tk.Button(root, text="Start New Entry", command=clear_form).pack(pady=10)

    root.mainloop()
