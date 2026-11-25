"""Offline checks for hub later-pass polish (names, hashes, tab JS, QA r2 defects)."""
import json, re, shutil, sys, tempfile
from pathlib import Path

def tabOf(h):
    h = (h or "").replace("#", "").lower()
    return "5a" if re.search(r"(?:^|-)5a(?:-|$)", h) else "6a"

def hrefs_for_team(html, name):
    found = []
    for m in re.finditer(r'<a([^>]*?)href="([^"]+)"([^>]*)>(.*?)</a>', html, re.S):
        if f'<span class="nm">{name}</span>' in m.group(4):
            found.append(m.group(2))
    return found

def standings_tab_links(pages):
    """Every in-site link to /high-school/standings/ with a #6a or #5a hash."""
    out = []
    for src, html in pages.items():
        for href in re.findall(r'href="([^"]*#[^"]+)"', html):
            if '#' not in href:
                continue
            path, frag = href.split('#', 1)
            path = path.split('?')[0]
            if frag not in ('6a', '5a'):
                continue
            if href.startswith('#') or path.startswith('/high-school/standings') or path.rstrip('/').endswith('standings'):
                out.append((src, href))
    return out

def polish_css(html):
    m = re.search(r'<style id="hs-polish"[^>]*>(.*?)</style>', html, re.S)
    assert m, 'missing hs-polish style'
    return m.group(1)

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
    rec = pages["high-school/recruiting/index.html"]
    assert 'id="hs-polish"' in idx and "white-space:normal" in idx
    assert "scroll-margin-top:96px" in idx and 'class="tkmask"' in idx
    assert "function tabOf(h)" in idx and "function tabOf(h)" in st

    # Defect 1: real #6a / #5a tags, not a CSS-selector false match.
    css_only = (
        '<style id="hs-polish">.hs [id="6a"],.hs [id="5a"]{scroll-margin-top:96px}</style>'
        '<section class="hsp" id="st-6a"></section>'
    )
    assert "6a" not in hs.hs_inpage_ids(css_only)
    assert "st-6a" in hs.hs_inpage_ids(css_only)
    pre = (
        '<html><head><style id="hs-polish">.hs [id="6a"],.hs [id="5a"]{x:1}</style></head>'
        '<body><section class="hsp" id="st-6a"></section>'
        '<section class="hsp" id="st-5a"></section></body></html>'
    )
    inserted, n_frag = hs.p_standings_frag_ids(pre)
    assert n_frag == 2, n_frag
    assert '<span id="6a" class="hs-frag"' in inserted
    assert '<span id="5a" class="hs-frag"' in inserted
    again, n2 = hs.p_standings_frag_ids(inserted)
    assert n2 == 0 and again == inserted
    assert '<span id="6a" class="hs-frag"' in st and '<span id="5a" class="hs-frag"' in st
    assert "6a" in hs.hs_inpage_ids(st) and "5a" in hs.hs_inpage_ids(st)
    # A style-only id= must not be enough to satisfy the resolver.
    assert "6a" not in hs.hs_inpage_ids(re.sub(r'<span id="6a" class="hs-frag"[^>]*>\s*</span>', '', st))
    tab_links = standings_tab_links(pages)
    assert len(tab_links) >= 8, tab_links
    for src, href in tab_links:
        dest_html = st
        frag = href.split('#', 1)[1]
        assert frag in hs.hs_inpage_ids(dest_html), (src, href)

    # Defect 2: ticker mask matches the UP NEXT pill, ticker navy, not 90px white.
    css = polish_css(idx)
    assert "width:67px" in css and "background:#000e28" in css
    assert "width:90px" not in css and "background:#fff" not in css
    assert "width:67px" in polish_css(st) and "background:#000e28" in polish_css(rec)

    # Defect 3: retarget by the school named in the <a>, not the leftover home slug.
    want = {
        "Skyridge": "/high-school/#hs-6a-final",
        "Corner Canyon": "/high-school/#hs-6a-final",
        "West": "/high-school/#hs-5a-final",
        "Orem": "/high-school/#hs-5a-final",
        "Riverton": "/high-school/#hub-6a",
        "Bingham": "/high-school/#hub-6a",
        "Roy": "/high-school/#hub-5a",
        "Timpview": "/high-school/#hub-5a",
    }
    for name, dest in want.items():
        hrefs = hrefs_for_team(st, name)
        assert hrefs, name
        assert all(h == dest for h in hrefs), (name, hrefs)
    # Final-card hashes are reserved for the four finalists (plus ticker lines, which have no .nm).
    for name in ("Riverton", "Bingham", "Roy", "Timpview"):
        hrefs = hrefs_for_team(st, name)
        assert not any(h.endswith("-final") for h in hrefs), (name, hrefs)

    # Defect 4: jump sentinel sits immediately before the state-final h2; article has no duplicate id.
    for cls in ("6A", "5A"):
        aid = f"hs-{cls.lower()}-final"
        i = idx.find(f'<span id="{aid}" class="hs-jump"')
        assert i >= 0, aid
        h2 = idx.find(f'<h2 class="hsh">{cls} <em>state final</em></h2>', i)
        assert 0 < h2 - i < 200, (aid, idx[i:i+180])
        assert f'<article id="{aid}"' not in idx
    assert ".hs-jump" in css

    assert 'href="/high-school/#hs-6a-final"' in st and 'href="/high-school/#hs-5a-final"' in st
    assert 'href="/high-school/#hub-6a"' in st and 'href="/high-school/#hub-5a"' in st
    assert "#hs-skyridge" not in st and "#hs-corner-canyon" not in st and "#hs-west" not in st
    miss = hs.unresolved_hs_hashes(pages)
    assert miss == [], miss
    rep2 = hs.patch_site(str(td), sched, scores, "2026-11-25")
    assert not any(rep2[f] for f in hs.PAGES), rep2
    for h, want_tab in [
        ("hs-5a-final", "5a"), ("hub-5a", "5a"), ("5a", "5a"), ("st-5a", "5a"),
        ("hs-6a-final", "6a"), ("hub-6a", "6a"), ("6a", "6a"), ("", "6a"),
    ]:
        assert tabOf(h) == want_tab, (h, tabOf(h))
    print("ok")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else str(Path(__file__).resolve().parents[1])))
