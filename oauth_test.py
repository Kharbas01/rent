from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

flow = InstalledAppFlow.from_client_secrets_file(
    "credentials.json",
    SCOPES,
)

creds = flow.run_local_server(port=8080)

service = build("drive", "v3", credentials=creds)

print("✅ Login Successful")