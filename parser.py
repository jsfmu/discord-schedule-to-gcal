import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import List, Optional, Tuple

DAY_MAP = {
    "mon": "MO", "monday": "MO",
    "tue": "TU", "tues": "TU", "tuesday": "TU",
    "wed": "WE", "weds": "WE", "wednesday": "WE",
    "thu": "TH", "thur": "TH", "thurs": "TH", "thursday": "TH",
    "fri": "FR", "friday": "FR",
    "sat": "SA", "saturday": "SA",
    "sun": "SU", "sunday": "SU",
}

@dataclass
class Shift:
    day: str           # "MO", "TU", ...
    start: str         # "16:00"
    end: str           # "21:00"
    overnight: bool = False  # True if end < start (spans to next day)

_time_re = re.compile(
    r"(?P<day>mon|monday|tue|tues|tuesday|wed|weds|wednesday|thu|thur|thurs|thursday|fri|friday|sat|saturday|sun|sunday)\s*"
    r"(?P<start>\d{1,2})(?::(?P<start_min>\d{2}))?\s*(?P<start_ampm>a|am|p|pm)?\s*"
    r"[-–to]+\s*"
    r"(?P<end>\d{1,2})(?::(?P<end_min>\d{2}))?\s*(?P<end_ampm>a|am|p|pm)?",
    re.IGNORECASE
)

def _to_24h(hour: int, minute: int, ampm: Optional[str]) -> str:
    # If ampm missing, treat as "unknown" heuristic later; for now assume PM for 1-11, AM for 12
    if not ampm:
        if hour == 12:
            ampm = "pm"
        else:
            ampm = "pm"
    ampm = ampm.lower()
    if ampm in ("a", "am"):
        if hour == 12:
            hour = 0
    else:
        if hour != 12:
            hour += 12
    return f"{hour:02d}:{minute:02d}"

def parse_shifts(text: str) -> Tuple[List[Shift], List[str]]:
    """
    Input example: 'Mon 4-9, Wed 5-10pm, Sat 12-6'
    Returns (shifts, warnings)
    """
    shifts: List[Shift] = []
    warnings: List[str] = []

    for m in _time_re.finditer(text):
        day_raw = m.group("day").lower()
        day = DAY_MAP.get(day_raw)
        if not day:
            warnings.append(f"Unknown day: {day_raw}")
            continue

        sh = int(m.group("start"))
        sm = int(m.group("start_min") or 0)
        eh = int(m.group("end"))
        em = int(m.group("end_min") or 0)

        start_ampm = m.group("start_ampm")
        end_ampm = m.group("end_ampm")

        start_24 = _to_24h(sh, sm, start_ampm)
        end_24 = _to_24h(eh, em, end_ampm)

        # warn if AM/PM missing
        if not start_ampm or not end_ampm:
            warnings.append(f"{day_raw.title()} missing AM/PM; assumed PM.")

        # Overnight: end < start means end is next day
        sh_h, sm = map(int, start_24.split(":"))
        eh_h, em = map(int, end_24.split(":"))
        overnight = (eh_h < sh_h) or (eh_h == sh_h and em < sm)

        shifts.append(Shift(day=day, start=start_24, end=end_24, overnight=overnight))

    if not shifts:
        warnings.append("No shifts found. Use format like: 'Mon 4-9, Wed 5-10pm'")
    return shifts, warnings


def shifts_hash(shifts: List[Shift]) -> str:
    """Canonical hash for deduplication."""
    canonical = json.dumps([asdict(s) for s in shifts], sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()