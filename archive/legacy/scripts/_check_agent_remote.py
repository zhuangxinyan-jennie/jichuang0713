import json
import urllib.request

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "cursor-agent"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

# Compare teammate main vs origin main for bear_agent paths via commit search
print("=== search commits on teammate for bear_agent/agent ===")
# GitHub code search
try:
    url = "https://api.github.com/search/code?q=repo:sherry-THRZ/jichuang0713+filename:agent.py"
    print(get(url))
except Exception as e:
    print("code search fail (needs auth often):", e)

# Get file content of bear_agent/agent.py from teammate main and look for http
for owner in ["sherry-THRZ", "zhuangxinyan-jennie"]:
    print(f"\n=== {owner} bear_agent/agent.py presence ===")
    try:
        meta = get(f"https://api.github.com/repos/{owner}/jichuang0713/contents/bear_agent/agent.py")
        print("sha", meta.get("sha"), "size", meta.get("size"))
        # raw
        raw_url = meta["download_url"]
        raw = urllib.request.urlopen(urllib.request.Request(raw_url, headers={"User-Agent": "cursor-agent"}), timeout=60).read().decode("utf-8", "replace")
        keys = ["http", "openai", "dashscope", "requests", "server", "api.openai", "base_url", "remote"]
        for k in keys:
            if k.lower() in raw.lower():
                print(f"  contains '{k}'")
        # print first 40 lines
        lines = raw.splitlines()
        print("  lines", len(lines))
        for i, line in enumerate(lines[:30], 1):
            print(f"  {i}: {line[:120]}")
    except Exception as e:
        print("fail", e)

print("\n=== PR4 patch summary (filenames containing agent/llm/server) ===")
files = get("https://api.github.com/repos/zhuangxinyan-jennie/jichuang0713/pulls/4/files?per_page=100")
for f in files:
    name = f["filename"].lower()
    if any(x in name for x in ["agent", "llm", "server", "openai", "dash", "tts", "bear"]):
        print(f["filename"])
