#!/usr/bin/env python3
"""
Smoke-test script for the OT-2 REST wrapper.

Usage:
    # Server must be running already, e.g.:
    #   uvicorn app.main:app --host 0.0.0.0 --port 8000

    # Test health only (no robot needed):
    python test_server.py

    # Full integration test against a live OT-2:
    python test_server.py --full --host 192.168.0.61

    # Custom server URL:
    python test_server.py --base-url http://10.0.0.5:8000
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import requests

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
SKIP = "\033[93mSKIP\033[0m"

passed = 0
failed = 0
skipped = 0


def check(label: str, response: requests.Response, expected_status: int = 200) -> Any:
    """Assert status code, print result, return parsed JSON."""
    global passed, failed
    ok = response.status_code == expected_status
    tag = PASS if ok else FAIL
    print(f"  [{tag}] {label}  (HTTP {response.status_code})")
    if ok:
        passed += 1
    else:
        failed += 1
        print(f"         Expected {expected_status}, body: {response.text[:300]}")
    try:
        return response.json()
    except Exception:
        return None


def skip(label: str, reason: str = "") -> None:
    global skipped
    skipped += 1
    extra = f" — {reason}" if reason else ""
    print(f"  [{SKIP}] {label}{extra}")


# ---------------------------------------------------------------------------
# Test groups
# ---------------------------------------------------------------------------

def test_health(base: str) -> bool:
    print("\n=== Health ===")
    r = requests.get(f"{base}/health")
    data = check("GET /health", r)
    return data is not None and data.get("status") == "ok"


def test_status_disconnected(base: str):
    print("\n=== Robot status (before connect) ===")
    r = requests.get(f"{base}/robot/status")
    data = check("GET /robot/status", r)
    if data:
        assert data["connected"] is False, "Expected connected=false"


def test_deck_requires_connection(base: str):
    print("\n=== Deck guard (no connection) ===")
    r = requests.get(f"{base}/deck")
    check("GET /deck → 503", r, expected_status=503)


def test_connect(base: str, host: str):
    print("\n=== Connect ===")
    r = requests.post(f"{base}/robot/connect", json={"host": host})
    data = check("POST /robot/connect", r)
    if data:
        assert data.get("status") == "connected"

    r = requests.get(f"{base}/robot/status")
    data = check("GET /robot/status (after connect)", r)
    if data:
        assert data["connected"] is True


def test_double_connect(base: str, host: str):
    print("\n=== Double connect guard ===")
    r = requests.post(f"{base}/robot/connect", json={"host": host})
    check("POST /robot/connect again → 400", r, expected_status=400)


def test_home(base: str):
    print("\n=== Home ===")
    r = requests.post(f"{base}/robot/home")
    data = check("POST /robot/home", r)
    if data:
        assert data.get("status") == "homed"


def test_deck_empty(base: str):
    print("\n=== Deck (empty) ===")
    r = requests.get(f"{base}/deck")
    data = check("GET /deck", r)
    if data:
        assert isinstance(data, list) and len(data) == 12


def test_assign_tip_rack(base: str, slot: int = 9):
    print("\n=== Assign tip rack ===")
    r = requests.post(f"{base}/deck/slots/{slot}/tip-rack", json={
        "ot_name": "opentrons_96_filtertiprack_200ul",
        "name": "test_tips",
    })
    data = check(f"POST /deck/slots/{slot}/tip-rack", r)
    if data:
        assert data.get("status") == "ok"
    return "test_tips"


def test_assign_plate(base: str, slot: int = 6):
    print("\n=== Assign plate ===")
    r = requests.post(f"{base}/deck/slots/{slot}/plate", json={
        "resource_type": "agilent_96_wellplate_150uL_Vb",
        "name": "test_plate",
    })
    data = check(f"POST /deck/slots/{slot}/plate", r)
    if data:
        assert data.get("status") == "ok"
    return "test_plate"


def test_assign_tube_rack(base: str, slot: int = 4):
    print("\n=== Assign tube rack ===")
    r = requests.post(f"{base}/deck/slots/{slot}/tube-rack", json={
        "ot_name": "opentrons_24_aluminumblock_nest_1.5ml_snapcap",
        "name": "test_tubes",
    })
    data = check(f"POST /deck/slots/{slot}/tube-rack", r)
    if data:
        assert data.get("status") == "ok"
    return "test_tubes"


def test_deck_populated(base: str):
    print("\n=== Deck (populated) ===")
    r = requests.get(f"{base}/deck")
    data = check("GET /deck", r)
    if data:
        occupied = [s for s in data if s.get("resource_name")]
        print(f"         {len(occupied)} slot(s) occupied")


def test_slot_validation(base: str):
    print("\n=== Slot validation ===")
    r = requests.post(f"{base}/deck/slots/0/tip-rack", json={
        "ot_name": "opentrons_96_filtertiprack_20ul",
        "name": "bad",
    })
    check("POST /deck/slots/0/tip-rack → 400", r, expected_status=400)

    r = requests.post(f"{base}/deck/slots/13/tip-rack", json={
        "ot_name": "opentrons_96_filtertiprack_20ul",
        "name": "bad",
    })
    check("POST /deck/slots/13/tip-rack → 400", r, expected_status=400)


def test_pick_up_tips(base: str, tip_rack: str):
    print("\n=== Pick up tips ===")
    r = requests.post(f"{base}/commands/pick-up-tips", json={
        "resource_name": tip_rack,
        "well_indices": [0],
    })
    check("POST /commands/pick-up-tips", r)


def test_aspirate(base: str, plate: str):
    print("\n=== Aspirate ===")
    r = requests.post(f"{base}/commands/aspirate", json={
        "resource_name": plate,
        "well_indices": [0],
        "volumes": [10.0],
    })
    check("POST /commands/aspirate", r)


def test_dispense(base: str, plate: str):
    print("\n=== Dispense ===")
    r = requests.post(f"{base}/commands/dispense", json={
        "resource_name": plate,
        "well_indices": [1],
        "volumes": [10.0],
    })
    check("POST /commands/dispense", r)


def test_return_tips(base: str):
    print("\n=== Return tips ===")
    r = requests.post(f"{base}/commands/return-tips", json={})
    check("POST /commands/return-tips", r)


def test_drop_tips_trash(base: str, tip_rack: str):
    """Pick up tips again, then drop to trash."""
    print("\n=== Drop tips to trash ===")
    requests.post(f"{base}/commands/pick-up-tips", json={
        "resource_name": tip_rack,
        "well_indices": [1],
    })
    r = requests.post(f"{base}/commands/drop-tips", json={})
    check("POST /commands/drop-tips (trash)", r)


def test_remove_slot(base: str, slot: int):
    print("\n=== Remove slot ===")
    r = requests.delete(f"{base}/deck/slots/{slot}")
    check(f"DELETE /deck/slots/{slot}", r)


def test_remove_empty_slot(base: str):
    print("\n=== Remove empty slot ===")
    r = requests.delete(f"{base}/deck/slots/1")
    check("DELETE /deck/slots/1 → 400", r, expected_status=400)


def test_disconnect(base: str):
    print("\n=== Disconnect ===")
    r = requests.post(f"{base}/robot/disconnect")
    data = check("POST /robot/disconnect", r)
    if data:
        assert data.get("status") == "disconnected"

    r = requests.get(f"{base}/robot/status")
    data = check("GET /robot/status (after disconnect)", r)
    if data:
        assert data["connected"] is False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="OT-2 wrapper smoke tests")
    parser.add_argument("--base-url", default="http://localhost:8000",
                        help="Server base URL (default: http://localhost:8000)")
    parser.add_argument("--full", action="store_true",
                        help="Run full integration tests (requires a live OT-2)")
    parser.add_argument("--host", default="localhost",
                        help="OT-2 IP/hostname for --full mode (default: localhost)")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    print(f"Testing server at {base}")

    # ---- always run ----
    if not test_health(base):
        print("\nServer is not reachable. Is it running?")
        sys.exit(1)

    test_status_disconnected(base)
    test_deck_requires_connection(base)

    if not args.full:
        skip_msg = "use --full to run integration tests against a live robot"
        print()
        for label in [
            "Connect", "Home", "Deck assignment", "Tip operations",
            "Aspirate/Dispense", "Disconnect",
        ]:
            skip(label, skip_msg)
    else:
        # ---- connect ----
        test_connect(base, args.host)
        test_double_connect(base, args.host)
        # test_home(base)

        # ---- deck ----
        test_deck_empty(base)
        test_assign_tip_rack(base, slot=1)
        test_assign_plate(base, slot=2)
        test_deck_populated(base)
        test_slot_validation(base)

        # ---- liquid handling ----
        test_pick_up_tips(base, "test_tips")
        test_aspirate(base, "test_plate")
        # test_dispense(base, "test_plate")
        test_return_tips(base)
        # test_drop_tips_trash(base, "test_tips")
        #
        # # ---- cleanup ----
        # test_remove_slot(base, slot=9)
        # test_remove_slot(base, slot=6)
        # test_remove_slot(base, slot=4)
        # test_remove_empty_slot(base)
        test_home(base)
        test_disconnect(base)

    # ---- summary ----
    total = passed + failed + skipped
    print(f"\n{'='*40}")
    print(f"  {passed} passed, {failed} failed, {skipped} skipped  ({total} total)")
    print(f"{'='*40}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
