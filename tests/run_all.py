"""Run every suite.

    python tests/run_all.py

urlpath_test runs offline with mocked providers and needs nothing. The other
three drive a live server and assert against the --demo seed, so start one
first:

    python backend/server.py --demo

Set QRIP_TEST_BASE to point at a different host.
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("QRIP_TEST_BASE", "http://127.0.0.1:8000")

OFFLINE = ["urlpath_test.py"]
SERVER = ["api_test.py", "caqdas_test.py", "reviews_test.py"]


def run(suite):
    print("\n=== " + suite + " " + "=" * max(2, 60 - len(suite)))
    return subprocess.call([sys.executable, os.path.join(HERE, suite)])


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
    except urllib.error.HTTPError as exc:
        print("\nNo demo account at " + BASE + " (login returned "
              + str(exc.code) + ").")
        print("The server suites need the seed data. Restart with:")
        print("    python backend/server.py --demo")
        return False
    except urllib.error.URLError as exc:
        print("\nNo server responding at " + BASE + ": " + str(exc.reason))
        print("Start one with:  python backend/server.py --demo")
        return False
    return True


def main():
    failed = [suite for suite in OFFLINE if run(suite) != 0]

    if not preflight():
        print("\nSkipped the server suites.")
        return 1 if failed else 2

    for suite in SERVER:
        if run(suite) != 0:
            failed.append(suite)

    print("\n" + "=" * 66)
    if failed:
        print("FAILED: " + ", ".join(failed))
        return 1
    print("all suites passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
