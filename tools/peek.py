"""Print the visible text of a saved page, starting near the first date, to see its layout."""
import re, sys
from bs4 import BeautifulSoup
f, n = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 40
soup = BeautifulSoup(open(f, encoding="utf-8", errors="replace").read(), "lxml")
for t in soup(["script", "style", "noscript", "svg", "head"]): t.decompose()
lines = [re.sub(r"\s+", " ", l).strip() for l in soup.get_text("\n").splitlines()]
lines = [l for l in lines if l]
DATE = re.compile(r"(\d{1,2}\s*[/月.]\s*\d{1,2}\s*日?\s*[\(（]?\s*(月|火|水|木|金|土|日|Mon|Tue|Wed|Thu|Fri|Sat|Sun))|\b20\d\d[./-]\d{1,2}[./-]\d{1,2}|\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b", re.I)
start = next((i for i, l in enumerate(lines) if DATE.search(l)), 0)
print(f"--- {f.split('/')[-1]}: {len(lines)} lines, first date at {start}")
for l in lines[max(0, start - 2):start + n]:
    print("  " + l[:140])
