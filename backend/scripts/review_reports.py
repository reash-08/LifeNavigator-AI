import json
import csv
from pathlib import Path

repo_dir = Path(__file__).resolve().parents[2]
data_dir = repo_dir / "data" / "schemes"

ref_md = data_dir / "scheme_catalogue_reference.md"
ref_csv = data_dir / "scheme_catalogue_reference.csv"
ref_json = data_dir / "scheme_catalogue_reference.json"
summary_md = data_dir / "scheme_catalogue_summary.md"

print("=== FILE INTEGRITY CHECK ===")
for f in [ref_md, ref_csv, ref_json, summary_md]:
    content = f.read_text(encoding="utf-8")
    lines = len(content.splitlines())
    size_kb = f.stat().st_size / 1024
    print(f"{f.name}: {lines} lines, {size_kb:.1f} KB")

# Verify JSON
with open(ref_json, "r", encoding="utf-8") as f:
    j_data = json.load(f)
meta = j_data["metadata"]
schemes_json = j_data["schemes"]
print(f"\nJSON Meta: total_schemes={meta['total_schemes']}, verified={meta['total_verified']}, needs_review={meta['total_needs_review']}, unverified={meta['total_unverified']}")
print(f"JSON schemes list length: {len(schemes_json)}")

# Verify CSV
with open(ref_csv, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)
print(f"\nCSV rows: {len(rows)}")
print(f"CSV header columns ({len(reader.fieldnames)}): {reader.fieldnames}")

# Verify Markdown Table of Contents and counts
md_content = ref_md.read_text(encoding="utf-8")
headers = [line for line in md_content.splitlines() if line.startswith("#")]
print(f"\nMarkdown headers count: {len(headers)}")

# Consistency between files
assert len(schemes_json) == 130
assert len(rows) == 130
json_ids = {s["id"] for s in schemes_json}
csv_ids = {int(r["id"]) for r in rows}
assert json_ids == csv_ids
print("ID alignment between JSON and CSV: 100% matched (all 130 schemes).")
