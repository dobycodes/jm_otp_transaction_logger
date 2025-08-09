import os
import re
import pandas as pd
from PyPDF2 import PdfReader
from datetime import datetime

DEBUG = True  # Toggle debug logging

# ─────────────────────────────────────────────
# Utility Functions
# ─────────────────────────────────────────────

def normalize_text(raw):
    text = raw.replace("\r", "\n").replace("\xa0", " ")
    text = re.sub(r"[^\x00-\x7F]+", "", text)  # remove non-ASCII
    text = re.sub(r"\n+", "\n", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()

def re_search(pattern, text, label):
    match = re.search(pattern, text)
    return match.group(1) if match else "NOT FOUND"

# ─────────────────────────────────────────────
# Format-Specific Parsers
# ─────────────────────────────────────────────
def extract_vehicle_class(text):
    # Try labeled extraction first
    match = re.search(r"Vehicle Class:\s*(.+)", text)
    if match:
        return match.group(1).strip()
    
    # Fallback: scan for known class keywords
    known_classes = [
        "Articulated Vehicle", "Goods Carrier", "Motor Cab", "Omni Bus",
        "Trailer", "Three Wheeler", "Tractor", "Private Service Vehicle"
    ]
    for cls in known_classes:
        if cls in text:
            return cls
    return "Vehicle Class → NOT FOUND"

def parse_mv_tax(text):
    return {
        "Receipt No": " / ".join(re.findall(r"MH\d+V\d+|MH\d+C\d+", text)),
        "GRN No": re_search(r"GRN No: (\d+)", text, "GRN No"),
        "TIN": re_search(r"Transaction Identification Number\s+([\w]+)", text, "TIN"),
        "Tax Period": " to ".join(re.findall(r"\d{2}-[A-Za-z]{3}-\d{4}", text)),
        "Amount": re_search(r"GRAND TOTAL \(in Rs\):\s*(\d+)", text, "Amount"),
        "Vehicle No": re_search(r"Vehicle No:\s*([A-Z0-9]+)", text, "Vehicle No"),
        "Chassis No": re_search(r"Chasis No:\s*([A-Z0-9]+)", text, "Chassis No"),
        "Vehicle Class": re_search(r"Vehicle Class:\s*(.*)", text, "Vehicle Class"),
        "Transaction Date": re_search(r"Transaction Date:\s*(\d{2}-[A-Za-z]{3}-\d{4} \d{2}:\d{2} (?:AM|PM))", text, "Transaction Date"),
        "Bank Ref No": re_search(r"Bank Reference Number:\s*(\d+)", text, "Bank Ref No"),
        "Vehicle Class": extract_vehicle_class(text),
    }

def extract_amount(text):
    auth_block = re.search(r"Authorization Details:(.*?)(?:Transaction|Note:)", text, re.DOTALL)
    if auth_block:
        block_text = auth_block.group(1)
        match = re.search(r"\d{2}-\d{2}-\d{4}\s+\d{2}-\d{2}-\d{4}\s+(\d{3,6})", block_text)
        return match.group(1) if match else "Amount → NOT FOUND"
    return "Amount → NOT FOUND"


def parse_np_receipt(text):
    return {
        "Vehicle No": re_search(r"Regn\. No\.:\s*([A-Z0-9]+)", text, "Vehicle No"),
        "Chassis No": re_search(r"Chassis No\.:\s*([A-Z0-9]+)", text, "Chassis No"),
        "NP Auth No": re_search(r"NP Auth No:\s*([A-Z0-9\/]+)", text, "NP Auth No"),
        "Permit Validity": " to ".join(re.findall(r"\d{2}-\d{2}-\d{4}", text)),
        "Fee": re_search(r"Amount\s*\n\s*(\d{3,6})", text, "Fee"),
        "Penalty": re_search(r"Penalty\s*\n\s*(\d{1,5})", text, "Penalty"),
        "Amount": extract_amount(text),
        "Grand Total": extract_amount(text),
        "Fee": extract_amount(text),
        "Receipt No": re_search(r"Transaction Id:\s*(\d+)", text, "Transaction ID"),
        "Transaction Date": re_search(r"Transaction Date:\s*(\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2})", text, "Transaction Date"),
        "Bank Ref No": re_search(r"Bank Ref No:\s*(\d+)", text, "Bank Ref No"),
        "Vehicle Class": re_search(r"Vehicle Class:\s*(.+?)\s+Owner Name:", text, "Vehicle Class"),
    }


def parse_permit_renewal(text):
    return {
        "Receipt No": " / ".join(re.findall(r"MH\d+[PW]\d+", text)),
        "Vehicle No": re_search(r"Vehicle No:\s*(MH\d{2}[A-Z]{2}\d{4})", text, "Vehicle No"),
        "Chassis No": re_search(r"Chassis No:\s*([A-Z0-9]{17})", text, "Chassis No"),
        "Fee": re_search(r"Total\s+(\d+\.\d+)", text, "Fee"),
        "Penalty": re_search(r"Penalty\s+(\d+\.\d+)", text, "Penalty"),
        "Grand Total": re_search(r"GRAND TOTAL \(in Rs\):\s*(\d+)", text, "Grand Total"),
        "Tax Paid Upto": re_search(r"Tax Paid\s+Upto:\s*(\d{2}-[A-Za-z]{3}-\d{4})", text, "Tax Paid Upto"),
        "Description": re_search(r"Description\s*[:\-]?\s*(.*)", text, "Description"),
        "Transaction Date": re_search(r"Receipt Date:\s*(\d{2}-[A-Za-z]{3}-\d{4})", text, "Transaction Date"),
        "Vehicle Class": re_search(r"Vehicle Class:\s*(.+?)\s+Owner Name:", text, "Vehicle Class"),
    }

def extract_chassis_number(text):
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "Chassis No:" in line or "Chasis No:" in line:
            # Try extracting directly from the same line
            match = re.search(r"Chassis No:\s*([A-Z0-9]{10,17})", line)
            if not match:
                match = re.search(r"Chasis No:\s*([A-Z0-9]{10,17})", line)
            if match:
                return match.group(1)
            # If not found, look ahead up to 5 lines
            for j in range(i+1, min(i+6, len(lines))):
                candidate = lines[j].strip()
                if re.fullmatch(r"[A-Z0-9]{10,17}", candidate):
                    return candidate
    return "Chassis No → NOT FOUND"

def parse_new_registration(text):
    fee_lines = re.findall(r"([A-Za-z /]+)\s+(\d+)\s+0\s+(\d+)", text)

    # Try both transaction date formats
    txn_date = re_search(r"Print on\s*(\d{2}-[A-Za-z]{3}-\d{4} \d{2}:\d{2}:\d{2})", text, "Transaction Date")
    if txn_date == "NOT FOUND":
        txn_date = re_search(r"Printed On:\s*(\d{2}-[A-Za-z]{3}-\d{4} \d{2}:\d{2}:\d{2})", text, "Transaction Date")

    return {
        "Receipt No": " / ".join(re.findall(r"MH\d+D\d+|MH\d+\d+", text)),
        "Vehicle Registration Date": re_search(r"Vehicle Registration Date:\s*(\d{2}-\d{2}-\d{4})", text, "Vehicle Registration Date"),
        "Grand Total": re_search(r"GRAND TOTAL \(in Rs\):\s*(\d+)", text, "Grand Total"),
        "Chassis No": extract_chassis_number(text),
        "Transaction Date": txn_date,
        "Vehicle No": re_search(r"Vehicle No:\s*([A-Z0-9]+)", text, "Vehicle No"),
        "Bank Ref No": re_search(r"Bank Reference\s*Number:\s*(\d{10})", text, "Bank Ref No"),
        "Vehicle Class": re_search(r"Vehicle Class:\s*(.+?)\s+Owner Name:", text, "Vehicle Class"),
    }



# ─────────────────────────────────────────────
# Dispatcher & Logging
# ─────────────────────────────────────────────

def classify_and_parse(text, filename):
    text = normalize_text(text)
    fname = filename.upper()
    if "MV TAX" in fname or "MV Tax" in text:
        schema = "MV Tax Receipt"
        data = parse_mv_tax(text)
    elif "NP" in fname or "National Permit Composite Fee Payment Detail" in text or "NP Auth No" in text:
        schema = "National Permit Receipt"
        data = parse_np_receipt(text)
    elif "PERMIT RENEWAL" in fname or "Renewal of Permit Authorization" in text:
        schema = "Permit Renewal Receipt"
        data = parse_permit_renewal(text)
    elif "NEW REGISTRATION" in fname or "E-FEE" in text or "Fitness Inspection" in text:
        schema = "New Registration Receipt"
        data = parse_new_registration(text)
    else:
        schema = "Unknown Format"
        data = {}
    data["Schema"] = schema
    data["File Name"] = filename
    return data

def log_to_excel(data_list, output_file="rto_receipts_log.xlsx"):
    df = pd.DataFrame(data_list)
    df["Logged At"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df["Missing Fields"] = df.apply(lambda row: [k for k, v in row.items() if v == "NOT FOUND"], axis=1)
    if os.path.exists(output_file):
        existing = pd.read_excel(output_file)
        df = pd.concat([existing, df], ignore_index=True)
    df.to_excel(output_file, index=False)

def batch_process(folder_path):
    all_data = []
    for file in os.listdir(folder_path):
        if file.lower().endswith(".pdf"):
            try:
                full_path = os.path.join(folder_path, file)
                reader = PdfReader(full_path)
                text = "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
                parsed = classify_and_parse(text, file)
                all_data.append(parsed)
                print(f"✅ Parsed: {file} as {parsed['Schema']}")
            except Exception as e:
                print(f"❌ Failed: {file} — {e}")
    log_to_excel(all_data)

# ─────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    batch_process("rto_reciepts")
    print("📂 Batch processing complete. Check rto_receipts_log.xlsx for results.")
