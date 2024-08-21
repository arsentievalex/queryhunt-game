import sqlparse
from pymysql import Connection
from pymysql.cursors import DictCursor
import pymysql
import re
from llama_index.core import VectorStoreIndex
from llama_index.llms.openai import OpenAI
from llama_index.vector_stores.tidbvector import TiDBVectorStore
from llama_index.core.vector_stores.types import (
    MetadataFilter,
    MetadataFilters,
)
from sqlglot import parse_one, errors
import streamlit as st


def get_connection(autocommit: bool = True) -> Connection:
    """
    Function that returns connection object to TiDB Serverless cluster.
    :param: autocommit
    :return: pymysql connection
    """
    db_conf = {
        "host": "gateway01.eu-central-1.prod.aws.tidbcloud.com",
        "port": 4000,
        "user": st.secrets['TIDB_USER'],
        "password": st.secrets['TIDB_PASSWORD'],
        "database": "original_game_schema",
        "autocommit": autocommit,
        "cursorclass": DictCursor,
    }

    db_conf["ssl_verify_cert"] = True
    db_conf["ssl_verify_identity"] = True
    db_conf["ssl_ca"] = "/etc/ssl/certs/ca-certificates.crt"

    return pymysql.connect(**db_conf)


def reset_tables():
    """
    Function to delete all data from the game tables.
    """
    delete_queries = [
        "DELETE FROM Evidence;",
        "DELETE FROM Murderer;",
        "DELETE FROM Alibis;",
        "DELETE FROM CrimeScene;",
        "DELETE FROM Suspects;",
        "DELETE FROM Victim;"
    ]

    with get_connection(autocommit=True) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SET SESSION tidb_multi_statement_mode='ON';")
            for query in delete_queries:
                cursor.execute(query)


def is_valid_query(query):
    """
    Checks if the SQL query is a valid SELECT statement.
    :param: query (str): The SQL query to check.
    :return: boolean
    """
    parsed = sqlparse.parse(query)

    # Check if there's only one statement
    if len(parsed) != 1:
        return False

    # Get the first token of the statement
    first_token = parsed[0].tokens[0]

    # Check if the first token is a DML keyword and it's SELECT
    if first_token.ttype == sqlparse.tokens.DML and first_token.value.upper() == 'SELECT':
        return True
    else:
        return False


# Function to check if the SQL query is destructive
def is_non_destructive(sql_query: str) -> bool:
    """
    Check if the SQL query is non-destructive (i.e., does not contain DROP, DELETE, or TRUNCATE commands).
    :param: sql_query
    :return: boolean
    """
    destructive_keywords = ['DROP', 'DELETE', 'TRUNCATE']
    for keyword in destructive_keywords:
        # Check if the keyword exists in the query, ignoring case
        if re.search(rf'\b{keyword}\b', sql_query, re.IGNORECASE):
            print(f"Destructive query detected: {keyword} command found.")
            return False
    return True


# Function to validate SQL syntax using sqlglot
def is_valid_sql(sql_query: str) -> bool:
    """
    Check if the SQL query is valid using sqlglot.
    :param sql_query:
    :return: boolean
    """
    try:
        parse_one(sql_query)
        return True
    except errors.ParseError as e:
        print(f"Invalid SQL: {e}")
        return False


def clean_string(input_string: str) -> str:
    """
    Clean the input string by removing unnecessary characters.
    :param input_string:
    :return: cleaned string
    """

    cleaned_string = input_string.replace('```json', '')
    cleaned_string = cleaned_string.replace("\\'", "")
    cleaned_string = cleaned_string.replace('\n', '')
    cleaned_string = cleaned_string.strip()

    return cleaned_string


def get_vs_store():
    """
    Get the vector store index from TiDB Vector Store.
    :return: VectorStoreIndex
    """
    vs_table_name = "vs_game_schema"
    tidbvec = TiDBVectorStore(
        connection_string=st.secrets["TIDB_CONNECTION_URL"],
        table_name=vs_table_name,
        distance_strategy="cosine",
        vector_dimension=1536,
        drop_existing_table=False,
    )
    return VectorStoreIndex.from_vector_store(vector_store=tidbvec)


def get_query_engine():

    llm = OpenAI("gpt-4o-mini", temperature=1)
    # Create the query engine using the loaded index
    vs_store = get_vs_store()

    query_engine = vs_store.as_query_engine(llm=llm, streaming=True, filters=MetadataFilters(
        filters=[MetadataFilter(key="schema", value="sql_mystery_game",
                                operator="==")]))
    return query_engine

