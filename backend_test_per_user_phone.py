#!/usr/bin/env python3
"""
Test script for per-user cloud phone feature verification.
CRITICAL: This creates a REAL paid GeeLark phone. Run EXACTLY ONCE with ONE clientId.
"""
import requests
import random
import string
import sys

# Base URL from frontend/.env
BASE_URL = "https://fl1nt-arcade.preview.emergentagent.com/api"

# Generate ONE random clientId for all tests
CLIENT_ID = f"qa-{''.join(random.choices(string.ascii_lowercase + string.digits, k=8))}"

print(f"🧪 Testing per-user cloud phone feature with clientId: {CLIENT_ID}")
print(f"⚠️  WARNING: This will create a REAL paid GeeLark phone")
print(f"📍 Base URL: {BASE_URL}\n")

test_results = []

# Test 1: POST /api/cloudphone/session/join
print("=" * 80)
print("TEST 1: POST /api/cloudphone/session/join")
print("=" * 80)
try:
    resp = requests.post(f"{BASE_URL}/cloudphone/session/join", json={"clientId": CLIENT_ID}, timeout=60)
    print(f"Status Code: {resp.status_code}")
    
    if resp.status_code != 200:
        print(f"❌ FAILED: Expected 200, got {resp.status_code}")
        print(f"Response: {resp.text}")
        test_results.append(("Test 1: Join", False, f"Status {resp.status_code}"))
    else:
        data = resp.json()
        print(f"Response: {data}")
        
        # Check status == "active"
        status = data.get("status")
        if status != "active":
            print(f"❌ FAILED: Expected status='active', got '{status}'")
            test_results.append(("Test 1: Join", False, f"Status is '{status}' not 'active'"))
        else:
            # Check streamUrl
            stream_url = data.get("streamUrl")
            has_error = "error" in data
            
            if has_error:
                print(f"❌ FAILED: Response contains 'error' field: {data.get('error')}")
                test_results.append(("Test 1: Join", False, f"Error field present: {data.get('error')}"))
            elif not stream_url:
                print(f"❌ FAILED: No streamUrl in response")
                test_results.append(("Test 1: Join", False, "No streamUrl"))
            elif not isinstance(stream_url, str):
                print(f"❌ FAILED: streamUrl is not a string, type={type(stream_url)}")
                test_results.append(("Test 1: Join", False, f"streamUrl type={type(stream_url)}"))
            elif not stream_url.startswith("https://phone.geelark.com/index.html?isApi=true"):
                print(f"❌ FAILED: streamUrl does not start with 'https://phone.geelark.com/index.html?isApi=true'")
                print(f"   Actual prefix: {stream_url[:80]}")
                test_results.append(("Test 1: Join", False, f"Wrong URL prefix: {stream_url[:55]}"))
            elif "token=" not in stream_url:
                print(f"❌ FAILED: streamUrl does not contain 'token='")
                print(f"   streamUrl: {stream_url}")
                test_results.append(("Test 1: Join", False, "No token= in URL"))
            elif "test=1" in stream_url:
                print(f"❌ FAILED: streamUrl contains 'test=1' (mock code still present)")
                print(f"   streamUrl: {stream_url}")
                test_results.append(("Test 1: Join", False, "Mock 'test=1' found in URL"))
            else:
                print(f"✅ PASSED: status='active', streamUrl is valid")
                print(f"   streamUrl prefix (first 55 chars): {stream_url[:55]}")
                print(f"   streamUrl length: {len(stream_url)} chars")
                print(f"   Contains 'token=': ✓")
                print(f"   Does NOT contain 'test=1': ✓")
                print(f"   No 'error' field: ✓")
                test_results.append(("Test 1: Join", True, f"streamUrl prefix: {stream_url[:55]}"))
                
except Exception as e:
    print(f"❌ FAILED: Exception occurred: {e}")
    test_results.append(("Test 1: Join", False, str(e)))

print()

# Test 2: POST /api/cloudphone/session/heartbeat
print("=" * 80)
print("TEST 2: POST /api/cloudphone/session/heartbeat")
print("=" * 80)
try:
    resp = requests.post(f"{BASE_URL}/cloudphone/session/heartbeat", json={"clientId": CLIENT_ID}, timeout=30)
    print(f"Status Code: {resp.status_code}")
    
    if resp.status_code != 200:
        print(f"❌ FAILED: Expected 200, got {resp.status_code}")
        print(f"Response: {resp.text}")
        test_results.append(("Test 2: Heartbeat", False, f"Status {resp.status_code}"))
    else:
        data = resp.json()
        print(f"Response: {data}")
        
        status = data.get("status")
        if status != "active":
            print(f"❌ FAILED: Expected status='active', got '{status}'")
            test_results.append(("Test 2: Heartbeat", False, f"Status is '{status}'"))
        else:
            print(f"✅ PASSED: status='active'")
            test_results.append(("Test 2: Heartbeat", True, "Status active"))
            
except Exception as e:
    print(f"❌ FAILED: Exception occurred: {e}")
    test_results.append(("Test 2: Heartbeat", False, str(e)))

print()

# Test 3: POST /api/cloudphone/session/leave
print("=" * 80)
print("TEST 3: POST /api/cloudphone/session/leave")
print("=" * 80)
try:
    resp = requests.post(f"{BASE_URL}/cloudphone/session/leave", json={"clientId": CLIENT_ID}, timeout=60)
    print(f"Status Code: {resp.status_code}")
    
    if resp.status_code != 200:
        print(f"❌ FAILED: Expected 200, got {resp.status_code}")
        print(f"Response: {resp.text}")
        test_results.append(("Test 3: Leave", False, f"Status {resp.status_code}"))
    else:
        data = resp.json()
        print(f"Response: {data}")
        
        left = data.get("left")
        if left != True:
            print(f"❌ FAILED: Expected left=true, got {left}")
            test_results.append(("Test 3: Leave", False, f"left={left}"))
        else:
            print(f"✅ PASSED: left=true")
            test_results.append(("Test 3: Leave", True, "Left successfully"))
            
except Exception as e:
    print(f"❌ FAILED: Exception occurred: {e}")
    test_results.append(("Test 3: Leave", False, str(e)))

print()

# Test 4: GET /api/cloudphone/session/stats
print("=" * 80)
print("TEST 4: GET /api/cloudphone/session/stats")
print("=" * 80)
try:
    resp = requests.get(f"{BASE_URL}/cloudphone/session/stats", timeout=30)
    print(f"Status Code: {resp.status_code}")
    
    if resp.status_code != 200:
        print(f"❌ FAILED: Expected 200, got {resp.status_code}")
        print(f"Response: {resp.text}")
        test_results.append(("Test 4: Stats", False, f"Status {resp.status_code}"))
    else:
        data = resp.json()
        print(f"Response: {data}")
        
        active = data.get("active")
        if active != 0:
            print(f"❌ FAILED: Expected active=0, got {active}")
            test_results.append(("Test 4: Stats", False, f"active={active}"))
        else:
            print(f"✅ PASSED: active=0")
            test_results.append(("Test 4: Stats", True, "Active sessions = 0"))
            
except Exception as e:
    print(f"❌ FAILED: Exception occurred: {e}")
    test_results.append(("Test 4: Stats", False, str(e)))

print()

# Summary
print("=" * 80)
print("SUMMARY")
print("=" * 80)
passed = sum(1 for _, success, _ in test_results if success)
total = len(test_results)
print(f"Tests Passed: {passed}/{total}\n")

for test_name, success, details in test_results:
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} - {test_name}: {details}")

print()
if passed == total:
    print("🎉 ALL TESTS PASSED - Per-user cloud phone feature is working correctly!")
    sys.exit(0)
else:
    print("⚠️  SOME TESTS FAILED - See details above")
    sys.exit(1)
