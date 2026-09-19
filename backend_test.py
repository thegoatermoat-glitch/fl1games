#!/usr/bin/env python3
"""
Backend API Test Suite for fl1nt g4m3s
Tests all backend endpoints with comprehensive validation
"""
import requests
import sys
import os
import time
import base64
import json
from typing import Dict, Any, List

# Get base URL from frontend .env
BASE_URL = "https://fl1nt-arcade.preview.emergentagent.com/api"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_test(name: str, passed: bool, details: str = ""):
    status = f"{Colors.GREEN}✓ PASS{Colors.RESET}" if passed else f"{Colors.RED}✗ FAIL{Colors.RESET}"
    print(f"{status} - {name}")
    if details:
        print(f"  {details}")
    return passed

def test_root_endpoint():
    """Test 1: GET /api/ returns JSON with message"""
    print(f"\n{Colors.BOLD}Test 1: Root Endpoint{Colors.RESET}")
    try:
        resp = requests.get(f"{BASE_URL}/", timeout=10)
        passed = (
            resp.status_code == 200 and
            resp.headers.get('content-type', '').startswith('application/json') and
            'message' in resp.json() and
            'fl1nt g4m3s api online' in resp.json()['message'].lower()
        )
        details = f"Status: {resp.status_code}, Response: {resp.json()}"
        return print_test("GET /api/ returns correct message", passed, details)
    except Exception as e:
        return print_test("GET /api/", False, f"Error: {str(e)}")

def test_games_list_default():
    """Test 2: GET /api/games (no params) returns total=302, games length=60"""
    print(f"\n{Colors.BOLD}Test 2: Games List (Default){Colors.RESET}")
    try:
        resp = requests.get(f"{BASE_URL}/games", timeout=10)
        data = resp.json()
        
        # Check status
        status_ok = resp.status_code == 200
        print_test("Status code 200", status_ok)
        
        # Check total
        total_ok = data.get('total') == 302
        print_test("Total is 302", total_ok, f"Got: {data.get('total')}")
        
        # Check games length
        games = data.get('games', [])
        length_ok = len(games) == 60
        print_test("Games length is 60 (default limit)", length_ok, f"Got: {len(games)}")
        
        # Check game structure
        if games:
            game = games[0]
            required_fields = ['slug', 'name', 'category', 'colorA', 'colorB', 'monogram', 'type']
            has_fields = all(field in game for field in required_fields)
            print_test("Game has required fields", has_fields, f"Sample game: {game.get('slug')}")
            
            # Check optional fields exist (can be null)
            optional_fields = ['image', 'target']
            has_optional = all(field in game for field in optional_fields)
            print_test("Game has optional fields (image, target)", has_optional)
        
        return status_ok and total_ok and length_ok
    except Exception as e:
        return print_test("GET /api/games", False, f"Error: {str(e)}")

def test_games_pagination():
    """Test 3: Pagination with skip=60&limit=60 returns different games"""
    print(f"\n{Colors.BOLD}Test 3: Pagination{Colors.RESET}")
    try:
        # Get first page
        resp1 = requests.get(f"{BASE_URL}/games?skip=0&limit=60", timeout=10)
        data1 = resp1.json()
        page1_slugs = {g['slug'] for g in data1.get('games', [])}
        
        # Get second page
        resp2 = requests.get(f"{BASE_URL}/games?skip=60&limit=60", timeout=10)
        data2 = resp2.json()
        page2_slugs = {g['slug'] for g in data2.get('games', [])}
        
        # Check no overlap
        no_overlap = len(page1_slugs & page2_slugs) == 0
        print_test("Page 1 and Page 2 have different games", no_overlap, 
                   f"Page 1: {len(page1_slugs)} games, Page 2: {len(page2_slugs)} games")
        
        # Test limit cap at 400
        resp3 = requests.get(f"{BASE_URL}/games?limit=1000", timeout=10)
        if resp3.status_code == 200:
            data3 = resp3.json()
            games_count = len(data3.get('games', []))
            capped = games_count <= 400
            print_test("Limit capped at 400 (requested 1000)", capped, 
                       f"Got: {games_count} games")
        elif resp3.status_code == 422:
            print_test("Limit validation returns 422 for limit=1000", True, 
                       "Validation error as expected")
        else:
            print_test("Limit cap handling", False, f"Unexpected status: {resp3.status_code}")
        
        return no_overlap
    except Exception as e:
        return print_test("Pagination test", False, f"Error: {str(e)}")

def test_search():
    """Test 4: Search with q=moto returns case-insensitive matches"""
    print(f"\n{Colors.BOLD}Test 4: Search Functionality{Colors.RESET}")
    try:
        resp = requests.get(f"{BASE_URL}/games?q=moto", timeout=10)
        data = resp.json()
        
        status_ok = resp.status_code == 200
        print_test("Status code 200", status_ok)
        
        games = data.get('games', [])
        total = data.get('total', 0)
        
        # Check all games contain "moto" (case-insensitive)
        all_match = all('moto' in g['name'].lower() for g in games)
        print_test("All returned games contain 'moto' (case-insensitive)", all_match,
                   f"Total matches: {total}, Sample: {games[0]['name'] if games else 'none'}")
        
        # Check total matches count
        count_ok = len(games) <= total
        print_test("Games count <= total", count_ok, f"Games: {len(games)}, Total: {total}")
        
        return status_ok and all_match and count_ok
    except Exception as e:
        return print_test("Search test", False, f"Error: {str(e)}")

def test_category_filter():
    """Test 5: Category filter for 'Cl0ud Gaming' and 'All'"""
    print(f"\n{Colors.BOLD}Test 5: Category Filter{Colors.RESET}")
    try:
        # Test Cl0ud Gaming category
        resp1 = requests.get(f"{BASE_URL}/games?category=Cl0ud%20Gaming", timeout=10)
        data1 = resp1.json()
        
        cloud_total = data1.get('total', 0)
        cloud_games = data1.get('games', [])
        
        total_ok = cloud_total == 2
        print_test("Cl0ud Gaming total is 2", total_ok, f"Got: {cloud_total}")
        
        # Check names
        names = [g['name'] for g in cloud_games]
        has_roblox = any('roblox' in n.lower() for n in names)
        has_fortnite = any('fortnite' in n.lower() for n in names)
        print_test("Includes Roblox (Cl0ud)", has_roblox, f"Names: {names}")
        print_test("Includes Fortnite (Cl0ud)", has_fortnite)
        
        # Check type and target
        all_cloud_type = all(g.get('type') == 'cloud' for g in cloud_games)
        all_have_target = all(g.get('target') is not None for g in cloud_games)
        print_test("All have type='cloud'", all_cloud_type)
        print_test("All have non-null target URL", all_have_target)
        
        # Test 'All' category
        resp2 = requests.get(f"{BASE_URL}/games?category=All", timeout=10)
        data2 = resp2.json()
        all_total = data2.get('total', 0)
        all_ok = all_total == 302
        print_test("Category 'All' returns all 302 games", all_ok, f"Got: {all_total}")
        
        return total_ok and has_roblox and has_fortnite and all_cloud_type and all_have_target and all_ok
    except Exception as e:
        return print_test("Category filter test", False, f"Error: {str(e)}")

def test_categories_endpoint():
    """Test 6: GET /api/categories returns total=302 and 10 categories"""
    print(f"\n{Colors.BOLD}Test 6: Categories Endpoint{Colors.RESET}")
    try:
        resp = requests.get(f"{BASE_URL}/categories", timeout=10)
        data = resp.json()
        
        status_ok = resp.status_code == 200
        print_test("Status code 200", status_ok)
        
        total = data.get('total', 0)
        total_ok = total == 302
        print_test("Total is 302", total_ok, f"Got: {total}")
        
        categories = data.get('categories', [])
        cat_count = len(categories)
        count_ok = cat_count == 10
        print_test("10 categories returned", count_ok, f"Got: {cat_count}")
        
        # Check specific categories
        cat_dict = {c['name']: c['count'] for c in categories}
        
        checks = [
            ("Cl0ud Gaming", 2),
            ("Arcade", 63),
            ("Racing", 50),
            ("Platformer", 52)
        ]
        
        for name, expected_count in checks:
            if name in cat_dict:
                match = cat_dict[name] == expected_count
                print_test(f"Category '{name}' has count {expected_count}", match, 
                           f"Got: {cat_dict[name]}")
            else:
                print_test(f"Category '{name}' exists", False, "Not found")
        
        return status_ok and total_ok and count_ok
    except Exception as e:
        return print_test("Categories endpoint test", False, f"Error: {str(e)}")

def test_single_game():
    """Test 7: GET /api/games/{slug} returns game or 404"""
    print(f"\n{Colors.BOLD}Test 7: Single Game Endpoint{Colors.RESET}")
    try:
        # Test valid slug
        resp1 = requests.get(f"{BASE_URL}/games/2048", timeout=10)
        valid_ok = resp1.status_code == 200
        
        if valid_ok:
            game = resp1.json()
            has_slug = game.get('slug') == '2048'
            has_name = 'name' in game
            print_test("GET /api/games/2048 returns 200", True, 
                       f"Game: {game.get('name')}")
            print_test("Game has correct slug", has_slug)
        else:
            print_test("GET /api/games/2048 returns 200", False, 
                       f"Status: {resp1.status_code}")
        
        # Test invalid slug
        resp2 = requests.get(f"{BASE_URL}/games/does-not-exist", timeout=10)
        invalid_ok = resp2.status_code == 404
        print_test("GET /api/games/does-not-exist returns 404", invalid_ok, 
                   f"Status: {resp2.status_code}")
        
        return valid_ok and invalid_ok
    except Exception as e:
        return print_test("Single game test", False, f"Error: {str(e)}")

def test_game_play_proxy():
    """Test 8: GET /api/games/{slug}/play returns HTML"""
    print(f"\n{Colors.BOLD}Test 8: Game Play Proxy{Colors.RESET}")
    results = []
    
    # Test valid slugs
    test_slugs = ['2048', 'google-dino', 'minesweeper']
    
    for slug in test_slugs:
        try:
            # Use stream=True and only read first chunk
            resp = requests.get(f"{BASE_URL}/games/{slug}/play", timeout=30, stream=True)
            
            status_ok = resp.status_code == 200
            content_type = resp.headers.get('content-type', '')
            type_ok = content_type.startswith('text/html')
            
            # Read only first 1KB to check for HTML
            chunk = next(resp.iter_content(chunk_size=1024), b'')
            chunk_str = chunk.decode('utf-8', errors='ignore').lower()
            has_html = '<html' in chunk_str or '<!doctype' in chunk_str or '<head' in chunk_str
            
            # Close the connection
            resp.close()
            
            passed = status_ok and type_ok and has_html
            results.append(passed)
            
            print_test(f"GET /api/games/{slug}/play", passed,
                       f"Status: {resp.status_code}, Type: {content_type}, Has HTML: {has_html}")
        except Exception as e:
            results.append(False)
            print_test(f"GET /api/games/{slug}/play", False, f"Error: {str(e)}")
    
    # Test invalid slug
    try:
        resp = requests.get(f"{BASE_URL}/games/nope/play", timeout=10)
        invalid_ok = resp.status_code == 404
        results.append(invalid_ok)
        print_test("GET /api/games/nope/play returns 404", invalid_ok, 
                   f"Status: {resp.status_code}")
    except Exception as e:
        results.append(False)
        print_test("Invalid slug test", False, f"Error: {str(e)}")
    
    return all(results)

def test_cloudphone_config():
    """Test 9: GET /api/cloudphone/config returns configuration status"""
    print(f"\n{Colors.BOLD}Test 9: Cloud Phone Config{Colors.RESET}")
    try:
        resp = requests.get(f"{BASE_URL}/cloudphone/config", timeout=10)
        data = resp.json()
        
        status_ok = resp.status_code == 200
        print_test("Status code 200", status_ok)
        
        geelark_configured = data.get('geelarkConfigured') == True
        print_test("geelarkConfigured is true", geelark_configured, 
                   f"Got: {data.get('geelarkConfigured')}")
        
        app_id_present = data.get('appIdPresent') == True
        print_test("appIdPresent is true", app_id_present, 
                   f"Got: {data.get('appIdPresent')}")
        
        api_key_present = data.get('apiKeyPresent') == True
        print_test("apiKeyPresent is true", api_key_present, 
                   f"Got: {data.get('apiKeyPresent')}")
        
        return status_ok and geelark_configured and app_id_present and api_key_present
    except Exception as e:
        return print_test("Cloud phone config test", False, f"Error: {str(e)}")

def test_cloudphone_phones():
    """Test 10: POST /api/cloudphone/phones returns phone list"""
    print(f"\n{Colors.BOLD}Test 10: Cloud Phone List{Colors.RESET}")
    try:
        resp = requests.post(f"{BASE_URL}/cloudphone/phones", json={}, timeout=15)
        data = resp.json()
        
        status_ok = resp.status_code == 200
        print_test("Status code 200", status_ok)
        
        raw_code = data.get('raw_code')
        code_ok = raw_code == 0
        print_test("raw_code == 0 (success)", code_ok, f"Got: {raw_code}")
        
        phones = data.get('phones', [])
        has_phones = len(phones) > 0
        print_test("phones list is non-empty", has_phones, f"Got {len(phones)} phone(s)")
        
        if phones:
            first_phone = phones[0]
            has_id = bool('id' in first_phone and first_phone['id'])
            print_test("First phone has 'id' field", has_id, 
                       f"Phone ID: {first_phone.get('id', 'N/A')}")
        else:
            has_id = False
            print_test("First phone has 'id' field", False, "No phones returned")
        
        return status_ok and code_ok and has_phones and has_id
    except Exception as e:
        return print_test("Cloud phone list test", False, f"Error: {str(e)}")

def decode_jwt_payload(token: str) -> dict:
    """Decode JWT token payload (middle segment)"""
    parts = token.split('.')
    if len(parts) != 3:
        raise ValueError(f"Invalid JWT format: expected 3 parts, got {len(parts)}")
    
    # Get the payload (middle part)
    payload_b64 = parts[1]
    
    # Add padding if needed
    padding = 4 - (len(payload_b64) % 4)
    if padding != 4:
        payload_b64 += '=' * padding
    
    # Decode base64url (replace - with + and _ with /)
    payload_b64 = payload_b64.replace('-', '+').replace('_', '/')
    payload_bytes = base64.b64decode(payload_b64)
    
    # Parse JSON
    return json.loads(payload_bytes.decode('utf-8'))

def test_cloudphone_start_stop():
    """Test 11: POST /api/cloudphone/start and /api/cloudphone/stop
    CRITICAL: This boots a REAL cloud phone that costs money!
    Call start ONCE and immediately call stop.
    """
    print(f"\n{Colors.BOLD}Test 11: Cloud Phone Start/Stop (REAL PHONE - COSTS MONEY){Colors.RESET}")
    print(f"{Colors.YELLOW}⚠️  WARNING: Starting a real GeeLark cloud phone...{Colors.RESET}")
    
    phone_id = None
    start_success = False
    
    try:
        # Test START
        current_time = time.time()
        resp = requests.post(f"{BASE_URL}/cloudphone/start", json={}, timeout=30)
        data = resp.json()
        
        status_ok = resp.status_code == 200
        print_test("Start: Status code 200", status_ok, f"Got: {resp.status_code}")
        
        if not status_ok:
            print(f"{Colors.RED}Start failed with status {resp.status_code}: {data}{Colors.RESET}")
            return False
        
        phone_id = data.get('phoneId')
        stream_url = data.get('streamUrl', '')
        
        has_stream_url = bool(stream_url)
        print_test("Start: streamUrl is non-empty", has_stream_url, 
                   f"URL length: {len(stream_url)}")
        
        starts_correct = stream_url.startswith('https://phone.geelark.com/')
        print_test("Start: streamUrl starts with 'https://phone.geelark.com/'", starts_correct,
                   f"URL prefix: {stream_url[:50] if stream_url else 'N/A'}...")
        
        # Extract and decode JWT token from query parameter
        token_valid = False
        timestamp_delta = None
        
        if stream_url:
            try:
                # Parse URL to get token query parameter
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(stream_url)
                query_params = parse_qs(parsed.query)
                token = query_params.get('token', [None])[0]
                
                if token:
                    print(f"  Token found in URL (length: {len(token)})")
                    
                    # Decode JWT payload
                    payload = decode_jwt_payload(token)
                    print(f"  JWT payload decoded: {payload}")
                    
                    # Extract 'e' field with format "phoneId.timestamp"
                    e_field = payload.get('e', '')
                    if '.' in e_field:
                        parts = e_field.rsplit('.', 1)
                        timestamp_str = parts[-1]
                        token_timestamp = int(timestamp_str)
                        
                        # Calculate delta
                        timestamp_delta = abs(current_time - token_timestamp)
                        
                        # Check if within 120 seconds
                        token_valid = timestamp_delta <= 120
                        
                        print_test("Start: Token timestamp within 120 seconds", token_valid,
                                   f"Delta: {timestamp_delta:.1f} seconds (issued at: {token_timestamp}, current: {int(current_time)})")
                    else:
                        print_test("Start: Token 'e' field format", False, 
                                   f"Expected 'phoneId.timestamp', got: {e_field}")
                else:
                    print_test("Start: Token extraction", False, "No 'token' query parameter found")
            except Exception as e:
                print_test("Start: Token decode/validation", False, f"Error: {str(e)}")
        
        start_success = status_ok and has_stream_url and starts_correct and token_valid
        
    except Exception as e:
        print_test("Cloud phone start test", False, f"Error: {str(e)}")
        start_success = False
    
    # ALWAYS try to stop the phone, even if start failed
    stop_success = False
    try:
        print(f"\n{Colors.YELLOW}⚠️  Stopping cloud phone...{Colors.RESET}")
        stop_resp = requests.post(f"{BASE_URL}/cloudphone/stop", json={}, timeout=30)
        stop_data = stop_resp.json()
        
        stop_status_ok = stop_resp.status_code == 200
        print_test("Stop: Status code 200", stop_status_ok, f"Got: {stop_resp.status_code}")
        
        stopped = stop_data.get('stopped') == True
        print_test("Stop: 'stopped' field is true", stopped, 
                   f"Response: {stop_data}")
        
        stop_success = stop_status_ok and stopped
        
    except Exception as e:
        print_test("Cloud phone stop test", False, f"Error: {str(e)}")
        stop_success = False
    
    return start_success and stop_success

def test_games_total_updated():
    """Test 12: Verify games total is now 301 (Fortnite removed)"""
    print(f"\n{Colors.BOLD}Test 12: Games Total Updated (301){Colors.RESET}")
    try:
        resp = requests.get(f"{BASE_URL}/games", timeout=10)
        data = resp.json()
        
        status_ok = resp.status_code == 200
        print_test("Status code 200", status_ok)
        
        total = data.get('total', 0)
        total_ok = total == 301
        print_test("Total is 301 (Fortnite removed)", total_ok, f"Got: {total}")
        
        return status_ok and total_ok
    except Exception as e:
        return print_test("Games total test", False, f"Error: {str(e)}")

def test_cloud_gaming_category_updated():
    """Test 13: Verify Cl0ud Gaming category has count 1 (only Roblox)"""
    print(f"\n{Colors.BOLD}Test 13: Cl0ud Gaming Category Updated (count=1){Colors.RESET}")
    try:
        resp = requests.get(f"{BASE_URL}/categories", timeout=10)
        data = resp.json()
        
        status_ok = resp.status_code == 200
        print_test("Status code 200", status_ok)
        
        categories = data.get('categories', [])
        cat_dict = {c['name']: c['count'] for c in categories}
        
        if 'Cl0ud Gaming' in cat_dict:
            count = cat_dict['Cl0ud Gaming']
            count_ok = count == 1
            print_test("Cl0ud Gaming count is 1", count_ok, f"Got: {count}")
            return status_ok and count_ok
        else:
            print_test("Cl0ud Gaming category exists", False, "Category not found")
            return False
    except Exception as e:
        return print_test("Cloud gaming category test", False, f"Error: {str(e)}")

def main():
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}fl1nt g4m3s Backend API Test Suite{Colors.RESET}")
    print(f"{Colors.BOLD}Base URL: {BASE_URL}{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
    
    results = []
    
    # Run all tests
    results.append(test_root_endpoint())
    results.append(test_games_list_default())
    results.append(test_games_pagination())
    results.append(test_search())
    results.append(test_category_filter())
    results.append(test_categories_endpoint())
    results.append(test_single_game())
    results.append(test_game_play_proxy())
    
    # NEW: GeeLark cloud phone tests
    results.append(test_cloudphone_config())
    results.append(test_cloudphone_phones())
    results.append(test_cloudphone_start_stop())  # CRITICAL: Costs money!
    
    # NEW: Verify updated game counts
    results.append(test_games_total_updated())
    results.append(test_cloud_gaming_category_updated())
    
    # Summary
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"{Colors.GREEN}{Colors.BOLD}ALL TESTS PASSED ({passed}/{total}){Colors.RESET}")
        sys.exit(0)
    else:
        print(f"{Colors.RED}{Colors.BOLD}SOME TESTS FAILED ({passed}/{total} passed){Colors.RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()
