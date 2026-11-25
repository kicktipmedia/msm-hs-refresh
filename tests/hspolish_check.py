"""Offline checks for hub later-pass polish (names, hashes, tab JS)."""
import json, re, shutil, sys, tempfile
from pathlib import Path

def tabOf(h):
    h = (h or "").replace("#", "").lower()
    return "5a" if re.search(r"(?:^|-)5a(?:-|$)", h) else "6a"

def main(root):
    root = Path(root)
    sys.path.insert(0, str(root / "tools"))
    import hs
    td = Path(tempfile.mkdtemp(prefix="hspolish-"))
    for f in hs.PAGES:
        dest = td / f
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(root / "site" / f, dest)
    sched = json.load(open(root / "data/hs_schedule.json"))
    scores = json.load(open(root / "data/hs_scores.json"))
    hs.patch_site(str(td), sched, scores, "2026-11-25")
    pages = {f: (td / f).read_text(encoding="utf-8") for f in hs.PAGES}
    idx, st = pages["high-school/index.html"], pages["high-school/standings/index.html"]
    assert 'id="hs-polish"' in idx and "white-space:normal" in idx
    assert "scroll-margin-top:96px" in idx and 'class="tkmask"' in idx
    assert "function tabOf(h)" in idx and "function tabOf(h)" in st
    assert 'id="6a"' in st and 'id="5a"' in st
    assert 'href="/high-school/#hs-6a-final"' in st and 'href="/high-school/#hs-5a-final"' in st
    assert 'href="/high-school/#hub-6a"' in st and 'href="/high-school/#hub-5a"' in st
    assert "#hs-skyridge" not in st and "#hs-corner-canyon" not in st and "#hs-west" not in st
    miss = hs.unresolved_hs_hashes(pages)
    assert miss == [], miss
    rep2 = hs.patch_site(str(td), sched, scores, "2026-11-25")
    assert not any(rep2[f] for f in hs.PAGES), rep2
    for h, want in [
        ("hs-5a-final", "5a"), ("hub-5a", "5a"), ("5a", "5a"), ("st-5a", "5a"),
        ("hs-6a-final", "6a"), ("hub-6a", "6a"), ("6a", "6a"), ("", "6a"),
    ]:
        assert tabOf(h) == want, (h, tabOf(h))
    print("ok")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1])))
