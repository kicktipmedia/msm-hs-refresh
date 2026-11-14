"""MSM high school refresh library: allowed-source fetch, parse, merge, live-HTML patch.
Allowed: KSL only (sports.ksl.com, ksl.com/www.ksl.com for KSL redirects). Re-checked after redirects. Blocked: MaxPreps, Deseret News, Yahoo, NFHS Network."""
import re, json, html, hashlib, datetime, urllib.request, os
from zoneinfo import ZoneInfo
MT = ZoneInfo('America/Denver')
BLOCK = ('maxpreps.', 'deseret.', 'yahoo.', 'nfhsnetwork.', 'nfhs.org')
ALLOW = ('sports.ksl.com', 'ksl.com', 'www.ksl.com')  # exact hosts; UHSAA/school sites are hand-entry only
RNAME = {'R1': 'First round', 'QF': 'Quarterfinals', 'SF': 'Semifinals', 'F': 'Final'}
RLAB = {'R1': 'First round', 'QF': 'Quarterfinal', 'SF': 'Semifinal', 'F': 'State final'}
UA = 'Mozilla/5.0 (MSM-HS-Refresh; +https://mtnsportsmedia.com)'

def allowed(url):
    h = re.sub(r'^https?://', '', url).split('/')[0].lower()
    if any(b in h for b in BLOCK): return False
    return url.startswith('https://') and h in ALLOW

def get(url, timeout=30):
    if not allowed(url): raise SystemExit(f'refusing non-allowed source {url}')
    r = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=timeout)
    if not allowed(r.geturl()): raise SystemExit(f'refusing redirect {url} -> {r.geturl()}')
    return r.read().decode('utf-8', 'replace')

def ksl_discover(index_html, limit=4):
    ids = {}
    for u in re.findall(r'https://sports\.ksl\.com/prep/[a-z0-9-]*(?:playoff|recap|roundup)[a-z0-9-]*/(\d+)', index_html):
        pass
    for m in re.finditer(r'(https://sports\.ksl\.com/prep/([a-z0-9-]*(?:playoff|recap|roundup)[a-z0-9-]*)/(\d+))', index_html):
        ids[int(m.group(3))] = m.group(1)
    return [ids[k] for k in sorted(ids, reverse=True)[:limit]]

def norm(s): return re.sub(r'[^a-z]', '', html.unescape(s).lower())

ROUNDMAP = {'firstround': 'R1', 'quarterfinals': 'QF', 'quarterfinal': 'QF', 'semifinals': 'SF', 'semifinal': 'SF', 'final': 'F', 'finals': 'F', 'championship': 'F', 'statechampionship': 'F', 'statefinal': 'F', 'statefinals': 'F'}
COVERED = {'5A', '6A'}  # 4A and other classifications are not on this site
_CLASS = re.compile(r'^Class\s+(\dA)\b(?:\s*[—–\-]\s*|\s+)(.+)$', re.I)
_SCORE = re.compile(r'^No\.\s*(\d+)\s+(.+?)\s+(\d+)\s*,\s*No\.\s*(\d+)\s+(.+?)\s+(\d+)(?:\s*,?\s*\(?\d?OT\)?)?\s*\.?$')
def _plain(fragment):
    t = html.unescape(re.sub(r'<[^>]+>', '', fragment)).replace('\xa0', ' ').replace('\u200b', '')
    return re.sub(r'\s+', ' ', t).strip()
def _score_row(cls, rnd, s, url):
    return dict(cls=cls, round=rnd, a_seed=int(s.group(1)), a=s.group(2).strip(), a_score=int(s.group(3)),
                b_seed=int(s.group(4)), b=s.group(5).strip(), b_score=int(s.group(6)), source='KSL Sports', source_url=url)
def parse_ksl(page, url):
    """KSL roundup. Accepts both shapes, and does not guess:
    <h3>Class 5A — First round</h3><strong>No. 16 Roy 0, No. 1 West 63</strong>
    <h2>Class 6A semifinals</h2><h3>No. 1 Skyridge 35, No. 4 Herriman 34</h3>
    A score split across two adjacent <strong> tags, with a trailing mascot, is one line.
    A line that is not a complete seeded score is skipped. 4A is ignored."""
    page = re.sub(r'</strong>\s*<strong>', ' ', page, flags=re.I)
    out = []; cls = rnd = None; cls_level = None
    for m in re.finditer(r'<h[23][^>]*>(.*?)</h[23]>|<strong>(.*?)</strong>', page, re.S | re.I):
        t = _plain(m.group(1) if m.group(1) is not None else m.group(2))
        if m.group(1) is not None:
            level = int(m.group(0)[2])  # h2 -> 2, h3 -> 3; a lower number outranks
            h = _CLASS.match(t)
            if h:
                c, r = h.group(1).upper(), ROUNDMAP.get(norm(h.group(2)))
                if c in COVERED and r:
                    cls, rnd, cls_level = c, r, level
                else:
                    cls = rnd = cls_level = None
                continue
            s = _SCORE.match(t) if cls and rnd else None
            if s:
                out.append(_score_row(cls, rnd, s, url))
                continue
            # A heading that is not a class and not a score ends the section when it is
            # at the class heading's level or higher. A lower heading (h3 under an h2
            # class) does not, so one bad h3 does not drop the rest of that class.
            if cls_level is not None and level <= cls_level:
                cls = rnd = cls_level = None
            continue
        if not cls or not rnd:
            continue
        s = _SCORE.match(t)
        if s:
            out.append(_score_row(cls, rnd, s, url))
    return out

def _catalog(sched):
    names = []
    for g in sched['games']:
        for side in ('home', 'away'):
            t = g.get(side)
            if t and t.get('school'):
                names.append(t['school'])
    return names
def _label_hits(label, school, protected):
    """Exact school, or school plus one trailing mascot word. Never a prefix guess.
    norm() drops digits, so a trailing number is rejected before that comparison."""
    label = ' '.join(str(label).split())
    parts = label.split()
    if len(parts) >= 2 and re.fullmatch(r"[A-Za-z][A-Za-z'’.\-]*", parts[-1]) is None:
        return [p.lower() for p in parts] == [p.lower() for p in str(school).split()]
    if norm(label) == norm(school):
        return True
    if len(parts) < 2 or parts[-1].lower() in protected:
        return False
    return norm(' '.join(parts[:-1])) == norm(school)
def _bind(c, g, protected):
    if not g.get('home') or not g.get('away'):
        return None
    schools = (g['home']['school'], g['away']['school'])
    def hits(label):
        return [s for s in schools if _label_hits(label, s, protected)]
    A, B = hits(c['a']), hits(c['b'])
    if len(A) != 1 or len(B) != 1 or A[0] == B[0]:
        return None
    return {norm(A[0]): c['a_score'], norm(B[0]): c['b_score']}

_CF_EMAIL_JS = re.compile(
    br'<script\b[^>]*\bsrc\s*=\s*["\'][^"\']*?/cdn-cgi/scripts/[^"\']*email-decode\.min\.js[^"\']*["\'][^>]*>\s*</script>',
    re.I)
_CF_EMAIL_EL = re.compile(
    br'<(a|span)\b[^>]*?(?:'
    br'href\s*=\s*["\'](?:mailto:[^"\']*|/cdn-cgi/l/email-protection[^"\']*)["\']'
    br'|__cf_email__'
    br'|data-cfemail\s*=\s*["\'][^"\']+["\']'
    br')[^>]*>(?:[^<]|<span\b[^>]*>[^<]*</span>)*</\1>',
    re.I)
def strip_cf_email(b):
    """Drop only Cloudflare email obfuscation so a live body can equal the repo file.
    That is the email-decode.min.js injector and mailto / __cf_email__ / data-cfemail links.
    Anything else is left byte for byte."""
    if isinstance(b, str):
        b = b.encode('utf-8')
    b = _CF_EMAIL_JS.sub(b'', b)
    return _CF_EMAIL_EL.sub(b'@', b)

def resolve(sched, scores):
    """Fill TBA teams from finals (winner of feed game). Returns games by id."""
    G = {g['id']: g for g in sched['games']}
    fin = {f"{f['class']}-{f.get('rid','R1')}-{f['game']}" if f.get('rid','R1')!='F' else f"{f['class']}-F": f for f in scores['finals']}
    pend = {f"{p['class']}-{p.get('rid','R1')}-{p['game']}" if p.get('rid','R1')!='F' else f"{p['class']}-F": p for p in scores.get('pending', [])}
    def winner(gid):
        g = G[gid]; f = fin.get(gid)
        if f:
            w = f['home'] if f['home_score'] > f['away_score'] else f['away']
        elif pend.get(gid, {}).get('winner'): w = pend[gid]['winner']
        else: return None
        return next(t for t in (g['home'], g['away']) if t and t['school'] == w)
    for rd in ('SF', 'F'):
        for g in [x for x in G.values() if x['round'] == rd]:
            ws = [winner(f) for f in g['feeds']]
            if all(ws) and not g.get('home'):
                g['home'], g['away'] = ws[0], ws[1]  # neutral site: feed order
    return G, fin, pend, winner

def merge(sched, scores, cands, today):
    """Returns (new_finals, conflicts, unmatched). Never overwrites; disagreement -> conflict (pending + issue)."""
    G, fin, pend, _ = resolve(sched, scores)
    protected = {n.split()[-1].lower() for n in _catalog(sched) if n.split()}
    by = {}; unmatched = []
    for c in cands:
        hits = []
        for g in G.values():
            if g['cls'] != c['cls'] or g['round'] != c['round']:
                continue
            sc = _bind(c, g, protected)
            if sc:
                hits.append((g, sc))
        if len(hits) != 1:
            unmatched.append(c); continue  # none or ambiguous: skip, do not guess
        g, sc = hits[0]
        by.setdefault(g['id'], []).append((sc[norm(g['home']['school'])], sc[norm(g['away']['school'])], c))
    new, conflicts = [], []
    for gid, L in by.items():
        g = G[gid]; vals = {(h, a) for h, a, _ in L}
        if gid in fin:
            f = fin[gid]
            if vals != {(f['home_score'], f['away_score'])}:
                conflicts.append(dict(id=gid, kind='disagrees with posted final', posted=(f['home_score'], f['away_score']), seen=sorted(vals), sources=sorted({c['source_url'] for *_, c in L})))
            continue
        if gid in pend and pend[gid].get('hold'):
            continue  # held by a human; resolve by hand
        if len(vals) > 1:
            conflicts.append(dict(id=gid, kind='sources disagree', seen=sorted(vals), sources=sorted({c['source_url'] for *_, c in L}))); continue
        h, a = vals.pop()
        if h == a: conflicts.append(dict(id=gid, kind='tie reported', seen=[(h, a)])); continue
        c = L[0][2]
        new.append(dict(**{'class': g['cls']}, rid=g['round'], round=RNAME[g['round']], game=g['n'], date=g['date'],
                        home=g['home']['school'], home_score=h, away=g['away']['school'], away_score=a,
                        source=f"{c['source']} ({len(L)} matching line(s))", source_url=c['source_url'],
                        entered_by='msm-hs-refresh (auto)', entered_at=datetime.datetime.now(MT).isoformat(timespec='minutes')))
    return new, conflicts, unmatched

# ---------------- live-HTML patcher ----------------
def slug(s): return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')
def kt(date, hhmm):
    d = datetime.datetime.fromisoformat(f"{date}T{hhmm or '18:00'}").replace(tzinfo=MT)
    return d.isoformat()
def tfmt(hhmm):
    if not hhmm: return 'time TBA'
    return datetime.datetime.strptime(hhmm, '%H:%M').strftime('%-I:%M %p') + ' MT'
def dfmt(date): return datetime.date.fromisoformat(date).strftime('%a %b %-d')

def ticker_items(G, fin, pend, winner, today, tab):
    ti = ' tabindex="-1"' if tab else ''
    out = []; ab = {'QF': 'QF', 'SF': 'SF', 'F': 'State final'}
    up = [g for g in G.values() if g['round'] != 'R1' and g.get('home') and g['date'] >= today and g['id'] not in fin and g['id'] not in pend]
    for k in ('6A', '5A'):
        for g in sorted([g for g in up if g['cls'] == k], key=lambda g: (g['date'], ['QF','SF','F'].index(g['round']), g['n'])):
            h, v = g['home']['school'], g['away']['school']
            sep = 'at' if g['round'] == 'QF' else 'vs.'
            pair = f'{html.escape(v)} at {html.escape(h)}' if sep == 'at' else f'{html.escape(h)} vs. {html.escape(v)}'
            out.append(f'<span data-kt="{kt(g["date"], g["kickoff"])}"><b>{dfmt(g["date"])}</b> · <a class="tml"{ti} href="/high-school/#hs-{slug(h)}">{k} {ab[g["round"]]}: {pair}</a> · {tfmt(g["kickoff"])}</span>')
    order = ['R1', 'QF', 'SF', 'F']
    for k in ('6A', '5A'):
        done = [g for g in G.values() if g['cls'] == k and (g['id'] in fin or g['id'] in pend)]
        if not done: continue
        last = max(order.index(g['round']) for g in done)
        LB = {'R1': 'Final', 'QF': 'QF final', 'SF': 'Semifinal', 'F': 'State final'}
        nxt = [g for g in G.values() if g['cls'] == k and order.index(g['round']) == last + 1]
        exp = kt(min(g['date'] for g in nxt), '18:00') if nxt else kt((datetime.date.fromisoformat(max(g['date'] for g in done)) + datetime.timedelta(days=7)).isoformat(), '18:00')
        if exp[:10] < today: continue  # expired results are not re-emitted
        for g in sorted([g for g in done if order.index(g['round']) == last], key=lambda g: g['n']):
            if g['id'] not in fin and not pend[g['id']].get('winner'): continue  # unresolved: nothing published
            anchor = f"hs-{slug(g['home']['school'] if g['round'] in ('R1','QF') else winner(g['id'])['school'])}"
            if g['id'] in fin:
                f = fin[g['id']]; w = f['home'] if f['home_score'] > f['away_score'] else f['away']; l = f['away'] if w == f['home'] else f['home']
                out.append(f'<span data-kt="{exp}"><b>{k} {LB[g['round']]}</b> · <a class="tml"{ti} href="/high-school/#{anchor}">{html.escape(w)} {max(f["home_score"], f["away_score"])}, {html.escape(l)} {min(f["home_score"], f["away_score"])}</a></span>')
            else:
                out.append(f'<span data-kt="{exp}"><b>{k} {LB[g['round']]}</b> · <a class="tml"{ti} href="/high-school/#{anchor}">{html.escape(pend[g["id"]]["winner"])} advances</a></span>')
    return ''.join(out)

def p_ticker(s, G, fin, pend, winner, today):
    return re.sub(r'(<span class="tkh"[^>]*>)((?:<span data-kt[^>]*>.*?</span>)+)</span>',
                  lambda m: m.group(1) + ticker_items(G, fin, pend, winner, today, 'tabindex="-1"' in m.group(2)) + '</span>', s)

ROW = r'(?:<a class="t[^"]*"[^>]*>.*?</a>|<div class="t[^"]*">.*?</div>)'
BLK = re.compile(r'<(div|article)(?P<at>[^>]*\bclass="g(?: [^"]*)?"[^>]*)>(?P<r1>' + ROW + r')(?P<r2>' + ROW + r')(?P<gm><div class="gm[^"]*">.*?</div>)(?P<end></div>|</article>)', re.S)
def nm(row):
    m = re.search(r'<span class="nm">(.*?)</span>', row); return html.unescape(m.group(1)) if m else None
def adv_row(row):
    row = re.sub(r'<a class="t[^"]*"', '<a class="t adv"', row, count=1)
    return re.sub(r'<span class="sc">[^<]*</span>', '<span class="sc">&ndash;</span>', row)
def ph_for(g):
    if g['round'] == 'R1':
        a, b = sorted([g['home']['seed'], g['away']['seed']]); return f'Winner {a}/{b}'
    return f"Winner {g['id'].split('-',1)[1].replace('-','')}" if g['round'] != 'F' else None

def p_bracket(s, G, fin, pend):
    changed = 0
    for k in ('6A', '5A'):
        kl = k.lower()
        for view in ('b', 'f'):
            i = s.find(f'id="p-{kl}-{view}"')
            j = s.find(f'<div id="p-{kl}-f"', i) if view == 'b' else s.find('<p class="hsnote">', i)
            seg = s[i:j]
            # locate blocks -> game ids
            blocks = []
            if view == 'b':
                for ci, rd in enumerate(('R1', 'QF', 'SF', 'F')):
                    a = seg.find(f'id="rd-{kl}-{ci}"'); b = seg.find(f'id="rd-{kl}-{ci+1}"') if ci < 3 else len(seg)
                    for n, m in enumerate(BLK.finditer(seg, a, b), 1):
                        blocks.append((m, f'{k}-{rd}-{n}' if rd != 'F' else f'{k}-F'))
            else:
                for m in BLK.finditer(seg):
                    lab = re.search(r'aria-label="' + k + r' (First round|Quarterfinal|Semifinal|State final) ?(\d*):', m.group('at'))
                    rd = {v: kk for kk, v in RLAB.items()}[lab.group(1)]
                    blocks.append((m, f'{k}-{rd}-{lab.group(2)}' if rd != 'F' else f'{k}-F'))
            repl = []; advance = []
            for m, gid in blocks:
                g = G[gid]; f = fin.get(gid); p = pend.get(gid)
                r1, r2 = m.group('r1'), m.group('r2')
                if f or p:
                    w = (f['home'] if f['home_score'] > f['away_score'] else f['away']) if f else p['winner']
                    for r in (r1, r2):
                        if nm(r) == w: advance.append((g, r))
                if not f or 'final' in m.group('at').split('class="', 1)[1].split('"')[0].split(): continue
                if nm(r1) is None or nm(r2) is None or {nm(r1), nm(r2)} != {f['home'], f['away']}: continue
                sc = {f['home']: f['home_score'], f['away']: f['away_score']}; w = f['home'] if f['home_score'] > f['away_score'] else f['away']
                def fix(r):
                    r = re.sub(r'class="t( adv)?"', lambda x: f'class="t{x.group(1) or ""} {"win" if nm(r) == w else "lose"}"', r, count=1)
                    return re.sub(r'<span class="sc">[^<]*</span>', f'<span class="sc">{sc[nm(r)]}</span>', r)
                at = m.group('at').replace('class="g pending"', 'class="g final"').replace('class="g"', 'class="g final"')
                at = at.replace(', not yet played"', f', final {f["away_score"]} to {f["home_score"]}"')
                gm = re.sub(r'(<div class="gm[^"]*">).*?</div>', r'\1FINAL</div>', m.group('gm'), count=1) if g['round'] != 'R1' else m.group('gm')
                repl.append((m.group(0), f'<{m.group(1)}{at}>{fix(r1)}{fix(r2)}{gm}{m.group("end")}')); changed += 1
            for a, b in repl: seg = seg.replace(a, b, 1)
            for g, r in advance:
                ph = ph_for(g)
                if not ph: continue
                tbd = f'<div class="t tbd"><span class="sd"></span><span class="nm">{ph}</span><span class="sc">&ndash;</span></div>'
                if tbd in seg:
                    seg = seg.replace(tbd, adv_row(r), 1); changed += 1
                    t = [x for x in (g['home'], g['away']) if x['school'] == nm(r)][0]
                    seg = re.sub(r'(aria-label="[^"]*?)' + re.escape(ph) + r'\b', lambda x: x.group(1) + html.escape(f"{t['seed']} {t['school']}"), seg)
            s = s[:i] + seg + s[j:]
    return s, changed

# Creative 2026-11-05: hub shows current round only by default.
# Set HUB_INCLUDE_LATER_ROUNDS=1 to also patch SF/Final cards if present in HTML.
HUB_INCLUDE_LATER_ROUNDS = os.environ.get('HUB_INCLUDE_LATER_ROUNDS', '0') in ('1', 'true', 'True', 'yes')
HUB_ROUNDS = ('R1', 'QF', 'SF', 'F')

def current_hub_round(G, fin, pend, today):
    """Calendar + entered finals → current hub round (SPEC). Defaults to QF in Nov 2026 QF window."""
    # Advance when every game of a round has a final (or pending winner)
    for rnd in ('R1', 'QF', 'SF'):
        games = [g for g in G.values() if g['round'] == rnd]
        if not games:
            continue
        done = all(g['id'] in fin or (g['id'] in pend and pend[g['id']].get('winner')) for g in games)
        if not done:
            return rnd
    return 'F'

def strip_tbd_home_away(article_html):
    """Soft QA: TBD sides (unknown home/away) should not show HOME/AWAY chrome."""
    return re.sub(
        r'(<div class="team (?:away|home) tbd"[^>]*>)<span class="ha">(?:AWAY|HOME)</span>',
        r'\1',
        article_html,
    )


def hub_aid(g, current=None):
    """Anchor id for a hub card. QF uses home-school slug; SF/F use stable round ids.
    When current is set and HUB_INCLUDE_LATER_ROUNDS is off, only that round is addressable."""
    if current and not HUB_INCLUDE_LATER_ROUNDS and g.get('round') != current:
        return None
    if g['round'] == 'QF' and g.get('home'):
        return f'hs-{slug(g["home"]["school"])}'
    if g['round'] == 'SF':
        return f'hs-{g["cls"].lower()}-sf-{g["n"]}'
    if g['round'] == 'F':
        return f'hs-{g["cls"].lower()}-final'
    if g['round'] == 'R1' and g.get('home'):
        return f'hs-{slug(g["home"]["school"])}'
    return None

def p_hub(s, G, fin, pend, today=None):
    """Patch hub cards. Default: current round only (Creative). HUB_INCLUDE_LATER_ROUNDS=1 patches all present."""
    n = 0
    cur = None if HUB_INCLUDE_LATER_ROUNDS else current_hub_round(G, fin, pend, today)
    for gid, g in G.items():
        aid = hub_aid(g, current=cur)
        if not aid: continue
        i = s.find(f'<article id="{aid}"')
        if i < 0: continue
        j = s.find('</article>', i) + 10; a = s[i:j]
        if 'data-game-state="final"' in a: continue
        if 'team away tbd' in a or 'team home tbd' in a:
            a2 = strip_tbd_home_away(a)
            if a2 != a:
                s = s[:i] + a2 + s[j:]; a = a2; j = i + len(a)
        f = fin.get(gid); p = pend.get(gid)
        if not f and not (p and p.get('winner')): continue
        # TBD cards have no real school abbreviations mapped; skip until both sides known
        ab = {html.unescape(v): k for k, v in re.findall(r'<span class="tb"[^>]*>(.*?)</span><span class="nm">(.*?)</span>', a)}
        if f and (f['home'] not in ab or f['away'] not in ab):
            continue
        if 'data-game-state="upcoming"' in a:
            a = a.replace('data-game-state="upcoming"', 'data-game-state="final"', 1)
        else:
            a = a.replace(' data-kickoff=', ' data-game-state="final" data-kickoff=', 1)
        a = re.sub(r'<span class="kt">[^<]*</span>', '<span class="kt">FINAL · ' + dfmt(g['date']).upper() + '</span>', a, count=1)
        if f:
            hs, as_ = f['home_score'], f['away_score']; w = f['home'] if hs > as_ else f['away']
            cd = f'<div class="cd" aria-label="Final: {html.escape(f["away"])} {as_}, {html.escape(f["home"])} {hs}"><div class="lbl"><i>FINAL</i></div><div><b>{as_}</b><i>{ab[f["away"]]}</i></div><div><b>{hs}</b><i>{ab[f["home"]]}</i></div><div><b>{ab[w]}</b><i>WINS</i></div></div>'
            note = f'<p class="hsn">Final: {html.escape(w)} {max(hs, as_)}, {html.escape(f["away"] if w == f["home"] else f["home"])} {min(hs, as_)}. Source: <a href="{html.escape(f["source_url"])}" rel="noopener">{html.escape(f["source"].split(" (")[0].split(",")[0])}</a>.</p>'
        else:
            w = p['winner']
            if w not in ab: continue
            cd = f'<div class="cd" aria-label="{html.escape(w)} advanced; final score pending"><div class="lbl"><i>FINAL</i></div><div><b>{ab[w]}</b><i>ADVANCES</i></div><div><b>&ndash;</b><i>SCORE</i></div><div><b>&ndash;</b><i>PENDING</i></div></div>'
            note = f'<p class="hsn">{html.escape(w)} advanced. We post the final score once sources agree.</p>'
        a = re.sub(r'<div class="cd".*?</div>(?=</div>)', cd, a, count=1)
        a = re.sub(r'<div class="tix".*?</div><p class="hsw">.*?</p>', '', a, count=1)
        a = re.sub(r'<p class="hsn">.*?</p>', note, a, count=1)
        s = s[:i] + a + s[j:]; n += 1
    return s, n

PAGES = ['high-school/index.html', 'high-school/standings/index.html', 'high-school/recruiting/index.html']
def patch_site(root, sched, scores, today):
    G, fin, pend, winner = resolve(sched, scores); rep = {}
    for f in PAGES:
        p = f'{root}/{f}'; s0 = s = open(p, encoding='utf-8').read()
        s = p_ticker(s, G, fin, pend, winner, today)
        if f == PAGES[0]: s, rep['hub'] = p_hub(s, G, fin, pend, today)
        if f == PAGES[1]: s, rep['bracket'] = p_bracket(s, G, fin, pend)
        if s != s0: open(p, 'w', encoding='utf-8').write(s)
        rep[f] = s != s0
    return rep
