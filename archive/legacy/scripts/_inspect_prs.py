import json
import urllib.request
import urllib.parse

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "cursor-agent"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

for num in [4, 3, 2]:
    print(f"\n======== PR #{num} files ========")
    files = get(f"https://api.github.com/repos/zhuangxinyan-jennie/jichuang0713/pulls/{num}/files?per_page=100")
    for f in files:
        print(f"{f['status']:8} {f['changes']:5}  {f['filename']}")
    print(f"\n======== PR #{num} commits ========")
    commits = get(f"https://api.github.com/repos/zhuangxinyan-jennie/jichuang0713/pulls/{num}/commits")
    for c in commits:
        print(c["sha"][:8], c["commit"]["message"].split("\n")[0], "|", c["commit"]["author"]["date"][:16])

print("\n======== teammate main recent commits ========")
commits = get("https://api.github.com/repos/sherry-THRZ/jichuang0713/commits?per_page=20")
for c in commits:
    msg = c["commit"]["message"].split("\n")[0]
    print(c["sha"][:8], c["commit"]["author"]["date"][:16], msg)

print("\n======== search code agent server in teammate ========")
# look at bear_agent paths in PR4 patch filenames already listed
