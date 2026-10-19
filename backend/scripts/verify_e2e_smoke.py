"""End-to-End smoke test verifying all core LifeNavigator-AI user journeys."""
import sys
import uuid
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main
from fastapi.testclient import TestClient

client = TestClient(main.app)

def run_smoke_test():
    print("=" * 70)
    print("LIFENAVIGATOR-AI END-TO-END SMOKE TEST")
    print("=" * 70)

    # 1. Health checks
    print("\n[1] Checking service health and readiness...")
    liveness = client.get("/health")
    assert liveness.status_code == 200, f"Liveness failed: {liveness.status_code}"
    print("  [PASS] Liveness probe OK:", liveness.json())

    readiness = client.get("/health/ready")
    assert readiness.status_code == 200, f"Readiness failed: {readiness.status_code}"
    print("  [PASS] Readiness probe OK (DB connected):", readiness.json())

    # 2. Register & Login
    unique_email = f"citizen_{uuid.uuid4().hex[:8]}@example.com"
    password = "StrongPassword2026!"
    print(f"\n[2] Registering citizen account: {unique_email}...")
    reg_res = client.post("/api/auth/register", json={
        "email": unique_email,
        "password": password
    })
    assert reg_res.status_code == 201, f"Registration failed: {reg_res.status_code} {reg_res.text}"
    user_id = reg_res.json()["id"]
    print(f"  [PASS] Registered user ID: {user_id}")

    print("  Logging in citizen...")
    login_res = client.post("/api/auth/login", json={
        "email": unique_email,
        "password": password
    })
    assert login_res.status_code == 200, f"Login failed: {login_res.status_code} {login_res.text}"
    token = login_res.json()["access_token"]
    assert token, "No access token returned"
    print("  [PASS] JWT access token acquired successfully")
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 3. Create & Get Profile
    print("\n[3] Creating citizen profile...")
    profile_payload = {
        "full_name": "Ramanathan Sundaram",
        "age": 42,
        "gender": "Male",
        "marital_status": "Married",
        "state": "Tamil Nadu",
        "district": "Madurai",
        "pincode": "625001",
        "domicile_state": "Tamil Nadu",
        "rural_or_urban": "rural",
        "category": "OBC",
        "minority_status": False,
        "education": "Secondary",
        "course": None,
        "specialization": None,
        "institution_type": None,
        "year_of_study": None,
        "previous_qualification": None,
        "marks_percentage": None,
        "employment_status": "Self-Employed",
        "occupation": "Farmer",
        "beneficiary_group": "Farmer",
        "fisher_activity": None,
        "employment_type": None,
        "annual_income": 140000,
        "income_source": "Agriculture",
        "income_certificate_available": True,
        "bpl_status": False,
        "ration_card_type": "PHH",
        "family_size": 4,
        "dependents": 2,
        "parents_alive": True,
        "single_parent": False,
        "orphan": False,
        "has_disability": False,
        "disability_type": None,
        "disability_percentage": None,
        "disability_certificate_available": False,
        "is_farmer": True,
        "land_ownership": True,
        "land_area": 2.0,
        "land_unit": "acre",
        "crop_type": "Paddy",
        "irrigation_available": True,
        "owns_house": True,
        "house_type": "Semi-Pucca",
        "housing_condition": "Fair",
        "electricity_available": True,
        "toilet_available": True,
        "widow": False,
        "ex_serviceman_family": False,
        "senior_citizen": False
    }
    prof_create_res = client.post("/api/profile", json=profile_payload, headers=auth_headers)
    assert prof_create_res.status_code == 201, f"Profile creation failed: {prof_create_res.status_code} {prof_create_res.text}"
    print(f"  [PASS] Profile created: {prof_create_res.json()['full_name']} (Category: {prof_create_res.json()['category']})")

    prof_get_res = client.get("/api/profile", headers=auth_headers)
    assert prof_get_res.status_code == 200, f"Profile get failed: {prof_get_res.status_code}"
    assert prof_get_res.json()["state"] == "Tamil Nadu"
    print("  [PASS] Profile retrieval verified")

    # 4. Search and browse schemes
    print("\n[4] Searching and browsing schemes...")
    search_all = client.get("/api/schemes/search?limit=10", headers=auth_headers)
    assert search_all.status_code == 200, f"Search failed: {search_all.status_code}"
    search_data = search_all.json()
    print(f"  [PASS] Search endpoint returned {len(search_data['results'])} schemes")

    # Query with keyword
    search_kisan = client.get("/api/schemes/search?q=kisan", headers=auth_headers)
    assert search_kisan.status_code == 200
    kisan_results = search_kisan.json()["results"]
    assert len(kisan_results) > 0, "Expected at least 1 scheme for 'kisan'"
    first_scheme = kisan_results[0]
    print(f"  [PASS] Keyword search found scheme: {first_scheme['name']} (ID: {first_scheme['id']})")

    # Scheme detail by ID
    scheme_id = first_scheme["id"]
    detail_res = client.get(f"/api/schemes/{scheme_id}", headers=auth_headers)
    assert detail_res.status_code == 200, f"Scheme detail failed: {detail_res.status_code}"
    detail_data = detail_res.json()
    print(f"  [PASS] Scheme details retrieved: Benefit: {detail_data.get('benefit', '')[:50]}...")
    print(f"    Source URL: {detail_data.get('source_url')}")
    print(f"    Verification Status: {detail_data.get('verification_status')}")

    # 5. Assess Eligibility
    print("\n[5] Assessing eligibility via /api/eligibility/matches...")
    matches_res = client.get("/api/eligibility/matches", headers=auth_headers)
    assert matches_res.status_code == 200, f"Eligibility matches failed: {matches_res.status_code}"
    matches_list = matches_res.json()
    print(f"  [PASS] Eligibility assessed across {len(matches_list)} active schemes")

    statuses = {m.get("assessment_status") for m in matches_list}
    print(f"  [PASS] Distinct assessment outcomes returned: {statuses}")
    assert "unverified" in statuses, "Expected unverified status in live matches"

    for m in matches_list:
        assert not any("Category does not match" in r for r in m.get("reasons", [])), \
            f"Scheme {m['name']} incorrectly compared sector category!"
    print("  [PASS] Decoupling verified: 0 sector-category false negative rejections across all active schemes")

    # 6. AI Agent Query
    print("\n[6] Querying AI Assistant (/api/agent/query)...")
    agent_res = client.post("/api/agent/query", json={
        "query": "Am I eligible for PM-KISAN?"
    }, headers=auth_headers)
    assert agent_res.status_code == 200, f"Agent query failed: {agent_res.status_code} {agent_res.text}"
    agent_data = agent_res.json()
    print(f"  [PASS] Agent responded: Intent: {agent_data.get('intent')}")
    print(f"    Answer excerpt: {agent_data.get('answer')[:80]}...")
    print(f"    Schemes evaluated: {len(agent_data.get('schemes', []))}")
    print(f"    Sources cited: {len(agent_data.get('sources', []))}")

    print("\n" + "=" * 70)
    print("ALL END-TO-END USER JOURNEYS PASSED CLEANLY (100% OPERATIONAL)")
    print("=" * 70)

if __name__ == "__main__":
    run_smoke_test()
