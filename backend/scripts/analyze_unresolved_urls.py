import json
from pathlib import Path

repo_dir = Path(__file__).resolve().parents[2]
results_path = repo_dir / "backend" / "scripts" / "url_check_results.json"

with open(results_path, "r", encoding="utf-8") as f:
    results = json.load(f)

print(f"Total checked URLs: {len(results)}")

non_200 = [r for r in results if r["status"] != "HTTP 200"]
print(f"Total non-200 URLs: {len(non_200)}\n")

by_status = {}
for r in non_200:
    st = r["status"]
    if st not in by_status:
        by_status[st] = []
    by_status[st].append(r)

for st, items in by_status.items():
    print(f"=== {st} ({len(items)} URLs) ===")
    for item in items:
        print(f"  URL: {item['url']}")
        print(f"  Schemes: {', '.join(item['schemes'][:3])}")
        if item.get("error"):
            print(f"  Error Detail: {item['error']}")
        print()
