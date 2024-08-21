import streamlit as st
from streamlit.components.v1 import html

# read text from index.txt
with open('index.html', 'r') as file:
    html_content = file.read()

html(html_content, height=600)


