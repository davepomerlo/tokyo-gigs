"""Show the HTML structure around repeated event cards: python tools/dom.py page.html 'css selector or text'"""
import re, sys, collections
from bs4 import BeautifulSoup
html = open(sys.argv[1], encoding="utf-8", errors="replace").read()
soup = BeautifulSoup(html, "lxml")
for t in soup(["script", "style", "svg", "noscript"]): t.decompose()
if len(sys.argv) > 2 and not sys.argv[2].startswith("@"):
    el = soup.find(string=re.compile(sys.argv[2]))
    node = el.parent if el else None
    for _ in range(int(sys.argv[3]) if len(sys.argv) > 3 else 4):
        if node is not None and node.parent is not None: node = node.parent
    print(re.sub(r"\s+", " ", str(node))[:2500] if node else "not found")
else:
    # most repeated class names: likely the event cards
    c = collections.Counter(" ".join(t.get("class")) for t in soup.find_all(True) if t.get("class"))
    print([x for x in c.most_common(25)])
