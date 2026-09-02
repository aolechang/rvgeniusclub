"""Shared constants for the tennis game booking app."""

from __future__ import annotations

WORKSHEET_NAME = "Games"

GAME_ID = "game_id"
COURT_NAME = "court_name"
START_TIME = "start_time"
DURATION = "duration"
HOSTNAME = "hostname"
PARTY = "party"
STATUS = "status"
ATTENDEES = "attendees"
PIN_CODE = "pin_code"

COLUMNS = [
    GAME_ID,
    COURT_NAME,
    START_TIME,
    DURATION,
    HOSTNAME,
    PARTY,
    STATUS,
    ATTENDEES,
    PIN_CODE,
]

STATUS_OPEN = "Open"
STATUS_FULL = "Full"
STATUS_CANCELLED = "Cancelled"

ATTENDEE_SEPARATOR = ", "

# Datetime format used to store start_time as a plain string in the sheet.
START_TIME_FORMAT = "%Y-%m-%d %H:%M"
