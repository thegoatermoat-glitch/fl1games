#!/usr/bin/env python3
"""
Test suite for cloud-phone session queue with 30-minute sessions.
Tests the queue logic with MAX_SLOTS=1 to avoid booting multiple phones.
"""
import requests
import json
import time

# Backend URL from frontend/.env
BASE_URL = "https://fl1nt-arcade.preview.emergentagent.com/api"

def test_a_session_stats_initial():
    """Test A: GET /api/cloudphone/session/stats -> active=0, queued=0, maxSlots=1, sessionSeconds=1800"""
    print("\n=== TEST A: Initial session stats ===")
    resp = requests.get(f"{BASE_URL}/cloudphone/session/stats")
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    assert data["active"] == 0, f"Expected active=0, got {data['active']}"
    assert data["queued"] == 0, f"Expected queued=0, got {data['queued']}"
    assert data["maxSlots"] == 1, f"Expected maxSlots=1, got {data['maxSlots']}"
    assert data["sessionSeconds"] == 1800, f"Expected sessionSeconds=1800, got {data['sessionSeconds']}"
    print("✓ TEST A PASSED")
    return True

def test_b_join_first_client():
    """Test B: POST /api/cloudphone/session/join {"clientId":"clientA"} -> status == "active", remainingSeconds close to 1800"""
    print("\n=== TEST B: First client joins (should become active) ===")
    resp = requests.post(f"{BASE_URL}/cloudphone/session/join", json={"clientId": "clientA"})
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    assert data["status"] == "active", f"Expected status='active', got '{data['status']}'"
    assert "remainingSeconds" in data, "Expected remainingSeconds in response"
    assert data["remainingSeconds"] > 1700, f"Expected remainingSeconds > 1700, got {data['remainingSeconds']}"
    assert data["remainingSeconds"] <= 1800, f"Expected remainingSeconds <= 1800, got {data['remainingSeconds']}"
    assert "streamUrl" in data, "Expected streamUrl in response"
    assert data["streamUrl"].startswith("https://phone.geelark.com/"), f"Expected streamUrl to start with 'https://phone.geelark.com/', got '{data['streamUrl']}'"
    print(f"✓ TEST B PASSED - clientA is active with {data['remainingSeconds']}s remaining, streamUrl: {data['streamUrl']}")
    return True

def test_c_join_second_client():
    """Test C: POST /api/cloudphone/session/join {"clientId":"clientB"} -> status == "queued", position == 1"""
    print("\n=== TEST C: Second client joins (should be queued) ===")
    resp = requests.post(f"{BASE_URL}/cloudphone/session/join", json={"clientId": "clientB"})
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    assert data["status"] == "queued", f"Expected status='queued', got '{data['status']}'"
    assert data["position"] == 1, f"Expected position=1, got {data['position']}"
    assert data["activeCount"] == 1, f"Expected activeCount=1, got {data['activeCount']}"
    assert data["maxSlots"] == 1, f"Expected maxSlots=1, got {data['maxSlots']}"
    print("✓ TEST C PASSED - clientB is queued at position 1")
    return True

def test_d_join_third_client():
    """Test D: POST /api/cloudphone/session/join {"clientId":"clientC"} -> status == "queued", position == 2"""
    print("\n=== TEST D: Third client joins (should be queued at position 2) ===")
    resp = requests.post(f"{BASE_URL}/cloudphone/session/join", json={"clientId": "clientC"})
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    assert data["status"] == "queued", f"Expected status='queued', got '{data['status']}'"
    assert data["position"] == 2, f"Expected position=2, got {data['position']}"
    print("✓ TEST D PASSED - clientC is queued at position 2")
    return True

def test_e_queue_promotion():
    """Test E: Leave clientA, then heartbeat clientB (should be promoted to active), then heartbeat clientC (should be queued at position 1)"""
    print("\n=== TEST E: Queue promotion logic ===")
    
    # Leave clientA
    print("\n--- E.1: clientA leaves ---")
    resp = requests.post(f"{BASE_URL}/cloudphone/session/leave", json={"clientId": "clientA"})
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    assert data["left"] == True, f"Expected left=true, got {data['left']}"
    print("✓ clientA left successfully")
    
    # Heartbeat clientB (should be promoted to active)
    print("\n--- E.2: clientB heartbeat (should be promoted to active) ---")
    resp = requests.post(f"{BASE_URL}/cloudphone/session/heartbeat", json={"clientId": "clientB"})
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    assert data["status"] == "active", f"Expected status='active', got '{data['status']}'"
    assert "remainingSeconds" in data, "Expected remainingSeconds in response"
    print(f"✓ clientB promoted to active with {data['remainingSeconds']}s remaining")
    
    # Heartbeat clientC (should be queued at position 1)
    print("\n--- E.3: clientC heartbeat (should be queued at position 1) ---")
    resp = requests.post(f"{BASE_URL}/cloudphone/session/heartbeat", json={"clientId": "clientC"})
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    assert data["status"] == "queued", f"Expected status='queued', got '{data['status']}'"
    assert data["position"] == 1, f"Expected position=1, got {data['position']}"
    print("✓ clientC is queued at position 1")
    
    print("\n✓ TEST E PASSED - Queue promotion works correctly")
    return True

def test_f_cleanup():
    """Test F: Clean up - leave clientB and clientC"""
    print("\n=== TEST F: Cleanup ===")
    
    # Leave clientB
    print("\n--- F.1: clientB leaves ---")
    resp = requests.post(f"{BASE_URL}/cloudphone/session/leave", json={"clientId": "clientB"})
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    assert data["left"] == True, f"Expected left=true, got {data['left']}"
    print("✓ clientB left successfully")
    
    # Leave clientC
    print("\n--- F.2: clientC leaves ---")
    resp = requests.post(f"{BASE_URL}/cloudphone/session/leave", json={"clientId": "clientC"})
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    assert data["left"] == True, f"Expected left=true, got {data['left']}"
    print("✓ clientC left successfully")
    
    # Verify stats are back to 0
    print("\n--- F.3: Verify stats are back to 0 ---")
    resp = requests.get(f"{BASE_URL}/cloudphone/session/stats")
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"Response: {json.dumps(data, indent=2)}")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    assert data["active"] == 0, f"Expected active=0, got {data['active']}"
    assert data["queued"] == 0, f"Expected queued=0, got {data['queued']}"
    print("✓ Stats back to 0")
    
    print("\n✓ TEST F PASSED - Cleanup successful")
    return True

def main():
    print("=" * 80)
    print("CLOUD-PHONE SESSION QUEUE TEST SUITE")
    print("Testing with MAX_SLOTS=1 and stubbed _ensure_phone_started")
    print("=" * 80)
    
    tests = [
        ("A: Initial stats", test_a_session_stats_initial),
        ("B: First client joins (active)", test_b_join_first_client),
        ("C: Second client joins (queued)", test_c_join_second_client),
        ("D: Third client joins (queued position 2)", test_d_join_third_client),
        ("E: Queue promotion", test_e_queue_promotion),
        ("F: Cleanup", test_f_cleanup),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n❌ TEST {name} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ TEST {name} ERROR: {e}")
            failed += 1
    
    print("\n" + "=" * 80)
    print(f"TEST RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 80)
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
