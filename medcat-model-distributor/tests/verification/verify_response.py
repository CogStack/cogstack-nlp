import sys


def main(status: str, model_display: str, body: str):

    errors = []

    # 1. HTTP 200
    if status != "200":
        errors.append(f"Expected HTTP 200, got {status}")

    # 2. Not an API-key rejection JSON
    if '"error"' in body and "API key" in body:
        errors.append("Response looks like an API key rejection (JSON error body returned)")

    # 3. Model display name present in the rendered page
    if model_display not in body:
        errors.append(f"Model display name '{model_display}' not found in page body")

    # 4. No Django error page
    if "Exception Value" in body or "Traceback (most recent call last)" in body:
        errors.append("Django error page / traceback detected in response body")

    # 5. Valid-key message present (from the view context message)
    if "Manually obtained API key is being used" not in body:
        errors.append("Expected validity message ('Manually obtained API key is being used') not in body")

    # ── Report ────────────────────────────────────────────────────────────────────
    if errors:
        print("\n[FAIL] Verification FAILED:")
        for e in errors:
            print(f"  ✗  {e}")
        sys.exit(1)
    else:
        print("\n[PASS] All checks passed:")
        print(f"  ✓  HTTP 200 received")
        print(f"  ✓  No API-key rejection in body")
        print(f"  ✓  Model '{model_display}' listed on page")
        print(f"  ✓  No Django error page")
        print(f"  ✓  Valid-key message present")


if __name__ == "__main__":
    main(*sys.argv[1:])
