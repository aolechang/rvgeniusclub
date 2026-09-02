"""Main booking page: create games, browse open games, manage your own game."""

from __future__ import annotations

from datetime import datetime, time

import streamlit as st

from src import game_service, sheets_client
from src.constants import (
    ATTENDEES,
    COURT_NAME,
    DURATION,
    GAME_ID,
    HOSTNAME,
    PARTY,
    START_TIME,
    START_TIME_FORMAT,
    STATUS,
    STATUS_CANCELLED,
    STATUS_FULL,
    STATUS_OPEN,
)

_STATUS_BADGES = {
    STATUS_OPEN: "🟢 Open",
    STATUS_FULL: "🔴 Full",
    STATUS_CANCELLED: "⚫ Cancelled",
}


def render() -> None:
    st.title("🎾 Tennis Game Booking")
    st.caption(
        "Create a game or join one hosted by a friend. Data is stored in a shared Google Sheet."
    )

    games_df = sheets_client.read_games()

    tab_open, tab_create, tab_manage = st.tabs(
        ["📅 Open Games", "➕ Create a Game", "🔑 Manage My Game"]
    )

    with tab_open:
        _render_open_games(games_df)

    with tab_create:
        _render_create_game(games_df)

    with tab_manage:
        _render_manage_game(games_df)


def _render_open_games(games_df) -> None:
    show_all = st.checkbox("Show past & cancelled games", value=False)

    view_df = games_df.copy()
    if not show_all:
        view_df = view_df[
            view_df[STATUS].isin([STATUS_OPEN, STATUS_FULL])
            & view_df[START_TIME].apply(game_service.is_upcoming)
        ]
    view_df = view_df.sort_values(START_TIME)

    if view_df.empty:
        st.info("No games to show yet. Create one in the 'Create a Game' tab!")
        return

    for _, row in view_df.iterrows():
        attendees = game_service.parse_attendees(row[ATTENDEES])
        badge = _STATUS_BADGES.get(row[STATUS], row[STATUS])
        label = f"{row[COURT_NAME]} — {row[START_TIME]} — {badge}"
        with st.expander(label):
            st.write(f"**Host:** {row[HOSTNAME]}")
            st.write(f"**Duration:** {row[DURATION]} hour(s)")
            st.write(f"**Party size:** {len(attendees)}/{row[PARTY]}")
            st.write(f"**Attendees:** {', '.join(attendees) if attendees else '—'}")

            if row[STATUS] == STATUS_CANCELLED:
                continue

            col_join, col_leave = st.columns(2)
            with col_join:
                with st.form(key=f"join_form_{row[GAME_ID]}"):
                    join_name = st.text_input("Your name", key=f"join_name_{row[GAME_ID]}")
                    submitted = st.form_submit_button(
                        "Join", disabled=row[STATUS] == STATUS_FULL
                    )
                    if submitted:
                        updated_df, error = game_service.join_game(
                            games_df, row[GAME_ID], join_name
                        )
                        if error:
                            st.error(error)
                        else:
                            sheets_client.write_games(updated_df)
                            st.success(f"{join_name} joined!")
                            st.rerun()
            with col_leave:
                with st.form(key=f"leave_form_{row[GAME_ID]}"):
                    leave_name = st.text_input("Your name", key=f"leave_name_{row[GAME_ID]}")
                    if st.form_submit_button("Leave"):
                        updated_df, error = game_service.leave_game(
                            games_df, row[GAME_ID], leave_name
                        )
                        if error:
                            st.error(error)
                        else:
                            sheets_client.write_games(updated_df)
                            st.success(f"{leave_name} left the game.")
                            st.rerun()


def _render_create_game(games_df) -> None:
    st.subheader("Create a new game")
    with st.form("create_game_form"):
        court_name = st.text_input("Court name")
        col_date, col_time = st.columns(2)
        with col_date:
            game_date = st.date_input("Date")
        with col_time:
            game_time = st.time_input("Time", value=time(18, 0))
        duration = st.number_input("Duration (hours)", min_value=0.5, step=0.5, value=1.0)
        hostname = st.text_input("Your name (host)")
        party = st.number_input("Party size (max players)", min_value=1, step=1, value=4)
        col_pin, col_pin_confirm = st.columns(2)
        with col_pin:
            pin = st.text_input("Set a 4-digit PIN", max_chars=4, type="password")
        with col_pin_confirm:
            pin_confirm = st.text_input("Confirm PIN", max_chars=4, type="password")
        st.caption("You'll need this PIN later to edit or cancel this game.")

        if st.form_submit_button("Create game"):
            if pin != pin_confirm:
                st.error("PINs do not match.")
            else:
                start_dt = datetime.combine(game_date, game_time)
                updated_df, error = game_service.create_game(
                    games_df, court_name, start_dt, duration, hostname, int(party), pin
                )
                if error:
                    st.error(error)
                else:
                    sheets_client.write_games(updated_df)
                    st.success("Game created!")
                    st.rerun()


def _render_manage_game(games_df) -> None:
    st.subheader("Manage a game you host")

    editable_df = games_df[games_df[STATUS] != STATUS_CANCELLED]
    if editable_df.empty:
        st.info("No active games to manage.")
        return

    options = {
        f"{row[COURT_NAME]} — {row[START_TIME]} (host: {row[HOSTNAME]})": row[GAME_ID]
        for _, row in editable_df.iterrows()
    }
    selected_label = st.selectbox("Select a game", list(options.keys()))
    game_id = options[selected_label]
    row = games_df[games_df[GAME_ID] == game_id].iloc[0]

    pin_code = st.text_input("Enter the game PIN", max_chars=4, type="password", key="manage_pin")

    with st.form("edit_game_form"):
        st.write("Edit game details")
        court_name = st.text_input("Court name", value=row[COURT_NAME])
        try:
            current_dt = datetime.strptime(row[START_TIME], START_TIME_FORMAT)
        except (ValueError, TypeError):
            current_dt = datetime.now()
        col_date, col_time = st.columns(2)
        with col_date:
            game_date = st.date_input("Date", value=current_dt.date())
        with col_time:
            game_time = st.time_input("Time", value=current_dt.time())
        duration = st.number_input(
            "Duration (hours)",
            min_value=0.5,
            step=0.5,
            value=float(row[DURATION]) if row[DURATION] else 1.0,
        )
        party = st.number_input(
            "Party size (max players)",
            min_value=1,
            step=1,
            value=int(float(row[PARTY])) if row[PARTY] else 4,
        )

        if st.form_submit_button("Save changes"):
            start_dt = datetime.combine(game_date, game_time)
            updated_df, error = game_service.edit_game(
                games_df, game_id, pin_code, court_name, start_dt, duration, int(party)
            )
            if error:
                st.error(error)
            else:
                sheets_client.write_games(updated_df)
                st.success("Game updated!")
                st.rerun()

    if st.button("Cancel this game"):
        updated_df, error = game_service.cancel_game(games_df, game_id, pin_code)
        if error:
            st.error(error)
        else:
            sheets_client.write_games(updated_df)
            st.success("Game cancelled.")
            st.rerun()
