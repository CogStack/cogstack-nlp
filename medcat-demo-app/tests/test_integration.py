# tests/test_integration.py

import requests

from bs4 import BeautifulSoup

URL = "http://localhost:8000/"
session = requests.Session()

# GET the page to get the CSRF token
resp = session.get(URL)
soup = BeautifulSoup(resp.text, "html.parser")
csrf = soup.find("input", {"name": "csrfmiddlewaretoken"}).get("value")

disease = "kidney failure"

text = f"Patient had been diagnosed with acute {disease} the week before"

# POST with the token and same session (cookies preserved)
resp = session.post(URL, data={
    "text": text,
    "csrfmiddlewaretoken": csrf})

print(f"RESPOONSE:\n{resp.text}")

assert disease in resp.text
