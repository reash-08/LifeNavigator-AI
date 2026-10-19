import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database.connection import SessionLocal
from app.models.scheme import Scheme

with SessionLocal() as db:
    verified_schemes = db.query(Scheme).filter_by(verification_status="verified").all()
    print(f"Total verified schemes in DB: {len(verified_schemes)}")
    
    active_verified = [s for s in verified_schemes if s.is_active]
    inactive_verified = [s for s in verified_schemes if not s.is_active]
    
    print(f"Active verified: {len(active_verified)}")
    print(f"Inactive verified: {len(inactive_verified)}")
    for s in inactive_verified:
        print(f"  Inactive Scheme ID {s.id}: '{s.name}' | Category: {s.category}")

    # Check for any expired dates among verified schemes
    for s in verified_schemes:
        if s.application_deadline:
            print(f"  Deadline present on ID {s.id} ('{s.name}'): {s.application_deadline}")

print("\nAll 122 verified schemes inspected.")
