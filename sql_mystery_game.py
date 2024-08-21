import streamlit as st
from pymysql import Connection
from pymysql.cursors import DictCursor
import pymysql
from streamlit_ace import st_ace
from utils import get_connection, get_vs_store, is_valid_query, get_query_engine
import pandas as pd
from workflow import run_workflow
import asyncio
from llama_index.core.vector_stores.types import (
    MetadataFilter,
    MetadataFilters,
)
from llama_index.llms.openai import OpenAI
import time
from datetime import datetime
import streamlit.components.v1 as components
import random


@st.cache_resource
def get_db_session():
    return get_connection()

@st.fragment
def show_hint(hint_prompt):
    hint_button = st.button('Get Hint 🪄')

    if hint_button:
        query_engine = get_query_engine()
        response = query_engine.query(hint_prompt.format(story=st.session_state.ai_story,
                                                         queries=st.session_state.user_queries,
                                                         hints=st.session_state.ai_hints))

        hint_chunks = []

        # stream the response to the frontend
        for chunk in st.write_stream(response.response_gen):
            hint_chunks.append(chunk)

        # add to session state
        full_hint = ''.join(hint_chunks)
        st.session_state['ai_hints'].append(full_hint)


@st.fragment
def check_solution():
    user_solution = st.text_input("Who's the murderer?", label_visibility='collapsed',
                                  placeholder="Who's the murderer? Insert full name")
    if user_solution:

        # add to session state
        st.session_state.user_solutions.append(user_solution)

        # get correct solution
        with get_connection(autocommit=True) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT name from Murderer;")
                data = cursor.fetchall()
                solution = data[0]['name']

        # compare correct solution with user solution
        if user_solution.strip() == solution.strip():
            # record end time
            st.session_state.end_time = time.time()
            st.session_state.elapsed_time = st.session_state.end_time - st.session_state.start_time

            st.balloons()

            # show dialog window
            game_over()
        else:
            st.warning("Not exactly...try again!")


@st.fragment
def sql_editor():
    sql_query = st_ace(
        placeholder="Your SQL query here...",
        language="sql",
        theme="tomorrow_night",
        keybinding="vscode",
        font_size=15,
        show_gutter=False,
        show_print_margin=False,
        wrap=False,
        auto_update=False,
        min_lines=10,
        key="ace",
    )

    if sql_query:
        if not is_valid_query(sql_query):
            st.error("Wrong query syntax or non-Select statement. Please provide a valid SQL query.")
        else:
            try:
                with get_connection(autocommit=True) as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(sql_query)
                        data = cursor.fetchall()

                        column_names = [desc[0] for desc in cursor.description]
                        df = pd.DataFrame(data, columns=column_names)

                        # display the result as df
                        st.dataframe(df, hide_index=True)
            except pymysql.Error as e:
                st.error(e)


@st.dialog("Woo hoo!")
def game_over():

    minutes = int(st.session_state.elapsed_time // 60)
    seconds = int(st.session_state.elapsed_time % 60)

    st.markdown(f"""
        Great job! You correctly identified the murderer and solved the QueryHunt game in 
        <span style="color:#4CAF50; font-weight:bold;">{minutes}:{seconds:02d}</span> min!
    """, unsafe_allow_html=True)

    components.html(
        f"""<a class="twitter-share-button" href="https://twitter.com/intent/tweet" data-text="I solved the QueryHunt game in {minutes}:{seconds:02d} min. What is your time? 🧐"  data-url="yourmist.streamlit.app" data-hashtags="SQLMurderMystery">
    <script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script></a>
    """, width=100, height=30)

    # append result to TiDB table
    add_to_leaderboard()


def generate_username():
    random_number = random.randint(100000, 999999)
    username = f"user_{random_number}"

    if st.session_state.current_user is None:
        st.session_state.current_user = username


def add_to_leaderboard():
    # Get today's date
    today_date = datetime.today().strftime('%Y-%m-%d')

    query = """
    INSERT INTO Leaderboard (username, date, time_sec) 
    VALUES (%s, %s, %s);
    """

    values = (st.session_state.current_user, today_date, int(st.session_state.elapsed_time))

    with get_connection(autocommit=True) as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, values)


HINT_PROMPT = """
You're an assistant helping a user with SQL murder mystery game.
Your goal is to provide a useful hint to a user and point them in the right direction towards identifying the correct murderer in the game.
Use your knowledge of dbml game schema.
Do not reveal the murderer.
Keep the hint short.

In your hint, reference the game story:
---------------------
{story}
---------------------
Here are the user's SQL queries so far:
---------------------
{queries}
---------------------
Here are your previous hints:
---------------------
{hints}
---------------------
"""


# wide layout
# st.set_page_config(layout="wide", initial_sidebar_state='collapsed')

# initiate session state dicts
if "user_queries" not in st.session_state:
    st.session_state.user_queries = []
if "ai_hints" not in st.session_state:
    st.session_state.ai_hints = []
if "ai_story" not in st.session_state:
    st.session_state.ai_story = None
if "user_solutions" not in st.session_state:
    st.session_state.user_solutions = []
if "start_time" not in st.session_state:
    st.session_state.start_time = None
if "end_time" not in st.session_state:
    st.session_state.end_time = None
if "elapsed_time" not in st.session_state:
    st.session_state.elapsed_time = None
if "current_user" not in st.session_state:
    st.session_state.current_user = None


st.title("SQL Murder Mystery Game")

# generate random username and add to session state
generate_username()

col1, col2 = st.columns(2)

with col1:
    if st.button("Generate Story"):
        result = asyncio.run(run_workflow())

        # add to session state
        st.session_state.ai_story = result['story']
        st.session_state.start_time = time.time()

with col2:
    with st.expander('See Schema'):
        st.image('schema.svg')

    sql_editor()

    col3, col4 = st.columns(2)

    with col3:
        check_solution()

    with col4:
        show_hint(hint_prompt=HINT_PROMPT)






