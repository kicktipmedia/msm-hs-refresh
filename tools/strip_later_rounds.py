#!/usr/bin/env python3
"""Hub later-round toggle (Creative 2026-11-05).

Default: current round only on /high-school/ hub (QF now).
Set HUB_INCLUDE_LATER_ROUNDS=1 to keep SF/Final sections if present in the HTML.
SF/Final live on Full Bracket (/high-school/standings/?view=bracket); hub links there via "Earlier rounds".
"""
from pathlib import Path
import os, re, sys

INCLUDE = os.environ.get("HUB_INCLUDE_LATER_ROUNDS", "0") in ("1", "true", "True", "yes")
PATH = Path(sys.argv[1] if len(sys.argv) > 1 else "/dev/shm/kt/hs1105/site/high-school/index.html")
html = PATH.read_text()
pat = re.compile(
    r'<h2 class="hsh">(?:6A|5A) <em>(?:semifinals|final)</em></h2>'
    r'<div class="hsg c1w">.*?</div>(?=<h2 class="hsh"|<p class="hsnote")',
    re.DOTALL,
)
n = len(pat.findall(html))
if INCLUDE:
    print(f"keep later rounds ({n} sections) in {PATH}")
    sys.exit(0)
new = pat.sub("", html)
PATH.write_text(new)
print(f"stripped {n} SF/Final sections from {PATH} ({len(html)} -> {len(new)})")
