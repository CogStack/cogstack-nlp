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

soup = BeautifulSoup(resp.text, "html.parser")

annotations = soup.select("div.entities mark.entity")
assert annotations, "No annotations found in the response"
assert any(disease in mark.text.lower() for mark in annotations), (
    f"Disease '{disease}' not found in annotations")

assert disease in resp.text
