import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database.connection import SessionLocal
from app.models.scheme import Scheme
from app.models.profile import UserProfile
from app.services.retrieval import search_schemes
from app.services.agent import run_agent
from app.services.eligibility import check_scheme_eligibility

with SessionLocal() as db:
    print("Testing Live Retrieval, Scheme Details, Eligibility, and Agent Endpoints...")
    
    # 1. Search schemes
    results = search_schemes(db, "scholarship for higher education", limit=5)
    print(f"Search results count: {len(results)}")
    assert len(results) > 0
    top = results[0]
    print(f"Top search result: {top.name} (score: {top.score})")
    assert top.source_url.startswith("https://")
    print(f"  Citations present: {len(top.evidence)} evidence items")
    for ev in top.evidence[:2]:
        print(f"    - [{ev.kind}] {ev.source_name}: {ev.text[:60]}...")

    # 2. Scheme details
    kcc = db.query(Scheme).filter(Scheme.name.like("%Kisan Credit Card%")).first()
    assert kcc is not None
    print(f"\nScheme details verified: ID {kcc.id} - '{kcc.name}'")
    print(f"  Source: {kcc.source_name} <{kcc.source_url}>")
    print(f"  Benefit: {kcc.benefit[:80]}...")
    print(f"  Category: {kcc.category} | State: {kcc.state or 'All India'}")

    # 3. Eligibility check
    profile = UserProfile(
        user_id=999,
        full_name="Farmer Test",
        age=40,
        gender="Male",
        state="Tamil Nadu",
        annual_income=120000,
        occupation="farmer",
        category="General"
    )
    eligible, reasons = check_scheme_eligibility(profile, kcc)
    print(f"\nEligibility evaluated for {kcc.name}: Eligible={eligible}")
    print(f"  Reasons: {reasons}")

    # 4. AI-agent retrieval with citations
    response = run_agent(db, query="scholarship for student in college", profile=None)
    print(f"\nAgent response intent: {response.intent}")
    print(f"  Answer preview: {response.answer[:120]}...")
    print(f"  Schemes recommended: {len(response.schemes)}")
    print(f"  Sources cited: {len(response.sources)}")
    assert len(response.sources) > 0
    for src in response.sources[:3]:
        print(f"    - Citations: {src.scheme_name} -> {src.source_url}")
        assert src.source_url.startswith("https://")

print("\nAll endpoints verified successfully with live grounded citations.")
