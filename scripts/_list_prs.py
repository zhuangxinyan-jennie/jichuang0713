import json
import urllib.request

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "cursor-agent"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

print("=== ALL PRs origin ===")
prs = get("https://api.github.com/repos/zhuangxinyan-jennie/jichuang0713/pulls?state=all&per_page=30")
for p in prs:
    print(f"#{p['number']} [{p['state']}] {p['title']} | by {p['user']['login']} | {p['created_at'][:10]} | head={p['head']['ref']} | updated={p['updated_at'][:16]}")

print("\n=== teammate fork branches ===")
try:
    branches = get("https://api.github.com/repos/sherry-THRZ/jichuang0713/branches?per_page=100")
    for b in branches:
        print(b["name"])
except Exception as e:
    print("fail", e)

print("\n=== search agent/server PRs ===")
try:
    import urllib.parse
    q = urllib.parse.quote("repo:zhuangxinyan-jennie/jichuang0713 is:pr agent OR server OR llm OR 调用")
    data = get(f"https://api.github.com/search/issues?q={q}")
    print("total", data.get("total_count"))
    for i in data.get("items", []):
        print(i["number"], i["title"], i["state"])
except Exception as e:
    print("fail", e)
