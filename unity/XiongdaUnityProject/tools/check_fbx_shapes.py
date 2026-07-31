import re
import sys

path = sys.argv[1]
data = open(path, "rb").read()
for name in ("fun", "happy", "cry", "A", "O"):
    print(name, "found" if name.encode() in data else "MISSING")
# print short tokens that look like shape names
seen = set()
for m in re.finditer(rb"[A-Za-z][A-Za-z0-9_]{0,8}", data):
    s = m.group().decode("ascii", "ignore")
    if s in ("fun", "happy", "cry", "A", "O") and s not in seen:
        seen.add(s)
        print("token", s)
