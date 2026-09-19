#!/usr/bin/env python3
"""
GeeLark Cloud Phone Session API Test Suite
Tests the session-based cloud phone endpoints to verify bug fix.
"""

import requests
import time
import random
import string

# Base URL from frontend/.env
BASE_URL = "https://fl1nt-arcade.preview.emergentagent.com/api"

def generate_client_id():
    """Generate a unique test client ID"""
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"qa-{random_suffix}"

def test_session_flow():
    """Test the complete session flow with ONE client ID"""
    
    print("\n" + "="*80)
    print("GEELARK CLOUD PHONE SESSION API TEST")
    print("="*80)
    
    # Generate ONE client ID for all tests
    client_id = generate_client_id()
    print(f"\n🔑 Using clientId: {client_id}")
    print("⚠️  WARNING: This will boot a REAL GeeLark phone (costs money)")
    
    results = {
        "test1_stats_before": False,
        "test2_join": False,
        "test3_heartbeat": False,
        "test4_leave": False,
        "test5_stats_after": False,
    }
    
    stream_url = None
    join_remaining_seconds = None
    
    try:
        # TEST 1: GET /api/cloudphone/session/stats (before join)
        print("\n" + "-"*80)
        print("TEST 1: GET /api/cloudphone/session/stats (before join)")
        print("-"*80)
        
        resp = requests.get(f"{BASE_URL}/cloudphone/session/stats", timeout=30)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.json()}")
        
        if resp.status_code == 200:
            data = resp.json()
            max_slots = data.get("maxSlots")
            session_seconds = data.get("sessionSeconds")
            
            print(f"\n✓ Status code: 200")
            print(f"  maxSlots: {max_slots} (expected: 20)")
            print(f"  sessionSeconds: {session_seconds} (expected: 1800)")
            
            if max_slots == 20 and session_seconds == 1800:
                results["test1_stats_before"] = True
                print("✅ TEST 1 PASSED")
            else:
                print("❌ TEST 1 FAILED: maxSlots or sessionSeconds incorrect")
        else:
            print(f"❌ TEST 1 FAILED: Expected 200, got {resp.status_code}")
        
        # TEST 2: POST /api/cloudphone/session/join
        print("\n" + "-"*80)
        print("TEST 2: POST /api/cloudphone/session/join")
        print("-"*80)
        print(f"Body: {{'clientId': '{client_id}'}}")
        
        resp = requests.post(
            f"{BASE_URL}/cloudphone/session/join",
            json={"clientId": client_id},
            timeout=60  # Longer timeout as this boots a real phone
        )
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.json()}")
        
        if resp.status_code == 200:
            data = resp.json()
            status = data.get("status")
            max_slots = data.get("maxSlots")
            remaining_seconds = data.get("remainingSeconds")
            stream_url = data.get("streamUrl")
            
            print(f"\n✓ Status code: 200")
            print(f"  status: {status} (expected: 'active')")
            print(f"  maxSlots: {max_slots} (expected: 20)")
            print(f"  remainingSeconds: {remaining_seconds} (expected: 1790-1800)")
            
            if stream_url:
                print(f"  streamUrl (first 100 chars): {stream_url[:100]}...")
                print(f"  streamUrl length: {len(stream_url)}")
                
                # CRITICAL CHECK: Verify it's the REAL GeeLark URL, not the mock
                if stream_url.startswith("https://phone.geelark.com/index.html?isApi=true"):
                    print("  ✓ streamUrl starts with 'https://phone.geelark.com/index.html?isApi=true'")
                else:
                    print(f"  ✗ streamUrl does NOT start with expected prefix")
                    print(f"    Actual start: {stream_url[:60]}")
                
                if "token=" in stream_url:
                    print("  ✓ streamUrl contains 'token='")
                else:
                    print("  ✗ streamUrl does NOT contain 'token='")
                
                if "test=1" in stream_url:
                    print("  ✗ streamUrl contains 'test=1' - THIS IS THE OLD MOCK! BUG NOT FIXED!")
                else:
                    print("  ✓ streamUrl does NOT contain 'test=1' (good - not the mock)")
            else:
                print(f"  streamUrl: {stream_url} (may be None if queued)")
            
            # Check all conditions
            checks = {
                "status_active": status == "active",
                "max_slots_20": max_slots == 20,
                "remaining_in_range": remaining_seconds and 1790 <= remaining_seconds <= 1800,
                "stream_url_exists": stream_url is not None,
                "stream_url_prefix": stream_url and stream_url.startswith("https://phone.geelark.com/index.html?isApi=true"),
                "stream_url_has_token": stream_url and "token=" in stream_url,
                "stream_url_no_test": stream_url and "test=1" not in stream_url,
            }
            
            print(f"\nChecks:")
            for check_name, check_result in checks.items():
                print(f"  {check_name}: {'✓' if check_result else '✗'}")
            
            if all(checks.values()):
                results["test2_join"] = True
                join_remaining_seconds = remaining_seconds
                print("✅ TEST 2 PASSED")
            else:
                print("❌ TEST 2 FAILED: One or more checks failed")
        else:
            print(f"❌ TEST 2 FAILED: Expected 200, got {resp.status_code}")
        
        # Wait a bit before heartbeat
        print("\n⏳ Waiting 2 seconds before heartbeat...")
        time.sleep(2)
        
        # TEST 3: POST /api/cloudphone/session/heartbeat
        print("\n" + "-"*80)
        print("TEST 3: POST /api/cloudphone/session/heartbeat")
        print("-"*80)
        print(f"Body: {{'clientId': '{client_id}'}}")
        
        resp = requests.post(
            f"{BASE_URL}/cloudphone/session/heartbeat",
            json={"clientId": client_id},
            timeout=30
        )
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.json()}")
        
        if resp.status_code == 200:
            data = resp.json()
            status = data.get("status")
            remaining_seconds = data.get("remainingSeconds")
            
            print(f"\n✓ Status code: 200")
            print(f"  status: {status} (expected: 'active')")
            print(f"  remainingSeconds: {remaining_seconds}")
            
            if join_remaining_seconds:
                print(f"  Previous remainingSeconds: {join_remaining_seconds}")
                if remaining_seconds <= join_remaining_seconds:
                    print(f"  ✓ remainingSeconds decreased or stayed same (expected)")
                else:
                    print(f"  ✗ remainingSeconds increased (unexpected)")
            
            if status == "active" and remaining_seconds is not None:
                results["test3_heartbeat"] = True
                print("✅ TEST 3 PASSED")
            else:
                print("❌ TEST 3 FAILED: status not active or remainingSeconds missing")
        else:
            print(f"❌ TEST 3 FAILED: Expected 200, got {resp.status_code}")
        
        # TEST 4: POST /api/cloudphone/session/leave
        print("\n" + "-"*80)
        print("TEST 4: POST /api/cloudphone/session/leave")
        print("-"*80)
        print(f"Body: {{'clientId': '{client_id}'}}")
        
        resp = requests.post(
            f"{BASE_URL}/cloudphone/session/leave",
            json={"clientId": client_id},
            timeout=30
        )
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.json()}")
        
        if resp.status_code == 200:
            data = resp.json()
            left = data.get("left")
            
            print(f"\n✓ Status code: 200")
            print(f"  left: {left} (expected: True)")
            
            if left is True:
                results["test4_leave"] = True
                print("✅ TEST 4 PASSED")
            else:
                print("❌ TEST 4 FAILED: left is not True")
        else:
            print(f"❌ TEST 4 FAILED: Expected 200, got {resp.status_code}")
        
        # TEST 5: GET /api/cloudphone/session/stats (after leave)
        print("\n" + "-"*80)
        print("TEST 5: GET /api/cloudphone/session/stats (after leave)")
        print("-"*80)
        
        resp = requests.get(f"{BASE_URL}/cloudphone/session/stats", timeout=30)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.json()}")
        
        if resp.status_code == 200:
            data = resp.json()
            active = data.get("active")
            
            print(f"\n✓ Status code: 200")
            print(f"  active: {active} (expected: 0)")
            
            if active == 0:
                results["test5_stats_after"] = True
                print("✅ TEST 5 PASSED")
            else:
                print(f"❌ TEST 5 FAILED: active is {active}, expected 0")
        else:
            print(f"❌ TEST 5 FAILED: Expected 200, got {resp.status_code}")
        
    except Exception as e:
        print(f"\n❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
    
    # SUMMARY
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    total = len(results)
    passed = sum(results.values())
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if stream_url:
        print(f"\n📋 streamUrl observed (first 100 chars):")
        print(f"   {stream_url[:100]}...")
        
        print(f"\n🔍 KEY VERIFICATION:")
        if stream_url.startswith("https://phone.geelark.com/index.html?isApi=true") and "token=" in stream_url and "test=1" not in stream_url:
            print("   ✅ streamUrl is REAL GeeLark URL (not mock)")
            print("   ✅ BUG FIX VERIFIED: No 'test=1' found")
        else:
            print("   ❌ streamUrl is NOT the expected real GeeLark URL")
            if "test=1" in stream_url:
                print("   ❌ BUG NOT FIXED: 'test=1' found in URL (this is the old mock)")
    
    print("\n" + "="*80)
    
    return all(results.values())

if __name__ == "__main__":
    success = test_session_flow()
    exit(0 if success else 1)
