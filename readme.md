🧾 Daily Transactions Log — OTP-Based Validation System
📌 Overview
This system validates transaction entries in a local Excel file by cross-referencing them with OTP-bearing emails. It ensures that only verified transactions are logged, with robust error handling, logging, and config-driven flexibility. The validated data is then synced to a Google Sheet titled Daily_Transactions_Log_OTP_based.

🧱 Architecture Summary
plaintext
┌────────────────────────────┐
│ Local Excel File           │◄────┐
│ (Staging + Logs)           │     │
└────────────────────────────┘     │
                                   ▼
┌────────────────────────────┐   ┌────────────────────────────┐
│ config_loader.py           │   │ email_parser.py            │
│ - Loads config.json        │   │ - Parses OTP emails        │
└────────────────────────────┘   └────────────────────────────┘
         ▲                                ▼
         │                                │
         └────────────┐         ┌─────────┘
                      ▼         ▼
               ┌────────────────────────────┐
               │ validator.py               │
               │ - Validates amount vs OTP  │
               │ - Returns matching OTP     │
               └────────────────────────────┘
                             │
                             ▼
               ┌────────────────────────────┐
               │ logger.py                  │
               │ - Centralized logging      │
               └────────────────────────────┘
                             │
                             ▼
               ┌────────────────────────────┐
               │ sync.py / downsync.py      │
               │ - Push/pull to Google Sheet│
               └────────────────────────────┘
📂 File-Level Breakdown
1. config_loader.py
Loads config.json for runtime parameters.

Used by validator.py to fetch amount_tolerance.

2. email_parser.py
Parses recent OTP-bearing emails.

Returns list of dicts: {"amount": "1,000.00", "otp": "123456", ...}.

3. validator.py
Validates entered amount against parsed emails.

Returns matching OTP if found.

Logs match/mismatch/parse errors.

4. logger.py
Centralized logging setup.

Used by validator.py for traceability.

5. config.json
Stores config values like:

json
{
  "amount_tolerance": 0.01,
  "email_sender_filter": "noreply@bank.com"
}
6. sync.py (assumed)
Pushes validated rows from Excel to Google Sheets.

Ensures no duplication or overwrite.

May use Sheets API or gspread.

7. downsync.py (assumed)
Pulls latest rows from Google Sheets into Excel.

Updates staging or audit tabs.

May filter by timestamp or transaction type.

📊 Sheet Structure
Google Sheet: Daily_Transactions_Log_OTP_based

A1: Timestamp

B1: Transaction Amount

C1: OTP

D1: Transaction Type

Tabs: Transaction_Log, Transaction_Types, possibly others

🔄 Local ↔ Cloud Sync Model
✅ Local Excel: Primary Workspace
All parsing, validation, and logging happen locally.

Excel contains:

Transaction staging

Audit logs

Sync control flags

🔁 Google Sheets: Source of Truth
Updated via:

Sync: Pushes validated entries from Excel to Sheets.

Downsync: Pulls latest entries from Sheets into Excel.

🔧 Sync/Downsync Logic
Sync:

Reads validated rows from Excel.

Writes to Google Sheet.

Avoids duplication via timestamp or ID checks.

Downsync:

Fetches latest rows from Google Sheet.

Updates local Excel tabs.

May overwrite or merge based on config.

✅ Validation Logic
python
abs(float(entered_amount) - float(email_amount)) <= tolerance
Tolerance is configurable.

Amounts cleaned of commas and whitespace.

Logs every step.

📌 Logging Examples
✅ Match found: entered=1000.0, email=1000.0, otp=123456

🔍 No match: entered=1000.0, email=999.99

⚠️ Failed to parse email amount: 'abc' (ValueError)

❌ No matching OTP found for amount: 1000.0

🛠️ Extensibility Ideas
Filter emails by timestamp or sender domain

Add CLI or GUI wrapper for manual entry

Modularize sync/downsync for handover clarity

Add audit trail tab in Excel for rejected entries