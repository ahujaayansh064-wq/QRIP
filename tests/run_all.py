"""Run every suite against a running server.

    python backend/server.py --demo      # in one terminal
    python tests/run_all.py              # in another

Set QRIP_TEST_BASE to point at a different host.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SUITES = ["api_test.py", "caqdas_test.py", "reviews_test.py"]


def main():
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
