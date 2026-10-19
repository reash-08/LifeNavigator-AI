import sys
import json
import urllib.request
import urllib.error
import ssl
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent

with open(REPO_DIR / "data" / "schemes" / "starter.json", "r", encoding="utf-8") as f:
    dataset = json.load(f)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

unique_urls = {}
for s in dataset["schemes"]:
    url = s["source_url"]
    if url not in unique_urls:
        unique_urls[url] = []
    unique_urls[url].append(s["name"])

print(f"Total unique URLs to test: {len(unique_urls)}")

def check_one(item):
    url, scheme_names = item
    status = "unknown"
    code = None
    error = None
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
            code = resp.getcode()
            status = f"HTTP {code}"
    except urllib.error.HTTPError as e:
        code = e.code
        status = f"HTTP {e.code}"
        error = str(e.reason)
    except urllib.error.URLError as e:
        status = "Connection/DNS error"
        error = str(e.reason)
    except Exception as e:
        status = "Error"
        error = str(e)
    return {
        "url": url,
        "schemes": scheme_names,
        "status": status,
        "status_code": code,
        "error": error
    }

results = []
with ThreadPoolExecutor(max_workers=20) as executor:
    futures = [executor.submit(check_one, item) for item in unique_urls.items()]
    for f in as_completed(futures):
        res = f.result()
        results.append(res)
        print(f"Checked: {res['url']} -> {res['status']}")

with open(BACKEND_DIR / "scripts" / "url_check_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

status_counts = {}
for r in results:
    s = r["status"]
    status_counts[s] = status_counts.get(s, 0) + 1

print("\nSummary of URL check results:")
for s, count in sorted(status_counts.items(), key=lambda x: -x[1]):
    print(f"  {s}: {count}")
