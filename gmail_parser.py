import os
import base64
import re
from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from config_loader import load_config
from logger import setup_logger

logger = setup_logger(name="gmail_parser")
config = load_config()

TOKEN_PATH = Path("token.json")
CLIENT_SECRET_PATH = Path(config["gmail_credentials_path"])
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def extract_otp_and_amount(body):
    otp_match = re.search(r'\b\d{6}\b', body)
    amount_match = re.search(r'Rs[ ]?([\d,]+(?:\.\d{1,2})?)', body)
    otp = otp_match.group(0) if otp_match else None
    amount = amount_match.group(1).replace(',', '') if amount_match else None
    logger.info(f"Extracted from email body → OTP: {otp}, Amount: {amount}")
    return otp, float(amount) if amount else None

def fetch_latest_otps(subject_filter='OTP', max_results=5):
    service = get_gmail_service()
    query = config["gmail_query"]
    otp_regex = config["otp_regex"]
    results = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
    messages = results.get('messages', [])

    otp_entries = []
    for msg in messages:
        try:
            msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
            payload = msg_data.get('payload', {})
            headers = payload.get('headers', [])
            date_header = next((h['value'] for h in headers if h['name'] == 'Date'), None)
            timestamp = datetime.strptime(date_header, '%a, %d %b %Y %H:%M:%S %z') if date_header else None

            parts = payload.get('parts', [])
            body_data = ''
            for part in parts:
                if part.get('mimeType') == 'text/plain':
                    body_data = part['body'].get('data', '')
                    break
            if not body_data and 'body' in payload:
                body_data = payload['body'].get('data', '')

            decoded_body = base64.urlsafe_b64decode(body_data.encode('ASCII')).decode('utf-8', errors='ignore')
            otp, amount = extract_otp_and_amount(decoded_body)

            if otp and amount:
                otp_entries.append({
                    'timestamp': timestamp,
                    'otp': otp,
                    'amount': amount,
                    'raw': decoded_body,
                    'gmail_id': msg['id']
                })

        except Exception as e:
            logger.warning(f"Failed to process email ID {msg['id']}: {type(e).__name__} - {e}")
            continue

    return otp_entries
