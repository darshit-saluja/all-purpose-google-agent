import os
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/youtube.readonly",
]

CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "credentials.json")
TOKEN_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "token.json")


def get_google_service(api_name: str, api_version: str):
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError(
            "credentials.json not found. Download it from Google Cloud Console "
            "(OAuth 2.0 Client ID, Desktop App type) and place it in the project root."
        )

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build(api_name, api_version, credentials=creds)


def check_auth_status() -> dict:
    credentials_exist = os.path.exists(CREDENTIALS_FILE)
    if not credentials_exist:
        return {"credentials_file_exists": False, "authenticated": False, "error": None}

    try:
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            if creds and creds.valid:
                return {"credentials_file_exists": True, "authenticated": True, "error": None}
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(TOKEN_FILE, "w") as f:
                    f.write(creds.to_json())
                return {"credentials_file_exists": True, "authenticated": True, "error": None}
        return {"credentials_file_exists": True, "authenticated": False, "error": None}
    except Exception as e:
        return {"credentials_file_exists": True, "authenticated": False, "error": str(e)}
