import sys
from pathlib import Path
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from main import app
from app.database.connection import SessionLocal
from app.models.scheme import Scheme
from app.models.profile import UserProfile
from app.models.user import User
from app.services.jwt_service import create_access_token

client = TestClient(app)

print("=================================================================")
print("=== LIVE WORKFLOW, EXPLORE, ELIGIBILITY & AGENT CITATIONS ===")
print("=================================================================")

# -------------------------------------------------------------
# 1. Explore Access - Limit 200 (Active only)
# -------------------------------------------------------------
res_active = client.get("/api/schemes/search?active_only=true&limit=200")
assert res_active.status_code == 200, f"Expected 200, got {res_active.status_code}: {res_active.text}"
active_data = res_active.json()
active_results = active_data.get("results", [])
print(f"1. Explore (active_only=true, limit=200): returned {len(active_results)} schemes")
assert len(active_results) >= 120, f"Expected >= 120 active schemes, got {len(active_results)}"

# Explore Access - Limit 200 (All statuses)
res_all = client.get("/api/schemes/search?active_only=false&limit=200")
assert res_all.status_code == 200
all_results = res_all.json().get("results", [])
print(f"   Explore (active_only=false, limit=200): returned {len(all_results)} schemes in database")
assert len(all_results) == 130, f"Expected 130 total schemes in DB, got {len(all_results)}"

# -------------------------------------------------------------
# 2. Explore Filtering by Category
# -------------------------------------------------------------
res_agri = client.get("/api/schemes/search?category=Agriculture&limit=50")
assert res_agri.status_code == 200
agri_results = res_agri.json().get("results", [])
print(f"2. Category filter ('Agriculture'): returned {len(agri_results)} schemes")
assert len(agri_results) >= 13, f"Expected >= 13 agriculture schemes, got {len(agri_results)}"
for s in agri_results:
    assert s["category"].lower() == "agriculture"

# -------------------------------------------------------------
# 3. Explore Filtering by State
# -------------------------------------------------------------
res_tn = client.get("/api/schemes/search?state=Tamil%20Nadu&limit=50")
assert res_tn.status_code == 200
tn_results = res_tn.json().get("results", [])
print(f"3. State filter ('Tamil Nadu'): returned {len(tn_results)} schemes (national + TN)")
tn_state_specific = [s for s in tn_results if s["state"] == "Tamil Nadu"]
print(f"   Of which state-specific to Tamil Nadu: {len(tn_state_specific)} schemes")
assert len(tn_state_specific) >= 3, f"Expected at least 3 TN state schemes, got {len(tn_state_specific)}"

# -------------------------------------------------------------
# 4. Explore Filtering by Beneficiary Group
# -------------------------------------------------------------
res_farmer = client.get("/api/schemes/search?beneficiary_group=farmer&limit=50")
assert res_farmer.status_code == 200
farmer_results = res_farmer.json().get("results", [])
print(f"4. Beneficiary filter ('farmer'): returned {len(farmer_results)} schemes")
assert len(farmer_results) >= 10, f"Expected >= 10 farmer schemes, got {len(farmer_results)}"

# -------------------------------------------------------------
# 5. Search with Query String
# -------------------------------------------------------------
res_search = client.get("/api/schemes/search?q=scholarship&limit=10")
assert res_search.status_code == 200
search_results = res_search.json().get("results", [])
print(f"5. Keyword search ('scholarship'): returned {len(search_results)} schemes")
assert len(search_results) > 0
top_hit = search_results[0]
print(f"   Top hit: '{top_hit['name']}' (score: {top_hit['score']})")
assert "evidence" in top_hit and len(top_hit["evidence"]) > 0

# -------------------------------------------------------------
# 6. Scheme Details Endpoint
# -------------------------------------------------------------
with SessionLocal() as db:
    pm_kisan = db.query(Scheme).filter(Scheme.id == 11).first()
    assert pm_kisan is not None
    pm_kisan_id = pm_kisan.id

res_detail = client.get(f"/api/schemes/{pm_kisan_id}")
assert res_detail.status_code == 200
detail = res_detail.json()
print(f"\n6. Scheme Details /api/schemes/{pm_kisan_id} -> '{detail['name']}'")
assert detail["id"] == pm_kisan_id
assert "benefit" in detail and len(detail["benefit"]) > 0
assert detail["source_url"].startswith("https://pmkisan.gov.in")
assert detail["verification_status"] == "verified"
print(f"   Category: {detail['category']} | Status: {detail['verification_status']}")
print(f"   Source URL: {detail['source_url']}")
print(f"   Benefit snippet: {detail['benefit'][:80]}...")

# -------------------------------------------------------------
# 7. Eligibility Engine Assessment
# -------------------------------------------------------------
with SessionLocal() as db:
    profile = db.query(UserProfile).first()
    assert profile is not None
    user_id = profile.user_id

token = create_access_token(user_id=user_id)
headers = {"Authorization": f"Bearer {token}"}

res_elig = client.get("/api/eligibility/matches", headers=headers)
assert res_elig.status_code == 200, f"Expected 200, got {res_elig.status_code}: {res_elig.text}"
elig_data = res_elig.json()
print(f"\n7. Eligibility Assessment for User {user_id} (State: {profile.state}, Income: {profile.annual_income}):")
print(f"   Evaluated {len(elig_data)} active schemes")
eligible_matches = [m for m in elig_data if m["eligible"]]
print(f"   Schemes evaluated as eligible: {len(eligible_matches)}")
for match in eligible_matches[:3]:
    print(f"   - Match: '{match['name']}' (Reasons: {match['reasons']})")

# -------------------------------------------------------------
# 8. AI-Agent Query Discovery & Citations
# -------------------------------------------------------------
res_agent = client.post("/api/agent/query", json={"query": "financial assistance for farmers"}, headers=headers)
assert res_agent.status_code == 200, f"Expected 200, got {res_agent.status_code}: {res_agent.text}"
agent_data = res_agent.json()
print(f"\n8. AI-Agent Query ('financial assistance for farmers'):")
print(f"   Intent: '{agent_data['intent']}'")
print(f"   Answer: {agent_data['answer'][:120]}...")
print(f"   Schemes recommended: {len(agent_data['schemes'])}")
print(f"   Sources cited: {len(agent_data['sources'])}")
assert len(agent_data["schemes"]) > 0
assert len(agent_data["sources"]) > 0
for src in agent_data["sources"][:3]:
    print(f"     Citation: {src['scheme_name']} -> {src['source_url']}")
    assert src["source_url"].startswith("https://") or src["source_url"].startswith("http://")

# -------------------------------------------------------------
# 9. AI-Agent Query Abstention (Out-of-domain)
# -------------------------------------------------------------
res_abstain = client.post(
    "/api/agent/query",
    json={"query": "Find a moon colony relocation subsidy"},
    headers=headers,
)
assert res_abstain.status_code == 200
abstain_data = res_abstain.json()
print(f"\n9. AI-Agent Abstention Test:")
print(f"   Insufficient evidence flag: {abstain_data['insufficient_evidence']}")
assert abstain_data["insufficient_evidence"] is True
print(f"   Abstention response snippet: {abstain_data['answer'][:100]}...")

print("\n=================================================================")
print(">>> ALL LIVE WORKFLOW & EXPLORE VERIFICATIONS PASSED CLEANLY! <<<")
print("=================================================================")
