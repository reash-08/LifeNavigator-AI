import sys
import json
import urllib.request
import urllib.error
import ssl
from pathlib import Path

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

results = []
print(f"Checking {len(dataset['schemes'])} URLs...")

unique_urls = {}
for s in dataset["schemes"]:
    url = s["source_url"]
    if url not in unique_urls:
        unique_urls[url] = []
    unique_urls[url].append(s["name"])

print(f"Unique URLs to check: {len(unique_urls)}")

for idx, (url, scheme_names) in enumerate(unique_urls.items(), 1):
    status = "unknown"
    error = None
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=6) as resp:
            status = f"HTTP {resp.getcode()}"
    except urllib.error.HTTPError as e:
        status = f"HTTP {e.code}"
        error = str(e.reason)
    except urllib.error.URLError as e:
        status = "Connection/DNS error"
        error = str(e.reason)
    except Exception as e:
        status = "Error"
        error = str(e)
    results.append({
        "url": url,
        "schemes": scheme_names,
        "status": status,
        "error": error
    })
    print(f"[{idx}/{len(unique_urls)}] {url} -> {status}")

with open(BACKEND_DIR / "scripts" / "url_check_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print("\nFinished URL checks.")
