import sys
import json
import urllib.request
import urllib.parse
from pathlib import Path
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
import os

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")

print("=================================================================")
print("=== END-TO-END APPLICATION WORKFLOW VERIFICATION ===")
print("=================================================================")

def api_call(endpoint, method="GET", data=None, token=None):
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(url, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    body = json.dumps(data).encode("utf-8") if data else None
    try:
        with urllib.request.urlopen(req, data=body) as res:
            return res.status, json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))

import time

# Flow 1: Registration and Login
test_email = f"demouser_{int(time.time())}@example.com"
test_password = "demopassword1234"

status, reg_res = api_call("/api/auth/register", "POST", {"email": test_email, "password": test_password})
print(f"1. Registration ({test_email}): Status {status}")

status, login_res = api_call("/api/auth/login", "POST", {"email": test_email, "password": test_password})
assert status == 200, f"Login failed: {login_res}"
token = login_res["access_token"]
print(f"   Login successful! Access token received.")

# Flow 2: Profile creation, editing, and retrieval
profile_payload = {
    "full_name": "Demo Farmer Kumar",
    "age": 42,
    "gender": "Man",
    "state": "Karnataka",
    "district": "Mandya",
    "marital_status": "Married",
    "education": "Secondary",
    "employment_status": "Self-Employed",
    "annual_income": 120000,
    "bpl_status": True,
    "is_farmer": True,
    "land_ownership": True,
    "owns_house": False,
    "urban": False
}
status, prof_create = api_call("/api/profile", "POST", profile_payload, token)
print(f"2. Profile Creation: Status {status}")
assert status in (200, 201)

status, prof_get = api_call("/api/profile", "GET", token=token)
assert status == 200 and prof_get["full_name"] == "Demo Farmer Kumar"
print(f"   Profile retrieved: {prof_get['full_name']} | State: {prof_get['state']} | Farmer: {prof_get.get('is_farmer')}")

# Update profile
status, prof_put = api_call("/api/profile", "PUT", {**profile_payload, "annual_income": 115000}, token)
assert status == 200
print(f"   Profile updated: Annual income updated to 115000")

# Flow 3: Explore the catalogue and filter schemes by category and state
status, explore_all = api_call("/api/schemes/search?active_only=true&limit=200", "GET")
assert status == 200
print(f"3. Explore (active_only=true): {len(explore_all['results'])} schemes available")

status, agri_filter = api_call("/api/schemes/search?category=Agriculture&limit=50", "GET")
assert status == 200 and len(agri_filter["results"]) >= 13
print(f"   Category filter ('Agriculture'): {len(agri_filter['results'])} schemes")

status, tn_filter = api_call("/api/schemes/search?state=Tamil%20Nadu&limit=50", "GET")
assert status == 200 and len(tn_filter["results"]) >= 8
print(f"   State filter ('Tamil Nadu'): {len(tn_filter['results'])} schemes")

# Flow 4: Search for a scholarship, farmer benefit, and healthcare scheme
for term in ["scholarship", "farmer", "health"]:
    status, search_res = api_call(f"/api/schemes/search?q={term}&limit=5", "GET")
    assert status == 200 and len(search_res["results"]) > 0
    top = search_res["results"][0]
    print(f"4. Search '{term}': Top hit -> '{top['name']}' (score: {top['score']})")

# Flow 5: Open scheme detail page (PM-KISAN ID 11)
status, detail_11 = api_call("/api/schemes/11", "GET")
assert status == 200
print(f"5. Scheme Detail (ID 11): '{detail_11['name']}'")
print(f"   Status: {detail_11['verification_status']} | Source: {detail_11['source_url']}")
print(f"   Benefit: {detail_11['benefit'][:80]}...")
print(f"   Documents: {detail_11['required_documents']}")

# Flow 6: Run eligibility checks (with user profile vs empty profile)
status, matches = api_call("/api/eligibility/matches", "GET", token=token)
assert status == 200
print(f"6. Eligibility Matches for {prof_get['full_name']}: {len(matches)} schemes evaluated")
# Test with user with incomplete profile:
temp_email = "incomplete_user@example.com"
api_call("/api/auth/register", "POST", {"email": temp_email, "password": "pass1234567890"})
_, temp_login = api_call("/api/auth/login", "POST", {"email": temp_email, "password": "pass1234567890"})
temp_token = temp_login["access_token"]
status, inc_matches = api_call("/api/eligibility/matches", "GET", token=temp_token)
assert status == 200 and len(inc_matches) == 0  # No profile created -> returns empty list []
print(f"   Eligibility for user without profile: correctly returns {len(inc_matches)} matches (requires profile)")

# Flow 7: Ask AI assistant for financial support for small farmers
status, agent_farmer = api_call("/api/agent/query", "POST", {"query": "financial support available to small farmers"}, token=token)
assert status == 200
print(f"\n7. AI Assistant ('financial support for small farmers'):")
print(f"   Answer: {agent_farmer['answer'][:120]}...")
print(f"   Schemes recommended: {len(agent_farmer['schemes'])}")
print(f"   Citations provided: {len(agent_farmer['sources'])}")
assert len(agent_farmer["schemes"]) > 0
assert len(agent_farmer["sources"]) > 0

# Flow 8: Ask about a scholarship for a college student
status, agent_scholar = api_call("/api/agent/query", "POST", {"query": "scholarship for a college student"}, token=token)
assert status == 200
print(f"\n8. AI Assistant ('scholarship for a college student'):")
print(f"   Answer: {agent_scholar['answer'][:120]}...")
print(f"   Schemes recommended: {len(agent_scholar['schemes'])}")
print(f"   Citations provided: {len(agent_scholar['sources'])}")
assert len(agent_scholar["schemes"]) > 0

# Flow 9: Ask unsupported question (moon colony subsidy)
status, agent_moon = api_call("/api/agent/query", "POST", {"query": "Find a moon colony relocation subsidy"}, token=token)
assert status == 200
print(f"\n9. AI Assistant Unsupported Query ('Find a moon colony relocation subsidy'):")
print(f"   Insufficient evidence: {agent_moon['insufficient_evidence']}")
print(f"   Schemes count: {len(agent_moon['schemes'])}")
print(f"   Answer: {agent_moon['answer']}")
assert agent_moon["insufficient_evidence"] is True
assert len(agent_moon["schemes"]) == 0

# Flow 10: Citation links and uncertainty display
print("\n10. Citation Verification:")
for src in agent_farmer["sources"][:4]:
    print(f"   - {src['scheme_name']}: {src['source_url']} (status: {src['verification_status']})")
    assert src["source_url"].startswith("http")

print("\n=================================================================")
print(">>> ALL 10 APPLICATION WORKFLOW FLOWS PASSED VERIFICATION! <<<")
print("=================================================================")
