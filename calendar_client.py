"""Google Calendar OAuth and event creation."""

import datetime
import json
import logging
from pathlib import Path
from typing import List, Optional, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from parser import Shift

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
CREDENTIALS_PATH = Path(__file__).parent / "credentials.json"
EVENT_TITLE = "Baskin Robbins Shift"
EVENT_LOCATION = "Baskin Robbins - Mission Blvd, Hayward"

DAY_TO_WEEKDAY = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


def _next_occurrence(day_code: str, tz: datetime.timezone) -> datetime.date:
    """Return next occurrence of day from today (in tz)."""
    today = datetime.datetime.now(tz).date()
    target = DAY_TO_WEEKDAY[day_code]
    days_ahead = (target - today.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7  # if today is that day, use next week
    return today + datetime.timedelta(days=days_ahead)


def _parse_time(s: str) -> Tuple[int, int]:
    h, m = map(int, s.split(":"))
    return h, m


def create_events(
    shifts: List[Shift],
    tz_str: str,
    token_json: str,
) -> Tuple[List[dict], Optional[str]]:
    """
    Create Google Calendar events for shifts.
    Returns (list of created event dicts with id/summary/start, error_msg or None).
    """
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(tz_str)

        creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                return [], "No valid credentials. Run auth flow first."

        service = build("calendar", "v3", credentials=creds)
        created: List[dict] = []

        for s in shifts:
            base_date = _next_occurrence(s.day, tz)
            sh, sm = _parse_time(s.start)
            eh, em = _parse_time(s.end)

            start_dt = datetime.datetime(
                base_date.year, base_date.month, base_date.day, sh, sm, tzinfo=tz
            )
            end_dt = datetime.datetime(
                base_date.year, base_date.month, base_date.day, eh, em, tzinfo=tz
            )
            if s.overnight:
                end_dt += datetime.timedelta(days=1)

            event = {
                "summary": EVENT_TITLE,
                "location": EVENT_LOCATION,
                "start": {"dateTime": start_dt.isoformat(), "timeZone": tz_str},
                "end": {"dateTime": end_dt.isoformat(), "timeZone": tz_str},
            }
            result = service.events().insert(calendarId="primary", body=event).execute()
            created.append({
                "id": result.get("id"),
                "summary": result.get("summary"),
                "start": result.get("start", {}).get("dateTime"),
            })
            logger.info("Created event: %s", result.get("id"))

        return created, None
    except HttpError as e:
        return [], str(e)
    except Exception as e:
        logger.exception("Calendar create_events failed")
        return [], str(e)


def run_auth_flow(token_saver) -> Optional[str]:
    """
    Run OAuth flow, save token via token_saver(token_json_str).
    Returns token_json on success, None on failure.
    """
    if not CREDENTIALS_PATH.exists():
        logger.error("credentials.json not found at %s", CREDENTIALS_PATH)
        return None

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0)
    token_json = creds.to_json()
    token_saver(token_json)
    return token_json
