import sys
import json
import urllib.request
import urllib.parse
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

FRONTEND_URL = "http://localhost:5173"
BACKEND_URL = "http://127.0.0.1:8000"

print("=================================================================")
print("=== LIVE FRONTEND & PROXY END-TO-END VERIFICATION ===")
print("=================================================================")

def http_get(url):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as res:
        return res.status, res.read()

def api_call(endpoint, method="GET", data=None, token=None):
    url = f"{FRONTEND_URL}{endpoint}"
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

# 1. Backend Health & Swagger Docs
st_h, body_h = http_get(f"{BACKEND_URL}/health")
assert st_h == 200 and b"ok" in body_h
print(f"1. Backend health ({BACKEND_URL}/health): HTTP {st_h} - OK")

st_doc, body_doc = http_get(f"{BACKEND_URL}/docs")
assert st_doc == 200 and b"Swagger UI" in body_doc
print(f"   Backend Swagger Docs ({BACKEND_URL}/docs): HTTP {st_doc} - OK")

# 2. Frontend Homepage & Proxy Health
st_fe, body_fe = http_get(FRONTEND_URL)
assert st_fe == 200 and b"<!doctype html>" in body_fe.lower()
print(f"2. Frontend Homepage ({FRONTEND_URL}/): HTTP {st_fe} - OK")

st_p_h, body_p_h = http_get(f"{FRONTEND_URL}/health")
assert st_p_h == 200 and b"ok" in body_p_h
print(f"   Frontend Proxy Health ({FRONTEND_URL}/health): HTTP {st_p_h} - OK")

# 3. Explore & Catalogue via Frontend Proxy
status, explore = api_call("/api/schemes/search?active_only=true&limit=200")
assert status == 200
schemes = explore.get("results", [])
print(f"3. Explore schemes via Frontend Proxy: {len(schemes)} active schemes loaded")
assert len(schemes) == 128, f"Expected 128 active schemes, got {len(schemes)}"

# 4. Search, Category, and State Filtering via Frontend Proxy
status, agri = api_call("/api/schemes/search?category=Agriculture&limit=50")
assert status == 200 and len(agri["results"]) == 14
print(f"4. Category filter ('Agriculture') via Proxy: {len(agri['results'])} schemes (All Agriculture)")

status, tn = api_call("/api/schemes/search?state=Tamil%20Nadu&limit=50")
assert status == 200 and len(tn["results"]) == 50
print(f"   State filter ('Tamil Nadu') via Proxy: {len(tn['results'])} schemes (Central + TN)")

status, search_edu = api_call("/api/schemes/search?q=scholarship&limit=5")
assert status == 200 and len(search_edu["results"]) > 0
top_scholarship = search_edu["results"][0]
print(f"   Search 'scholarship' via Proxy: Top hit '{top_scholarship['name']}' (score: {top_scholarship['score']})")

# 5. Scheme Details & Official Links
status, detail = api_call("/api/schemes/11")
assert status == 200 and detail["name"].startswith("Pradhan Mantri Kisan Samman Nidhi")
print(f"5. Scheme Detail (ID 11) via Proxy: '{detail['name']}'")
print(f"   Official URL: {detail['source_url']} | Verified: {detail['verification_status']}")
print(f"   Benefit excerpt: {detail['benefit'][:80]}...")

# 6. Auth & Profile Workflow via Frontend Proxy
test_email = f"live_demo_{int(time.time())}@example.com"
test_pass = "livedemo12345"

status, reg = api_call("/api/auth/register", "POST", {"email": test_email, "password": test_pass})
assert status == 201
print(f"6. User Registration via Proxy ({test_email}): HTTP {status}")

status, login = api_call("/api/auth/login", "POST", {"email": test_email, "password": test_pass})
assert status == 200
token = login["access_token"]
print(f"   User Login via Proxy: HTTP {status} (JWT Access Token issued)")

profile_data = {
    "full_name": "Reviewer Demo Citizen",
    "age": 35,
    "gender": "Woman",
    "state": "Tamil Nadu",
    "district": "Chennai",
    "education": "Graduate",
    "employment_status": "Employed",
    "annual_income": 350000,
    "bpl_status": False,
    "is_farmer": False,
}
status, prof = api_call("/api/profile", "POST", profile_data, token=token)
assert status in (200, 201)
print(f"   Profile Creation via Proxy: HTTP {status} for '{profile_data['full_name']}'")

status, prof_get = api_call("/api/profile", "GET", token=token)
assert status == 200 and prof_get["full_name"] == "Reviewer Demo Citizen"
print(f"   Profile Retrieval via Proxy: Verified profile data in PostgreSQL")

# 7. AI Assistant - Supported Query with Citations
status, agent_resp = api_call("/api/agent/query", "POST", {"query": "financial support available to small farmers"}, token=token)
assert status == 200
print(f"\n7. AI Assistant Supported Query via Proxy:")
print(f"   Query: 'financial support available to small farmers'")
print(f"   Answer: {agent_resp['answer'][:110]}...")
print(f"   Recommended schemes: {len(agent_resp['schemes'])}")
print(f"   Grounded citations: {len(agent_resp['sources'])}")
assert len(agent_resp["schemes"]) > 0 and len(agent_resp["sources"]) > 0
for src in agent_resp["sources"][:2]:
    print(f"   - Citation: {src['scheme_name']} -> {src['source_url']}")

# 8. AI Assistant - Unsupported Query Abstention
status, abstain_resp = api_call("/api/agent/query", "POST", {"query": "Find a moon colony relocation subsidy"}, token=token)
assert status == 200
print(f"\n8. AI Assistant Unsupported Query via Proxy:")
print(f"   Query: 'Find a moon colony relocation subsidy'")
print(f"   insufficient_evidence flag: {abstain_resp['insufficient_evidence']}")
print(f"   Recommended schemes count: {len(abstain_resp['schemes'])}")
print(f"   Answer: {abstain_resp['answer']}")
assert abstain_resp["insufficient_evidence"] is True
assert len(abstain_resp["schemes"]) == 0

print("\n=================================================================")
print(">>> ALL LIVE FRONTEND PROXY END-TO-END WORKFLOWS VERIFIED! <<<")
print("=================================================================")
