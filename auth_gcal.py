"""
One-time Google Calendar OAuth for local use.
Runs a small local server to capture the auth code and writes token.json next to credentials.json.
"""

import pathlib
import webbrowser
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Include Tasks scope in addition to Calendar
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
]
BASE_PATH = pathlib.Path(__file__).parent
CREDENTIALS_PATH = BASE_PATH / "credentials.json"
TOKEN_PATH = BASE_PATH / "token.json"


def get_creds() -> Credentials:
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
        try:
            # Prefer local server with browser if available
            webbrowser.open_new("http://localhost:")  # hint to Windows to allow browser pop
            creds = flow.run_local_server(port=0)
        except Exception:
            # Fallback to copy/paste console flow
            auth_url, _ = flow.authorization_url(prompt="consent")
            print("Open this URL, approve access, and paste the code below:")
            print(auth_url)
            code = input("Code: ").strip()
            creds = flow.fetch_token(code=code)
    TOKEN_PATH.write_text(creds.to_json())
    return creds


def main() -> None:
    creds = get_creds()
    print("Auth OK. Token cached at", TOKEN_PATH)


if __name__ == "__main__":
    main()
