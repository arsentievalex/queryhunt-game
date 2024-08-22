import streamlit as st
from utils.utils import get_connection
import pandas as pd

st.title("Leaderboard 🏆")

query = "SELECT username, date, time_sec FROM leaderboard ORDER BY time_sec ASC LIMIT 10;"

@st.cache_data
def get_leaderboard(query):
    with get_connection(autocommit=True, database="original_game_schema") as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)
            data = cursor.fetchall()

            column_names = [desc[0] for desc in cursor.description]
            df = pd.DataFrame(data, columns=column_names)

            return df


df = get_leaderboard(query)

# change column names for better readability, capitalize, remove underscores
df.columns = df.columns.str.replace('_', ' ').str.capitalize()

# change time_sec to Time (in seconds)
df.rename(columns={'Time sec': 'Time (in seconds)'}, inplace=True)

# add rank column
df.insert(0, 'Rank', range(1, 1 + len(df)))

# display the result as df
st.dataframe(df, hide_index=True, width=600)

