"""Business logic for creating, joining, leaving, editing and cancelling games.

All functions operate on (and return) a pandas DataFrame with the columns
defined in `src.constants.COLUMNS`. Functions that can fail return a
`(DataFrame, error_message | None)` tuple so the UI layer can surface a
friendly message without raising exceptions.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import pandas as pd

from src.constants import (
    ATTENDEE_SEPARATOR,
    ATTENDEES,
    COURT_NAME,
    DURATION,
    GAME_ID,
    HOSTNAME,
    PARTY,
    PIN_CODE,
    START_TIME,
    START_TIME_FORMAT,
    STATUS,
    STATUS_CANCELLED,
    STATUS_FULL,
    STATUS_OPEN,
)


def validate_pin_format(pin: str) -> bool:
    return isinstance(pin, str) and len(pin) == 4 and pin.isdigit()


def _normalize_pin(value) -> str:
    """Normalize a PIN for comparison.

    Google Sheets may coerce a numeric-looking string (e.g. "0007") into a
    number, dropping leading zeros or adding a trailing ".0". This strips
    everything down to digits and re-pads to 4 characters so comparisons
    stay correct regardless of how the sheet stored the value.
    """
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return digits.zfill(4) if digits else ""


def _to_int(value, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def parse_attendees(attendees: str) -> list[str]:
    if not attendees:
        return []
    return [name.strip() for name in str(attendees).split(",") if name.strip()]


def format_attendees(names: list[str]) -> str:
    return ATTENDEE_SEPARATOR.join(names)


def format_start_time(dt: datetime) -> str:
    return dt.strftime(START_TIME_FORMAT)


def _recompute_status(attendee_count: int, party: int, current_status: str) -> str:
    if current_status == STATUS_CANCELLED:
        return STATUS_CANCELLED
    return STATUS_FULL if attendee_count >= party else STATUS_OPEN


def _find_row_index(df: pd.DataFrame, game_id: str) -> int | None:
    matches = df.index[df[GAME_ID] == game_id]
    if len(matches) == 0:
        return None
    return matches[0]


def is_upcoming(start_time: str, now: datetime | None = None) -> bool:
    now = now or datetime.now()
    try:
        return datetime.strptime(start_time, START_TIME_FORMAT) >= now
    except (ValueError, TypeError):
        return True


def create_game(
    df: pd.DataFrame,
    court_name: str,
    start_time: datetime,
    duration: float,
    hostname: str,
    party: int,
    pin_code: str,
) -> tuple[pd.DataFrame, str | None]:
    if not court_name or not hostname:
        return df, "Court name and host name are required."
    if party < 1:
        return df, "Party size must be at least 1."
    if not validate_pin_format(pin_code):
        return df, "PIN must be exactly 4 digits."

    new_row = {
        GAME_ID: uuid.uuid4().hex,
        COURT_NAME: court_name,
        START_TIME: format_start_time(start_time),
        DURATION: duration,
        HOSTNAME: hostname,
        PARTY: party,
        STATUS: _recompute_status(1, party, STATUS_OPEN),
        ATTENDEES: format_attendees([hostname]),
        PIN_CODE: pin_code,
    }
    new_df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    return new_df, None


def join_game(df: pd.DataFrame, game_id: str, name: str) -> tuple[pd.DataFrame, str | None]:
    if not name or not name.strip():
        return df, "Please enter your name."
    name = name.strip()

    idx = _find_row_index(df, game_id)
    if idx is None:
        return df, "Game not found."

    row = df.loc[idx]
    if row[STATUS] == STATUS_CANCELLED:
        return df, "This game has been cancelled."
    if row[STATUS] == STATUS_FULL:
        return df, "This game is already full."

    attendees = parse_attendees(row[ATTENDEES])
    if any(existing.lower() == name.lower() for existing in attendees):
        return df, f"{name} has already joined this game."

    attendees.append(name)
    party = _to_int(row[PARTY], default=1)
    df.loc[idx, ATTENDEES] = format_attendees(attendees)
    df.loc[idx, STATUS] = _recompute_status(len(attendees), party, row[STATUS])
    return df, None


def leave_game(df: pd.DataFrame, game_id: str, name: str) -> tuple[pd.DataFrame, str | None]:
    if not name or not name.strip():
        return df, "Please enter your name."
    name = name.strip()

    idx = _find_row_index(df, game_id)
    if idx is None:
        return df, "Game not found."

    row = df.loc[idx]
    attendees = parse_attendees(row[ATTENDEES])
    remaining = [a for a in attendees if a.lower() != name.lower()]
    if len(remaining) == len(attendees):
        return df, f"{name} is not on the attendee list for this game."

    party = _to_int(row[PARTY], default=1)
    df.loc[idx, ATTENDEES] = format_attendees(remaining)
    df.loc[idx, STATUS] = _recompute_status(len(remaining), party, row[STATUS])
    return df, None


def _verify_pin(df: pd.DataFrame, idx: int, pin_code: str) -> bool:
    return _normalize_pin(df.loc[idx, PIN_CODE]) == _normalize_pin(pin_code)


def edit_game(
    df: pd.DataFrame,
    game_id: str,
    pin_code: str,
    court_name: str,
    start_time: datetime,
    duration: float,
    party: int,
) -> tuple[pd.DataFrame, str | None]:
    idx = _find_row_index(df, game_id)
    if idx is None:
        return df, "Game not found."
    if not _verify_pin(df, idx, pin_code):
        return df, "Incorrect PIN."
    if df.loc[idx, STATUS] == STATUS_CANCELLED:
        return df, "Cannot edit a cancelled game."
    if not court_name:
        return df, "Court name is required."
    if party < 1:
        return df, "Party size must be at least 1."

    attendee_count = len(parse_attendees(df.loc[idx, ATTENDEES]))
    df.loc[idx, COURT_NAME] = court_name
    df.loc[idx, START_TIME] = format_start_time(start_time)
    df.loc[idx, DURATION] = duration
    df.loc[idx, PARTY] = party
    df.loc[idx, STATUS] = _recompute_status(attendee_count, party, df.loc[idx, STATUS])
    return df, None


def cancel_game(df: pd.DataFrame, game_id: str, pin_code: str) -> tuple[pd.DataFrame, str | None]:
    idx = _find_row_index(df, game_id)
    if idx is None:
        return df, "Game not found."
    if not _verify_pin(df, idx, pin_code):
        return df, "Incorrect PIN."

    df.loc[idx, STATUS] = STATUS_CANCELLED
    return df, None
