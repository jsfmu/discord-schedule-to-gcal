"""One-time script to authorize Google Calendar. Run: python auth_gcal.py"""

import os
from dotenv import load_dotenv
from calendar_client import run_auth_flow
from db import init_db, save_gcal_token

load_dotenv()
MY_DISCORD_USER_ID = int(os.getenv("MY_DISCORD_USER_ID", "0"))

def main():
    init_db()
    print("Opening browser for Google sign-in...")
    token = run_auth_flow(lambda tj: save_gcal_token(MY_DISCORD_USER_ID, tj))
    if token:
        print("Authorization successful. Token saved to data.db")
    else:
        print("Authorization failed.")

if __name__ == "__main__":
    main()
