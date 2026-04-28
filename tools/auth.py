import os
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def _build_credentials() -> Credentials:
    """Build Google OAuth credentials entirely from environment variables.

    Required env vars:
        GOOGLE_CLIENT_ID      - OAuth 2.0 client ID
        GOOGLE_CLIENT_SECRET  - OAuth 2.0 client secret
        GOOGLE_REFRESH_TOKEN  - Long-lived refresh token (generated once locally)
    """
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        missing = [
            k for k, v in {
                "GOOGLE_CLIENT_ID": client_id,
                "GOOGLE_CLIENT_SECRET": client_secret,
                "GOOGLE_REFRESH_TOKEN": refresh_token,
            }.items() if not v
        ]
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Set them in your .env file (local) or Vercel Dashboard (production)."
        )

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )

    # Refresh to obtain a valid access token
    creds.refresh(Request())
    return creds


def get_google_service(api_name: str, api_version: str):
    """Return an authorized Google API service client."""
    from googleapiclient.discovery import build
    creds = _build_credentials()
    return build(api_name, api_version, credentials=creds)


def check_auth_status() -> dict:
    """Check whether Google credentials are configured and valid."""
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        return {
            "credentials_file_exists": False,
            "authenticated": False,
            "error": "One or more GOOGLE_* environment variables are not set.",
        }

    try:
        _build_credentials()
        return {"credentials_file_exists": True, "authenticated": True, "error": None}
    except Exception as e:
        return {"credentials_file_exists": True, "authenticated": False, "error": str(e)}
