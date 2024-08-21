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
import random


def get_connection(database: str = None, autocommit: bool = True) -> Connection:
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
        "autocommit": autocommit,
        "cursorclass": DictCursor,
    }

    if database:
        db_conf["database"] = database

    db_conf["ssl_verify_cert"] = True
    db_conf["ssl_verify_identity"] = True
    db_conf["ssl_ca"] = "/etc/ssl/certs/ca-certificates.crt"

    return pymysql.connect(**db_conf)


def run_queries_in_schema(schema_name: str, query_list: list):
    """
    Function to execute queries within a specific schema in TiDB cluster.
    :param schema_name: Name of the schema to use
    :param query_list: List of SQL queries to execute
    """
    with get_connection(database=schema_name) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SET SESSION tidb_multi_statement_mode='ON';")
            for query in query_list:
                cursor.execute(query)


def is_valid_query(query: str) -> bool:
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


def create_schema_and_tables(schema_name: str):
    """
    Function to create a schema and tables in TiDB cluster.
    :param schema_name: Name of the schema to create
    """
    create_table_victim = f"""
    CREATE TABLE Victim (
        victim_id INT NOT NULL,
        name VARCHAR(100),
        age INT,
        occupation VARCHAR(100),
        time_of_death DATETIME,
        location_of_death VARCHAR(100),
        PRIMARY KEY (victim_id)
    );
    """

    create_table_suspects = f"""
    CREATE TABLE Suspects (
        suspect_id INT NOT NULL,
        name VARCHAR(100),
        age INT,
        relationship_to_victim VARCHAR(100),
        motive VARCHAR(100),
        PRIMARY KEY (suspect_id)
    );
    """

    create_table_alibis = f"""
    CREATE TABLE Alibis (
        alibi_id INT NOT NULL,
        suspect_id INT,
        alibi VARCHAR(255),
        alibi_verified BOOLEAN,
        alibi_time DATETIME,
        PRIMARY KEY (alibi_id),
        FOREIGN KEY (suspect_id) REFERENCES Suspects(suspect_id)
    );
    """

    create_table_crime_scene = f"""
    CREATE TABLE CrimeScene (
        scene_id INT NOT NULL,
        location VARCHAR(100),
        description TEXT,
        evidence_found BOOLEAN,
        victim_id INT,
        PRIMARY KEY (scene_id),
        FOREIGN KEY (victim_id) REFERENCES Victim(victim_id)
    );
    """

    create_table_evidence = f"""
    CREATE TABLE Evidence (
        evidence_id INT NOT NULL,
        description TEXT,
        found_at_location VARCHAR(100),
        points_to_suspect_id INT,
        scene_id INT,
        PRIMARY KEY (evidence_id),
        FOREIGN KEY (points_to_suspect_id) REFERENCES Suspects(suspect_id),
        FOREIGN KEY (scene_id) REFERENCES CrimeScene(scene_id)
    );
    """

    create_table_murderer = f"""
    CREATE TABLE Murderer (
        murderer_id INT NOT NULL,
        suspect_id INT,
        name VARCHAR(100),
        PRIMARY KEY (murderer_id),
        FOREIGN KEY (suspect_id) REFERENCES Suspects(suspect_id)
    );
    """

    table_queries = [
        create_table_victim,
        create_table_suspects,
        create_table_alibis,
        create_table_crime_scene,
        create_table_evidence,
        create_table_murderer
    ]

    # Step 1: Connect without specifying a database to create the schema
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE SCHEMA {schema_name};")

    # Step 2: Reconnect with the newly created schema
    with get_connection(database=schema_name) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SET SESSION tidb_multi_statement_mode='ON';")
            for query in table_queries:
                cursor.execute(query)


def generate_username() -> str:
    """
    Function to generate random username for leaderboard.
    :return: username str
    """
    adjectives = [
        "Wacky", "Silly", "Cheerful", "Quirky", "Funky", "Zany", "Bubbly",
        "Gigantic", "Mischievous", "Goofy", "Bouncy", "Sneaky", "Jolly"
    ]

    animals = [
        "Panda", "Kangaroo", "Penguin", "Platypus", "Llama", "Elephant",
        "Giraffe", "Dolphin", "Sloth", "Otter", "Chameleon", "Hedgehog", "Moose"
    ]

    # Generate a random username by combining an adjective, an animal, and a random number
    adjective = random.choice(adjectives)
    animal = random.choice(animals)
    number = random.randint(1000, 9999)

    # Combine them into a username
    username = f"{adjective}{animal}{number}"

    return username

