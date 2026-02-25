#!/usr/bin/env python3
"""
verify_integration.py
─────────────────────
Called by integration_test.sh.  Hits auth-callback-api with a valid API key
and asserts that:
  1. The response is HTTP 200.
  2. The page does NOT contain an error / unauthorised message.
  3. The model display name appears somewhere in the rendered HTML.

Usage (standalone):
  python3 verify_integration.py \
      --base-url http://localhost:8000 \
      --api-key  <key> \
      --model-name "Integration Test Model"
"""
import argparse
import sys
import urllib.request
import urllib.error
import urllib.parse


# ── ANSI colours ──────────────────────────────────────────────────────────────
RED   = "\033[0;31m"
GREEN = "\033[0;32m"
RESET = "\033[0m"

def ok(msg: str)   -> None: print(f"{GREEN}  ✓ {msg}{RESET}")
def err(msg: str)  -> None: print(f"{RED}  ✗ {msg}{RESET}", file=sys.stderr)


# ── assertions ────────────────────────────────────────────────────────────────
class AssertionFailed(Exception):
    pass


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionFailed(message)


def run_checks(base_url: str, api_key: str, model_name: str) -> None:
    url = f"{base_url.rstrip('/')}/auth-callback-api/"

    # ── 1. Call with key in query string ──────────────────────────────────────
    # NOTE: The "API key" used here is a test time one that has no value
    #       outside this test. It is generated for the purposes of the test
    quoted_api_key = urllib.parse.quote(api_key)
    api_key_descr = (
        f"Redacted Api key of length {len(quoted_api_key)} "
        f"with hash {hash(quoted_api_key)}")
    full_url = f"{url}?api_key={quoted_api_key}"
    redacted_url = full_url.replace(quoted_api_key, f'<{api_key_descr}>')
    print(f"  GET {redacted_url}")

    try:
        req = urllib.request.Request(full_url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            status  = resp.status
            body    = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise AssertionFailed(
            f"HTTP {exc.code} from {full_url}. "
            "Expected 200 – check that the API key was seeded correctly."
        )
    except urllib.error.URLError as exc:
        raise AssertionFailed(f"Could not reach {full_url}: {exc.reason}")

    # ── 2. Status code ────────────────────────────────────────────────────────
    assert_true(status == 200, f"Expected HTTP 200, got {status}")
    ok(f"HTTP 200 received")

    # ── 3. No auth-error markers in the body ──────────────────────────────────
    error_markers = [
        "API key required",
        "Invalid or expired API key",
        '"error":',          # JSON error response accidentally rendered
    ]
    for marker in error_markers:
        assert_true(
            marker not in body,
            f"Response body contains error marker: {marker!r}"
        )
    ok("No error markers in page body")

    # ── 4. Model display name present in the page ─────────────────────────────
    assert_true(
        model_name in body,
        f"Model name {model_name!r} not found in page body. "
        "Was the MedcatModel seeded successfully?"
    )
    ok(f"Model name {model_name!r} found in page body")

    # ── 5. Repeat with header-based auth (belt-and-braces) ────────────────────
    req_header = urllib.request.Request(url, headers={"X-API-Key": api_key})
    try:
        with urllib.request.urlopen(req_header, timeout=15) as resp:
            header_status = resp.status
            header_body   = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raise AssertionFailed(
            f"Header-based auth returned HTTP {exc.code}. Expected 200."
        )

    assert_true(header_status == 200, f"Header auth: expected 200, got {header_status}")
    assert_true(
        model_name in header_body,
        f"Header auth: model name {model_name!r} not found in page body"
    )
    ok("Header-based auth (X-API-Key) also works")


# ── entrypoint ────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Integration test verifier")
    parser.add_argument("--base-url",   required=True, help="App base URL, e.g. http://localhost:8000")
    parser.add_argument("--api-key",    required=True, help="The API key that was seeded into the DB")
    parser.add_argument("--model-name", required=True, help="MedcatModel.model_display_name to look for")
    args = parser.parse_args()

    print(f"\nVerifying auth-callback-api at {args.base_url} …\n")
    try:
        run_checks(args.base_url, args.api_key, args.model_name)
    except AssertionFailed as exc:
        err(f"ASSERTION FAILED: {exc}")
        sys.exit(1)

    print()  # trailing blank line for readability


if __name__ == "__main__":
    main()