"""Run every suite against a running server.

    python backend/server.py --demo      # in one terminal
    python tests/run_all.py              # in another

The suites assert against the --demo seed (the demo account and the referral
project), so the server must have been started with that flag. Set
QRIP_TEST_BASE to point at a different host.
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("QRIP_TEST_BASE", "http://127.0.0.1:8000")

HERE = os.path.dirname(os.path.abspath(__file__))
SUITES = ["api_test.py", "caqdas_test.py", "reviews_test.py"]


def preflight():
    """Fail loudly if the server is missing or was started without --demo."""
    try:
        request = urllib.request.Request(
            BASE + "/api/auth/login",
            data=json.dumps({"email": "demo@qrip.local",
                             "password": "demo-password"}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=10) as response:
            json.loads(response.read())
    except urllib.error.URLError as exc:
        if isinstance(exc, urllib.error.HTTPError):
            print("No demo account at " + BASE + " (login returned "
                  + str(exc.code) + ").")
            print("The suites need the seed data. Restart the server with:")
            print("    python backend/server.py --demo")
        else:
            print("No server responding at " + BASE + ": " + str(exc.reason))
            print("Start one with:  python backend/server.py --demo")
        return False
    return True


def main():
    if not preflight():
        return 2
    failed = []
    for suite in SUITES:
        print("\n=== " + suite + " " + "=" * (60 - len(suite)))
        code = subprocess.call([sys.executable, os.path.join(HERE, suite)])
        if code != 0:
            failed.append(suite)
    print("\n" + "=" * 66)
    if failed:
        print("FAILED: " + ", ".join(failed))
        return 1
    print("all suites passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
