"""Google Sheets access layer.

Uses the official Streamlit GSheets connection (`st-gsheets-connection`).
All reads/writes operate on the whole worksheet as a pandas DataFrame -
this is a simple read-modify-write pattern, good enough for a small
friend-group app. It is not safe against two people writing at the exact
same moment (last write wins).
"""

from __future__ import annotations

import pandas as pd
import streamlit as st
from gspread.exceptions import WorksheetNotFound
from streamlit_gsheets import GSheetsConnection

from src.constants import COLUMNS, WORKSHEET_NAME


def get_connection() -> GSheetsConnection:
    return st.connection("gsheets", type=GSheetsConnection)


def _empty_games_df() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMNS)


def read_games(ttl: int | str = 0) -> pd.DataFrame:
    """Read all games from the sheet, returning a DataFrame with the fixed columns.

    ttl=0 disables caching so the app always sees the latest data after a write.
    """
    try:
        conn = get_connection()
        df = conn.read(worksheet=WORKSHEET_NAME, ttl=ttl)
    except Exception:
        return _empty_games_df()

    if df is None or df.empty:
        return _empty_games_df()

    df = df.dropna(how="all")
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df = df[COLUMNS].fillna("")
    return df.reset_index(drop=True)


def write_games(df: pd.DataFrame) -> None:
    """Overwrite the whole worksheet with the given DataFrame.

    Creates the worksheet (with header row) on first use if it doesn't exist yet.
    """
    conn = get_connection()
    df = df[COLUMNS]
    try:
        conn.update(worksheet=WORKSHEET_NAME, data=df)
    except WorksheetNotFound:
        conn.create(worksheet=WORKSHEET_NAME, data=df)
