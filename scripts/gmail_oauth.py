"""One-time LOCAL OAuth setup. Prints refresh token; do not paste into chat or commit."""
import os
from pathlib import Path
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv()
client_id, client_secret = os.getenv('GOOGLE_CLIENT_ID'), os.getenv('GOOGLE_CLIENT_SECRET')
if not client_id or not client_secret:
    raise SystemExit('First fill GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env')
config = {'installed': {'client_id': client_id, 'client_secret': client_secret,
                        'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                        'token_uri': 'https://oauth2.googleapis.com/token',
                        'redirect_uris': ['http://localhost']}}
flow = InstalledAppFlow.from_client_config(config, scopes=['https://www.googleapis.com/auth/gmail.readonly'])
credentials = flow.run_local_server(port=0, access_type='offline', prompt='consent')
print('GOOGLE_REFRESH_TOKEN=' + (credentials.refresh_token or 'NOT_RETURNED_CHECK_OAUTH_CONSENT'))
print('Keep this token in .env locally. Never share it in chat or commit to GitHub.')
