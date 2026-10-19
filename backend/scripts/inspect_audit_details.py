import json
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

with open("data/two_profile_audit_results.json", encoding="utf-8") as f:
    data = json.load(f)

print("=" * 80)
print(f"PROFILE A (STUDENT) - RELEVANT SCHEMES ({data['profile_a']['relevant_schemes_count']})")
print("=" * 80)
for s in data["profile_a"]["schemes"][:10]:
    print(f"ID {s['id']}: {s['name']}")
    print(f"  Ministry: {s.get('ministry')} | Dept: {s.get('department')}")
    print(f"  Benefit: {s.get('benefit')}")
    print(f"  Assessment Status: {s.get('assessment_status')} | Eligible: {s.get('eligible')}")
    print(f"  Reasons: {s.get('reasons')}")
    print(f"  Missing fields: {s.get('missing_fields')}")
    print(f"  Verification Status: {s.get('verification_status')} | EligVerif: {s.get('eligibility_verification_status')}")
    print(f"  Source: {s.get('source_name')} | URL: {s.get('source_url')}")
    print(f"  Application URL: {s.get('application_url')}")
    print(f"  Required Documents: {s.get('required_documents')}")
    print(f"  Deadline: {s.get('application_deadline')}")
    print("-" * 60)

print("\n" + "=" * 80)
print(f"PROFILE B (FARMER) - RELEVANT SCHEMES ({data['profile_b']['relevant_schemes_count']})")
print("=" * 80)
for s in data["profile_b"]["schemes"][:10]:
    print(f"ID {s['id']}: {s['name']}")
    print(f"  Ministry: {s.get('ministry')} | Dept: {s.get('department')}")
    print(f"  Benefit: {s.get('benefit')}")
    print(f"  Assessment Status: {s.get('assessment_status')} | Eligible: {s.get('eligible')}")
    print(f"  Reasons: {s.get('reasons')}")
    print(f"  Missing fields: {s.get('missing_fields')}")
    print(f"  Verification Status: {s.get('verification_status')} | EligVerif: {s.get('eligibility_verification_status')}")
    print(f"  Source: {s.get('source_name')} | URL: {s.get('source_url')}")
    print(f"  Application URL: {s.get('application_url')}")
    print(f"  Required Documents: {s.get('required_documents')}")
    print(f"  Deadline: {s.get('application_deadline')}")
    print("-" * 60)
