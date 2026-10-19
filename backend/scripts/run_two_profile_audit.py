"""Two-Person Government Scheme Eligibility & Recommendation Audit.

Runs an end-to-end evaluation of two distinct synthetic citizen profiles:
Profile A: College student (Undergraduate engineering, Age 20, OBC, Tamil Nadu, ₹1,50,000 income)
Profile B: Rural self-employed farmer (Age 45, General, Tamil Nadu, Farmer, 2.5 acres, ₹2,40,000 income)

Uses the actual live FastAPI backend, database, eligibility engine, and AI assistant.
Outputs findings and structured comparison to data/two_profile_audit_results.json.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from main import app
from app.database.connection import SessionLocal
from app.models.scheme import Scheme
from app.models.eligibility_rule import EligibilityRule


def run_audit():
    print("=" * 80)
    print("LIFENAVIGATOR-AI: TWO-PERSON CITIZEN ELIGIBILITY & RECOMMENDATION AUDIT")
    print("=" * 80)

    client = TestClient(app)

    # =========================================================================
    # 1. PERSONA DEFINITIONS
    # =========================================================================
    profile_a_payload = {
        "full_name": "Kavitha Rajan",
        "age": 20,
        "gender": "Female",
        "marital_status": "Single",
        "state": "Tamil Nadu",
        "district": "Coimbatore",
        "pincode": "641001",
        "domicile_state": "Tamil Nadu",
        "rural_or_urban": "urban",
        "category": "OBC",
        "minority_status": False,
        "education": "Undergraduate",
        "course": "Bachelor of Engineering",
        "specialization": "Computer Science and Engineering",
        "institution_type": "Government-aided College",
        "year_of_study": 2,
        "previous_qualification": "Higher Secondary (12th)",
        "marks_percentage": 88.0,
        "employment_status": "Student",
        "occupation": "Student",
        "beneficiary_group": "Students",
        "fisher_activity": None,
        "employment_type": None,
        "sector": "Education",
        "annual_income": 150000,
        "income_source": "Parental Support",
        "income_certificate_available": True,
        "bpl_status": False,
        "ration_card_type": "NPHH",
        "family_size": 4,
        "dependents": 2,
        "parents_alive": True,
        "single_parent": False,
        "orphan": False,
        "has_disability": False,
        "disability_type": None,
        "disability_percentage": None,
        "disability_certificate_available": False,
        "is_farmer": False,
        "land_ownership": False,
        "land_area": None,
        "land_unit": None,
        "crop_type": None,
        "irrigation_available": None,
        "owns_house": True,
        "house_type": "Pucca",
        "housing_condition": "Good",
        "electricity_available": True,
        "toilet_available": True,
        "widow": False,
        "ex_serviceman_family": False,
        "senior_citizen": False,
    }

    profile_b_payload = {
        "full_name": "Murugan Palanisamy",
        "age": 45,
        "gender": "Male",
        "marital_status": "Married",
        "state": "Tamil Nadu",
        "district": "Thanjavur",
        "pincode": "613001",
        "domicile_state": "Tamil Nadu",
        "rural_or_urban": "rural",
        "category": "General",
        "minority_status": False,
        "education": "Secondary",
        "course": None,
        "specialization": None,
        "institution_type": None,
        "year_of_study": None,
        "previous_qualification": "Secondary (10th)",
        "marks_percentage": 62.0,
        "employment_status": "Self-Employed",
        "occupation": "Farmer",
        "beneficiary_group": "Farmers",
        "fisher_activity": None,
        "employment_type": None,
        "sector": "Agriculture",
        "annual_income": 240000,
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
        "land_area": 2.5,
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
        "senior_citizen": False,
    }

    audit_data = {
        "profile_a": {},
        "profile_b": {},
        "comparison": {},
    }

    # =========================================================================
    # 2. EXECUTE AUDIT FOR PROFILE A (STUDENT)
    # =========================================================================
    print("\n>>> AUDITING PROFILE A: COLLEGE STUDENT (Age 20, OBC, TN, Income 1.5L)")
    email_a = "student_audit_2026@example.com"
    pw = "AuditPass2026!"

    # Register/login
    client.post("/api/auth/register", json={"email": email_a, "password": pw})
    login_a = client.post("/api/auth/login", json={"email": email_a, "password": pw})
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Profile CRUD
    prof_res_a = client.post("/api/profile", json=profile_a_payload, headers=headers_a)
    if prof_res_a.status_code != 201:
        # Might already exist, update it
        prof_res_a = client.put("/api/profile", json=profile_a_payload, headers=headers_a)
    print(f"  Profile Status: {prof_res_a.status_code}")

    # Eligibility matching across full catalogue
    matches_a_res = client.get("/api/eligibility/matches", headers=headers_a)
    matches_a = matches_a_res.json()
    print(f"  Total schemes evaluated by engine: {len(matches_a)}")

    statuses_a = {m["assessment_status"] for m in matches_a}
    print(f"  Distinct outcomes returned: {statuses_a}")

    # Keyword search
    search_edu_res = client.get("/api/schemes/search?q=scholarship&limit=50", headers=headers_a)
    search_edu = search_edu_res.json().get("results", [])
    print(f"  Search for 'scholarship' returned: {len(search_edu)} schemes")

    # AI Assistant queries
    q1_a = "What government schemes or scholarships am I eligible for as an undergraduate engineering student in Tamil Nadu with family income of 1.5 lakh?"
    agent_a_1 = client.post("/api/agent/query", json={"query": q1_a}, headers=headers_a).json()
    print(f"  AI Query 1 Response excerpt: {agent_a_1.get('answer', '')[:120]}...")

    q2_a = "Can I apply for Pudhumai Penn or post-matric scholarships?"
    agent_a_2 = client.post("/api/agent/query", json={"query": q2_a}, headers=headers_a).json()
    print(f"  AI Query 2 Response excerpt: {agent_a_2.get('answer', '')[:120]}...")

    # =========================================================================
    # 3. EXECUTE AUDIT FOR PROFILE B (FARMER)
    # =========================================================================
    print("\n>>> AUDITING PROFILE B: RURAL FARMER (Age 45, General, TN, Income 2.4L, 2.5 acres)")
    email_b = "farmer_audit_2026@example.com"

    client.post("/api/auth/register", json={"email": email_b, "password": pw})
    login_b = client.post("/api/auth/login", json={"email": email_b, "password": pw})
    token_b = login_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Profile CRUD
    prof_res_b = client.post("/api/profile", json=profile_b_payload, headers=headers_b)
    if prof_res_b.status_code != 201:
        prof_res_b = client.put("/api/profile", json=profile_b_payload, headers=headers_b)
    print(f"  Profile Status: {prof_res_b.status_code}")

    # Eligibility matching across full catalogue
    matches_b_res = client.get("/api/eligibility/matches", headers=headers_b)
    matches_b = matches_b_res.json()
    print(f"  Total schemes evaluated by engine: {len(matches_b)}")

    statuses_b = {m["assessment_status"] for m in matches_b}
    print(f"  Distinct outcomes returned: {statuses_b}")

    # Keyword search
    search_agri_res = client.get("/api/schemes/search?q=kisan&limit=50", headers=headers_b)
    search_agri = search_agri_res.json().get("results", [])
    print(f"  Search for 'kisan' returned: {len(search_agri)} schemes")

    # AI Assistant queries
    q1_b = "What agricultural or welfare schemes can I apply for as a farmer in Tamil Nadu with 2.5 acres of land?"
    agent_b_1 = client.post("/api/agent/query", json={"query": q1_b}, headers=headers_b).json()
    print(f"  AI Query 1 Response excerpt: {agent_b_1.get('answer', '')[:120]}...")

    q2_b = "Am I eligible for PM-KISAN, PM Fasal Bima Yojana, or PM-KUSUM?"
    agent_b_2 = client.post("/api/agent/query", json={"query": q2_b}, headers=headers_b).json()
    print(f"  AI Query 2 Response excerpt: {agent_b_2.get('answer', '')[:120]}...")

    # =========================================================================
    # 4. SCHEME SELECTION & DOMAIN ANALYSIS
    # =========================================================================
    # Fetch all active schemes from DB with relations for deep inspection
    with SessionLocal() as db:
        all_schemes = db.query(Scheme).filter(Scheme.is_active == True).all()
        scheme_map = {s.id: s for s in all_schemes}

    # Categorize schemes relevant to Student (Profile A)
    # Education, Higher Education, Skill Development, Women Higher Ed (Pudhumai Penn), Youth
    student_relevant_keywords = ["education", "scholarship", "fellowship", "higher education", "student", "college", "pudhumai penn", "skill", "training"]
    student_schemes = []
    for m in matches_a:
        s = scheme_map.get(m["id"])
        if not s:
            continue
        text_corpus = f"{s.name} {s.category or ''} {s.subcategory or ''} {' '.join(s.beneficiary_groups or [])} {s.description or ''}".lower()
        if any(kw in text_corpus for kw in student_relevant_keywords):
            student_schemes.append({
                "id": s.id,
                "name": s.name,
                "ministry": s.ministry,
                "department": s.department,
                "category": s.category,
                "subcategory": s.subcategory,
                "benefit": s.benefit,
                "assessment_status": m.get("assessment_status"),
                "eligible": m.get("eligible"),
                "reasons": m.get("reasons"),
                "missing_fields": m.get("missing_fields"),
                "required_documents": s.required_documents,
                "source_name": s.source_name,
                "source_url": s.source_url,
                "application_url": s.application_url,
                "application_deadline": s.application_deadline,
                "verification_status": s.verification_status,
                "eligibility_verification_status": s.eligibility_verification_status,
            })

    # Categorize schemes relevant to Farmer (Profile B)
    # Agriculture, Farmers, Crops, Soil, Irrigation, Kisan, Rural housing, Health
    farmer_relevant_keywords = ["kisan", "farmer", "agriculture", "crop", "fasal", "kusum", "soil", "irrigation", "mandi", "rural", "krishi", "fertilizer", "horticulture"]
    farmer_schemes = []
    for m in matches_b:
        s = scheme_map.get(m["id"])
        if not s:
            continue
        text_corpus = f"{s.name} {s.category or ''} {s.subcategory or ''} {' '.join(s.beneficiary_groups or [])} {s.description or ''}".lower()
        if any(kw in text_corpus for kw in farmer_relevant_keywords):
            farmer_schemes.append({
                "id": s.id,
                "name": s.name,
                "ministry": s.ministry,
                "department": s.department,
                "category": s.category,
                "subcategory": s.subcategory,
                "benefit": s.benefit,
                "assessment_status": m.get("assessment_status"),
                "eligible": m.get("eligible"),
                "reasons": m.get("reasons"),
                "missing_fields": m.get("missing_fields"),
                "required_documents": s.required_documents,
                "source_name": s.source_name,
                "source_url": s.source_url,
                "application_url": s.application_url,
                "application_deadline": s.application_deadline,
                "verification_status": s.verification_status,
                "eligibility_verification_status": s.eligibility_verification_status,
            })

    # Universal / Shared Welfare Schemes (Health, Insurance, Food, Digital)
    universal_keywords = ["ayushman", "health", "insurance", "ration", "nfsa", "aadhaar", "digital"]
    shared_schemes = []
    for s in all_schemes:
        text_corpus = f"{s.name} {s.category or ''} {s.subcategory or ''} {' '.join(s.beneficiary_groups or [])} {s.description or ''}".lower()
        if any(kw in text_corpus for kw in universal_keywords):
            shared_schemes.append({
                "id": s.id,
                "name": s.name,
                "category": s.category,
                "benefit": s.benefit,
                "required_documents": s.required_documents,
                "source_url": s.source_url,
                "application_url": s.application_url,
            })

    print(f"\nIdentified {len(student_schemes)} schemes relevant to Student (Profile A)")
    print(f"Identified {len(farmer_schemes)} schemes relevant to Farmer (Profile B)")
    print(f"Identified {len(shared_schemes)} universal welfare schemes potentially relevant to both")

    audit_data["profile_a"] = {
        "persona": profile_a_payload,
        "relevant_schemes_count": len(student_schemes),
        "schemes": student_schemes,
        "ai_responses": {
            "query_1": {"prompt": q1_a, "response": agent_a_1},
            "query_2": {"prompt": q2_a, "response": agent_a_2},
        },
    }

    audit_data["profile_b"] = {
        "persona": profile_b_payload,
        "relevant_schemes_count": len(farmer_schemes),
        "schemes": farmer_schemes,
        "ai_responses": {
            "query_1": {"prompt": q1_b, "response": agent_b_1},
            "query_2": {"prompt": q2_b, "response": agent_b_2},
        },
    }

    audit_data["shared_schemes"] = shared_schemes

    # Save to data/
    out_file = REPO_ROOT / "data" / "two_profile_audit_results.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(audit_data, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n[PASS] Complete audit data saved to {out_file}")
    print("=" * 80)
    return audit_data


if __name__ == "__main__":
    run_audit()
