import streamlit as st

from src.pages import booking, placeholder

st.set_page_config(page_title="RV Genius Club - Tennis Games", page_icon="🎾")

pg = st.navigation(
    [
        st.Page(booking.render, title="Book a Game", icon="🎾", url_path="book-a-game", default=True),
        st.Page(placeholder.render, title="More", icon="🔧", url_path="more"),
    ]
)
pg.run()
