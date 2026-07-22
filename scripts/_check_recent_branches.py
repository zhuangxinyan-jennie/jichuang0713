#!/usr/bin/env python3
import json
import urllib.request


def get(url: str):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "cursor-agent", "Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


print("=== recent repo events (origin) ===")
try:
    ev = get("https://api.github.com/repos/zhuangxinyan-jennie/jichuang0713/events?per_page=20")
    for e in ev[:20]:
        created = (e.get("created_at") or "")[:19]
        actor = (e.get("actor") or {}).get("login")
        t = e.get("type")
        payload = e.get("payload") or {}
        extra = ""
        if t == "PushEvent":
            ref = payload.get("ref", "")
            commits = payload.get("commits") or []
            msg = commits[0]["message"].split("\n")[0] if commits else ""
            extra = f" ref={ref} n={len(commits)} | {msg}"
        elif t == "CreateEvent":
            extra = f" ref_type={payload.get('ref_type')} ref={payload.get('ref')}"
        elif t == "PullRequestEvent":
            pr = payload.get("pull_request") or {}
            extra = f" action={payload.get('action')} #{pr.get('number')} {str(pr.get('title') or '')[:60]}"
        print(f"{created} {actor} {t}{extra}")
except Exception as ex:
    print("events fail:", ex)

print("\n=== origin branches ===")
for b in get("https://api.github.com/repos/zhuangxinyan-jennie/jichuang0713/branches?per_page=100"):
    print(b["name"], b["commit"]["sha"][:8])

print("\n=== teammate fork branches (with latest commit time) ===")
for b in get("https://api.github.com/repos/sherry-THRZ/jichuang0713/branches?per_page=100"):
    sha = b["commit"]["sha"]
    c = get(f"https://api.github.com/repos/sherry-THRZ/jichuang0713/commits/{sha}")
    date = c["commit"]["author"]["date"][:19]
    msg = c["commit"]["message"].split("\n")[0][:80]
    print(f"{date}  {b['name']:40} {sha[:8]} | {msg}")

print("\n=== PRs sorted by updated ===")
prs = get(
    "https://api.github.com/repos/zhuangxinyan-jennie/jichuang0713/pulls?state=all&per_page=15&sort=updated"
)
for p in prs:
    print(
        f"#{p['number']} [{p['state']}] updated={p['updated_at'][:16]} "
        f"created={p['created_at'][:10]} head={p['head']['ref']} | {p['title'][:70]}"
    )
