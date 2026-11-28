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
    # Include "championship" slugs (e.g. championship-football-friday). playoff|recap|roundup alone missed the 2026 5A/6A title recap.
    pat = r'(https://sports\.ksl\.com/prep/([a-z0-9-]*(?:playoff|recap|roundup|championship)[a-z0-9-]*)/(\d+))'
    for m in re.finditer(pat, index_html):
        ids[int(m.group(3))] = m.group(1)
    return [ids[k] for k in sorted(ids, reverse=True)[:limit]]

def norm(s): return re.sub(r'[^a-z]', '', html.unescape(s).lower())

ROUNDMAP = {'firstround': 'R1', 'quarterfinals': 'QF', 'quarterfinal': 'QF', 'semifinals': 'SF', 'semifinal': 'SF', 'final': 'F', 'finals': 'F', 'championship': 'F', 'statechampionship': 'F', 'statefinal': 'F', 'statefinals': 'F'}
def _round_of(rest):
    """Map a Class heading remainder to a round. Exact first, then longest prefix.
    'Championship Game' and 'Championship Game (6 p.m. MT Kickoff)' both map to F."""
    n = norm(rest)
    if n in ROUNDMAP:
        return ROUNDMAP[n]
    for key in sorted(ROUNDMAP, key=len, reverse=True):
        if n.startswith(key):
            return ROUNDMAP[key]
    return None
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
    <h3>Class 5A — Championship Game</h3><strong>No. 1 West Panthers 30, </strong><strong>No. 2 Orem Tigers 21</strong>
    A score split across two adjacent <strong> tags, with a trailing mascot, is one line.
    A line that is not a complete seeded score is skipped. 4A is ignored."""
    page = re.sub(r'</strong>\s*<strong>', ' ', page, flags=re.I)
    out = []; cls = rnd = None; cls_level = None
    for m in re.finditer(r'<h([1-6])[^>]*>(.*?)</h\1>|<strong>(.*?)</strong>', page, re.S | re.I):
        if m.group(1) is not None:
            level = int(m.group(1))  # h1 outranks h6; a lower number is higher
            t = _plain(m.group(2))
            h = _CLASS.match(t)
            if h:
                c, r = h.group(1).upper(), _round_of(h.group(2))
                if c in COVERED and r:
                    cls, rnd, cls_level = c, r, level
                else:
                    cls = rnd = cls_level = None
                continue
            s = _SCORE.match(t) if cls and rnd else None
            if s:
                out.append(_score_row(cls, rnd, s, url))
                continue
            # Neither a class nor a parsed score. A heading with no digits ends the
            # section at any level. A heading that still contains digits ends it only
            # when it is at the class level or higher; a lower heading (higher number)
            # leaves the class in place.
            if not re.search(r'\d', t) or cls_level is None or level <= cls_level:
                cls = rnd = cls_level = None
            continue
        t = _plain(m.group(3) or '')
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

CHAMP_KEEP_DAYS = 365  # data-kt offset for kept champions; stable so a daily patch is byte-identical (no daily redeploy)
def champs_rolled(G, today, final_date):
    """True once the next HS season has a posted game. That is any schedule row whose date is in a
    later calendar year than the state final (a season runs Aug-Nov inside one year), or any row dated
    today or later that is not a state final (round F). Rows are only ever read, never invented."""
    for g in G.values():
        d = g.get('date') or ''
        if d[:4] > final_date[:4]: return True
        if d >= today and g['round'] != 'F': return True
    return False

def ticker_items(G, fin, pend, winner, today, tab):
    ti = ' tabindex="-1"' if tab else ''
    out = []; ab = {'QF': 'QF', 'SF': 'SF', 'F': 'State final'}
    up = [g for g in G.values() if g['round'] != 'R1' and g.get('home') and g['date'] >= today and g['id'] not in fin and g['id'] not in pend]
    for k in ('6A', '5A'):
        for g in sorted([g for g in up if g['cls'] == k], key=lambda g: (g['date'], ['QF','SF','F'].index(g['round']), g['n'])):
            h, v = g['home']['school'], g['away']['school']
            sep = 'at' if g['round'] == 'QF' else 'vs.'
            pair = f'{html.escape(v)} at {html.escape(h)}' if sep == 'at' else f'{html.escape(h)} vs. {html.escape(v)}'
            aid = hub_aid(g, current=None) or f"hs-{slug(h)}"
            out.append(f'<span data-kt="{kt(g["date"], g["kickoff"])}"><b>{dfmt(g["date"])}</b> · <a class="tml"{ti} href="/high-school/#{aid}">{k} {ab[g["round"]]}: {pair}</a> · {tfmt(g["kickoff"])}</span>')
    order = ['R1', 'QF', 'SF', 'F']
    for k in ('6A', '5A'):
        done = [g for g in G.values() if g['cls'] == k and (g['id'] in fin or g['id'] in pend)]
        if not done: continue
        last = max(order.index(g['round']) for g in done)
        LB = {'R1': 'Final', 'QF': 'QF final', 'SF': 'Semifinal', 'F': 'State final'}
        nxt = [g for g in G.values() if g['cls'] == k and order.index(g['round']) == last + 1]
        exp = kt(min(g['date'] for g in nxt), '18:00') if nxt else kt((datetime.date.fromisoformat(max(g['date'] for g in done)) + datetime.timedelta(days=7)).isoformat(), '18:00')
        # Sourced state finals (round F, in fin) stay up through the offseason. They roll off when the next
        # season's first game is posted (champs_rolled). Earlier rounds, and a final that is only in pend, keep the 7-day rule.
        champs = [g for g in done if g['round'] == 'F' and g['id'] in fin]
        if champs and last == order.index('F'):
            fd = max(g['date'] for g in champs)
            if champs_rolled(G, today, fd): continue
            exp = kt((datetime.date.fromisoformat(fd) + datetime.timedelta(days=CHAMP_KEEP_DAYS)).isoformat(), '18:00')
        elif exp[:10] < today: continue  # expired results are not re-emitted
        for g in sorted([g for g in done if order.index(g['round']) == last], key=lambda g: g['n']):
            if g['id'] not in fin and not pend[g['id']].get('winner'): continue  # unresolved: nothing published
            # Final / SF cards use stable round ids (hs-6a-final), not the winner's QF slug
            anchor = hub_aid(g, current=None) or f"hs-{slug(g['home']['school'] if g['round'] in ('R1','QF') else winner(g['id'])['school'])}"
            if g['id'] in fin:
                f = fin[g['id']]; w = f['home'] if f['home_score'] > f['away_score'] else f['away']; l = f['away'] if w == f['home'] else f['home']
                out.append(f'<span data-kt="{exp}"><b>{k} {LB[g['round']]}</b> · <a class="tml"{ti} href="/high-school/#{anchor}">{html.escape(w)} {max(f["home_score"], f["away_score"])}, {html.escape(l)} {min(f["home_score"], f["away_score"])}</a></span>')
            else:
                out.append(f'<span data-kt="{exp}"><b>{k} {LB[g['round']]}</b> · <a class="tml"{ti} href="/high-school/#{anchor}">{html.escape(pend[g["id"]]["winner"])} advances</a></span>')
    return ''.join(out)

def p_ticker(s, G, fin, pend, winner, today):
    """Fill .tkh even when the morning cleanup left it empty. Previously the regex
    required an existing data-kt child, so a cleared ticker could never be repopulated."""
    def _repl(m):
        hidden = 'aria-hidden' in m.group(1)
        return m.group(1) + ticker_items(G, fin, pend, winner, today, hidden) + '</span>'
    return re.sub(r'(<span class="tkh"[^>]*>)(?:(?:<span data-kt[^>]*>.*?</span>)+)?</span>', _repl, s)

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

CD_BLOCK = re.compile(r'<div class="cd"[^>]*>(?:<div\b[^>]*>(?:(?!</?div\b).)*</div>)*</div>', re.S)

def div_balance(s):
    """Open <div> count minus </div> count; 0 for a well-formed card."""
    return len(re.findall(r'<div\b', s)) - s.count('</div>')

# Presentation for hub cards. Colors are the same approximations already used on the QF cards
# (UHSAA-listed color names). Rice-Eccles lat/lon match the stadium cards on the live site.
RICE_ECCLES = {
    'name': 'Rice-Eccles Stadium',
    'sub': 'University of Utah, Salt Lake City',
    'maps': 'https://www.google.com/maps/search/?api=1&query=Rice-Eccles+Stadium%2C+University+of+Utah%2C+Salt+Lake+City%2C+UT',
    'venue': 'rice-eccles', 'lat': '40.76', 'lon': '-111.8489',
}
# tb, jersey color, ink, bar accent — used when a school is not already on the hub page
HUB_TEAM = {
    'Skyridge':      ('SKY', '#6E7681', '#FFFFFF', '#CC5500'),
    'Corner Canyon': ('CC',  '#1B2A4A', '#FFFFFF', '#A7A9AC'),
    'West':          ('WST', '#D0202E', '#FFFFFF', '#111111'),
    'Orem':          ('ORE', '#2251C2', '#FFFFFF', '#C99700'),
}
_WX = ('<span class="wx" data-wx-state="hidden" data-venue="{venue}" data-lat="{lat}" data-lon="{lon}" '
       'title="Kickoff forecast (National Weather Service)"><svg role="img" aria-label=""><use href="#wx-sun"/>'
       '</svg><span class="t"></span></span>')

def _hub_team(page, school):
    """Abbrev + colors from an existing hub card, else HUB_TEAM, else initials."""
    for m in re.finditer(
        r'<div class="team (away|home)" style="--accent:([^"]+)">(?:(?!</div>).)*?'
        r'<span class="tb">([^<]+)</span><span class="nm">([^<]+)</span>',
        page, re.S):
        if html.unescape(m.group(4)) != school:
            continue
        side, accent, tb = m.group(1), m.group(2), html.unescape(m.group(3))
        # nearest article opening style before this team block
        head = page.rfind('<article ', 0, m.start())
        sm = re.search(r'style="([^"]*)"', page[head:m.start()]) if head >= 0 else None
        color = ink = None
        if sm:
            st = sm.group(1)
            color = re.search(rf'--{side}-color:([^;"]+)', st)
            ink = re.search(rf'--{side}-ink:([^;"]+)', st)
            color = color.group(1) if color else None
            ink = ink.group(1) if ink else None
        fb = HUB_TEAM.get(school, (tb, '#000E28', '#FFFFFF', accent))
        return tb, color or fb[1], ink or fb[2], accent or fb[3]
    fb = HUB_TEAM.get(school)
    if fb:
        return fb
    initials = ''.join(w[0] for w in school.split() if w)[:3].upper() or 'TBD'
    return initials, '#000E28', '#FFFFFF', '#000E28'

def _hub_kick_label(rnd, G):
    lab = {'R1': 'First round', 'QF': 'Quarterfinals', 'SF': 'Semifinals', 'F': 'State finals'}[rnd]
    games = [g for g in G.values() if g['round'] == rnd]
    if not games:
        return f'UHSAA state playoffs · {lab}'
    d = min(g['date'] for g in games)
    return f'UHSAA state playoffs · {lab} {dfmt(d)}'

def render_hub_card(page, g, fin, pend):
    """One .card.mx.c1 article for a hub game, same layout as the existing QF cards."""
    if not g.get('home') or not g.get('away'):
        return None
    home, away = g['home'], g['away']
    ht = _hub_team(page, home['school']); at = _hub_team(page, away['school'])
    aid = hub_aid(g, current=None)
    if not aid:
        return None
    rnd_lab = {'R1': 'First round', 'QF': 'Quarterfinals', 'SF': 'Semifinals', 'F': 'State final'}[g['round']]
    strip = f"{g['cls']} · {rnd_lab}" + (f" · Game {g['n']}" if g['round'] != 'F' else '')
    aria = f"{g['cls']} {rnd_lab.lower()}: No. {away['seed']} {away['school']} at No. {home['seed']} {home['school']}"
    venue = RICE_ECCLES if g['round'] in ('SF', 'F') else None
    if venue:
        where = (f'<div class="where"><b><a href="{html.escape(venue["maps"])}" target="_blank" rel="noopener">'
                 f'{html.escape(venue["name"])}</a></b><br>{html.escape(venue["sub"])}</div>')
        wx = _WX.format(**venue)
    else:
        where = '<div class="where"></div>'
        wx = _WX.format(venue=f"hs-{slug(home['school'])}", lat='', lon='')
    iso = kt(g['date'], g.get('kickoff') or '18:00')
    fid = g['id']
    f = fin.get(fid); p = pend.get(fid)
    def team_div(side, team, look):
        tb, color, ink, accent = look
        ha = 'HOME' if side == 'home' else 'AWAY'
        return (f'<div class="team {side}" style="--accent:{html.escape(accent)}"><span class="ha">{ha}</span>'
                f'<span class="sd">NO. {int(team["seed"])}</span><span class="tb">{html.escape(tb)}</span>'
                f'<span class="nm">{html.escape(team["school"])}</span><span class="bar"></span></div>')
    match = (f'<div class="match">{team_div("away", away, at)}<span class="at">@</span>'
             f'{team_div("home", home, ht)}</div>')
    art_style = (f'--away-color:{html.escape(at[1])};--away-ink:{html.escape(at[2])};'
                 f'--home-color:{html.escape(ht[1])};--home-ink:{html.escape(ht[2])}')
    if f:
        hs, as_ = f['home_score'], f['away_score']
        w = f['home'] if hs > as_ else f['away']
        ab_h, ab_a = ht[0], at[0]
        ab_w = ab_h if w == f['home'] else ab_a
        loser = f['away'] if w == f['home'] else f['home']
        cd = (f'<div class="cd" aria-label="Final: {html.escape(f["away"])} {as_}, {html.escape(f["home"])} {hs}">'
              f'<div class="lbl"><i>FINAL</i></div><div><b>{as_}</b><i>{html.escape(ab_a)}</i></div>'
              f'<div><b>{hs}</b><i>{html.escape(ab_h)}</i></div><div><b>{html.escape(ab_w)}</b><i>WINS</i></div></div>')
        src_name = html.escape(f['source'].split(' (')[0].split(',')[0])
        note = (f'<p class="hsn">Final: {html.escape(w)} {max(hs, as_)}, {html.escape(loser)} {min(hs, as_)}. '
                f'Source: <a href="{html.escape(f["source_url"])}" rel="noopener">{src_name}</a>.</p>')
        state, when = 'final', f'FINAL · {dfmt(g["date"]).upper()} · {tfmt(g.get("kickoff"))}'
    elif p and p.get('winner'):
        w = p['winner']
        ab_w = ht[0] if w == home['school'] else at[0]
        cd = (f'<div class="cd" aria-label="{html.escape(w)} advanced; final score pending">'
              f'<div class="lbl"><i>FINAL</i></div><div><b>{html.escape(ab_w)}</b><i>ADVANCES</i></div>'
              f'<div><b>&ndash;</b><i>SCORE</i></div><div><b>&ndash;</b><i>PENDING</i></div></div>')
        note = f'<p class="hsn">{html.escape(w)} advanced. We post the final score once sources agree.</p>'
        state, when = 'final', f'FINAL · {dfmt(g["date"]).upper()} · {tfmt(g.get("kickoff"))}'
    else:
        cd = ('<div class="cd" aria-label="Kickoff time"><div class="lbl"><i>KICKOFF<br>IN</i></div>'
              '<div><b>&ndash;</b><i>DAYS</i></div><div><b>&ndash;</b><i>HRS</i></div>'
              '<div><b>&ndash;</b><i>MIN</i></div></div>')
        note = '<p class="hsn">Finals only. We post the score with a source once the game is final.</p>'
        state, when = 'upcoming', f'{dfmt(g["date"]).upper()} · {tfmt(g.get("kickoff"))}'
    # State-final hash target is a sentinel before the h2, so the heading
    # stays clear of the sticky header. The article must not reuse that id.
    id_attr = '' if g['round'] == 'F' else f'id="{html.escape(aid)}" '
    return (
        f'<article {id_attr}class="card mx c1" data-theme="grey-mid" data-level="hs" '
        f'data-game-state="{state}" data-kickoff="{html.escape(iso)}" style="{art_style}" '
        f'aria-label="{html.escape(aria)}"><div class="strip"><span class="rnd">{html.escape(strip)}</span></div>'
        f'<div class="inner"><div class="meta"><span class="when"><span class="kt">{html.escape(when)}</span></span>'
        f'{wx}</div>{match}<div class="facts">{where}{cd}</div>{note}'
        f'<div class="foot"><span class="brand">MTN SPORTS MEDIA</span></div></div></article>'
    )

def _set_hub_panel(s, cls, heading, cards_html):
    """Replace the heading + .hsg.c1w grid inside #hub-6a / #hub-5a; leave the hsnote alone."""
    mark = f'id="hub-{cls.lower()}"'
    i = s.find(mark)
    if i < 0:
        return s, False
    h2 = s.find('<h2 class="hsh">', i)
    grid = s.find('<div class="hsg c1w">', h2 if h2 >= 0 else i)
    note = s.find('<p class="hsnote">', grid if grid >= 0 else i)
    if h2 < 0 or grid < 0 or note < 0 or not (i < h2 < grid < note):
        return s, False
    close = s.rfind('</div>', grid, note)
    if close < 0:
        return s, False
    # Include a previously injected jump sentinel so a second pass is a no-op.
    start = h2
    sent = s.rfind('<span ', i, h2)
    if sent >= 0 and 'class="hs-jump"' in s[sent:h2] and 'id="hs-' in s[sent:h2]:
        start = sent
    new = heading + '<div class="hsg c1w">' + cards_html + '</div>'
    return s[:start] + new + s[close + 6:], True

def p_hub(s, G, fin, pend, today=None):
    """Patch hub cards. Default: current round only (Creative). When that round is the
    state final and the live HTML still has quarterfinal cards, rewrite the .c1w grids
    so a later cron run cannot revert them. HUB_INCLUDE_LATER_ROUNDS=1 patches all present."""
    n = 0
    cur = None if HUB_INCLUDE_LATER_ROUNDS else current_hub_round(G, fin, pend, today)
    if cur == 'F':
        for cls in ('6A', '5A'):
            games = [g for g in G.values() if g['cls'] == cls and g['round'] == 'F']
            cards = []
            for g in sorted(games, key=lambda x: x['n']):
                c = render_hub_card(s, g, fin, pend)
                if c:
                    cards.append(c); n += 1
            if not cards:
                continue
            heading = (
                f'<span id="hs-{cls.lower()}-final" class="hs-jump" aria-hidden="true"></span>'
                f'<h2 class="hsh">{cls} <em>state final</em></h2>'
            )
            s, ok = _set_hub_panel(s, cls, heading, ''.join(cards))
            if not ok:
                continue
        s2, k = re.subn(r'<span class="kick">[^<]*</span>',
                         f'<span class="kick">{html.escape(_hub_kick_label("F", G))}</span>', s, count=1)
        if k:
            s = s2
        return s, n
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
        # Replace the whole countdown block: its child divs hold no nested divs, so match
        # each child through its own </div> and then the block's closing </div>.
        # (The old lazy '.*?</div>(?=</div>)' stopped one </div> short and left a stray
        # closing tag per final card, which broke the card wrapper at 320px.)
        a = CD_BLOCK.sub(lambda _m: cd, a, count=1)
        a = re.sub(r'<div class="tix".*?</div><p class="hsw">.*?</p>', '', a, count=1)
        a = re.sub(r'<p class="hsn">.*?</p>', note, a, count=1)
        s = s[:i] + a + s[j:]; n += 1
    return s, n


# Later-pass hub polish (names, hash nav, leftover QF anchors). Kept in the
# generator so a cron run cannot drop the CSS or restore dead R1/QF hrefs.
POLISH_STYLE_ID = 'hs-polish'
POLISH_CSS = (
    # Full school names wrap on narrow hub cards (320–390) instead of ellipsizing.
    '.hs .c1w .mx .team .nm{white-space:normal;overflow:visible;text-overflow:clip;'
    'overflow-wrap:break-word;line-height:1.15;min-width:0;max-width:100%}'
    # Sticky .top header (~67px phone, ~79px desktop) must not cover a 6A/5A
    # heading, tab, or card when the page jumps to a hash.
    '.hs #hub-6a,.hs #hub-5a,.hs #hs-6a-final,.hs #hs-5a-final,.hs .hs-jump,'
    '.hs .hstabs,.hs #hubt-6a,.hs #hubt-5a,'
    '.hs #st-6a,.hs #st-5a,.hs #stt-6a,.hs #stt-5a,'
    '.hs [id="6a"],.hs [id="5a"],.hs .hs-frag{scroll-margin-top:96px}'
    # UP NEXT pill mask: width matches the navy pill (~67px border-box), not the
    # 84px text inset, and uses ticker navy so it cannot cover "6A STATE F".
    'html body .ticker[data-lvl=hs]>.tkmask{position:absolute;z-index:1;left:0;top:0;bottom:0;width:67px;'
    'background:#000e28;pointer-events:none}'
)

def p_polish(s):
    """Inject or refresh the later-pass style block on an HS page."""
    style = f'<style id="{POLISH_STYLE_ID}">{POLISH_CSS}</style>'
    s2, n = re.subn(r'<style id="%s"[^>]*>.*?</style>' % POLISH_STYLE_ID, style, s, count=1, flags=re.S)
    if n:
        return s2, s2 != s
    if '</head>' in s:
        return s.replace('</head>', style + '\n</head>', 1), True
    return s, False

def p_ticker_mask(s):
    """Add a left-edge mask sibling inside the HS ticker, once."""
    if re.search(r'class="tkmask"', s):
        return s, False
    s2, n = re.subn(
        r'(<div class="ticker"[^>]*data-lvl="hs"[^>]*>)',
        r'\1<span class="tkmask" aria-hidden="true"></span>',
        s, count=1)
    return s2, bool(n)

def hub_slug_targets(G, fin, pend, today):
    """Map a school slug to a live hub hash (current-round card, else class section)."""
    cur = current_hub_round(G, fin, pend, today)
    m = {}
    for g in G.values():
        for side in ('home', 'away'):
            t = g.get(side)
            if t:
                m[slug(t['school'])] = f'hub-{g["cls"].lower()}'
    for g in G.values():
        if g.get('round') != cur:
            continue
        aid = hub_aid(g, current=None)
        if not aid:
            continue
        for side in ('home', 'away'):
            t = g.get(side)
            if t:
                m[slug(t['school'])] = aid
    return m

def p_hub_hrefs(s, G, fin, pend, today):
    """Retarget leftover hub anchors by the school named in the <a>, not the old href slug."""
    targets = hub_slug_targets(G, fin, pend, today)
    def repl(mm):
        inner = mm.group('inner')
        nm = re.search(r'<span class="nm">([^<]+)</span>', inner)
        if not nm:
            # Ticker lines have no .nm; leave their already-correct hashes alone.
            return mm.group(0)
        dest = targets.get(slug(html.unescape(nm.group(1))))
        if not dest:
            return mm.group(0)
        return f'<a{mm.group("pre")}href="{mm.group("prefix")}#{dest}"{mm.group("post")}>{inner}</a>'
    return re.subn(
        r'<a(?P<pre>\s[^>]*?)href="(?P<prefix>/high-school/?)#hs-(?P<sl>[a-z0-9-]+)"(?P<post>[^>]*)>(?P<inner>.*?)</a>',
        repl, s, flags=re.S)

HASHNAV_OLD = "var h=location.hash.slice(1).toLowerCase();show(h==='5a'?'5a':'6a',false)})();"
HASHNAV_NEW = (
    "function tabOf(h){h=(h||'').replace(/^#/,'').toLowerCase();"
    "return /(?:^|-)5a(?:-|$)/.test(h)?'5a':'6a'}"
    "function goHash(){var raw=location.hash.slice(1),k=tabOf(raw);show(k,false);"
    "var el=raw&&document.getElementById(raw);if(el)el.scrollIntoView({block:'start',behavior:'auto'})}"
    "goHash();addEventListener('hashchange',goHash)})();"
)

def p_hashnav(s):
    """Select the 5A tab for #hs-5a-final / #hub-5a / #5a, then honor scroll-margin."""
    if HASHNAV_NEW in s:
        return s, False
    if HASHNAV_OLD in s:
        return s.replace(HASHNAV_OLD, HASHNAV_NEW, 1), True
    return s, False

def p_standings_frag_ids(s):
    """Give ?view=bracket#6a / #5a a real id on the standings panels."""
    n = 0
    for cls in ('6a', '5a'):
        # Must match a real tag, not the polish CSS `[id="6a"]` selector.
        if re.search(r'<span id="%s" class="hs-frag"' % cls, s):
            continue
        s2, c = re.subn(
            r'(<section class="hsp" id="st-%s"[^>]*>)' % cls,
            r'\1<span id="%s" class="hs-frag" aria-hidden="true"></span>' % cls,
            s, count=1)
        if c:
            s = s2
            n += 1
    return s, n

def hs_inpage_ids(html):
    """Id attributes on real tags only — ignore CSS selectors and script strings."""
    cut = re.sub(r'<style\b[^>]*>.*?</style>', ' ', html, flags=re.S | re.I)
    cut = re.sub(r'<script\b[^>]*>.*?</script>', ' ', cut, flags=re.S | re.I)
    ids = set()
    for tag in re.findall(r'<[^>]+>', cut):
        if tag.startswith('</') or tag.startswith('<!'):
            continue
        m = re.search(r'\bid=["\']([^"\']+)["\']', tag)
        if m:
            ids.add(m.group(1))
    return ids

def unresolved_hs_hashes(pages):
    """pages: dict of url path -> html. Returns leftover in-site hashes that do not resolve."""
    missing = []
    for src, html in pages.items():
        for href in re.findall(r'href="([^"]*#[^"]+)"', html):
            if href.startswith('http') and 'mtnsportsmedia.com' not in href and 'ksl.com' not in href and 'google.com' not in href:
                continue
            if href.startswith('https://') and '/high-school' not in href:
                continue
            if '#' not in href:
                continue
            path, frag = href.split('#', 1)
            path = path.split('?')[0]
            if href.startswith('#'):
                dest = src
                frag = href[1:]
            elif path.startswith('/high-school') or path == '':
                if path in ('', '/high-school', '/high-school/'):
                    dest = 'high-school/index.html'
                elif path.rstrip('/').endswith('standings'):
                    dest = 'high-school/standings/index.html'
                elif path.rstrip('/').endswith('recruiting'):
                    dest = 'high-school/recruiting/index.html'
                else:
                    dest = path.lstrip('/')
                    if dest.endswith('/'):
                        dest += 'index.html'
                frag = frag
            else:
                continue
            if frag.startswith('wx-'):
                continue  # svg sprites on the same page
            html_dest = pages.get(dest)
            if html_dest is None:
                missing.append((src, href, 'no-page'))
                continue
            if frag not in hs_inpage_ids(html_dest):
                missing.append((src, href, frag))
    return missing

PAGES = ['high-school/index.html', 'high-school/standings/index.html', 'high-school/recruiting/index.html']
def patch_site(root, sched, scores, today):
    G, fin, pend, winner = resolve(sched, scores); rep = {}
    for f in PAGES:
        p = f'{root}/{f}'; s0 = s = open(p, encoding='utf-8').read()
        s = p_ticker(s, G, fin, pend, winner, today)
        s, _ = p_ticker_mask(s)
        # Frag ids before p_polish so the CSS `[id="6a"]` cannot satisfy the existence check.
        if f == PAGES[1]:
            s, _ = p_standings_frag_ids(s)
        s, _ = p_polish(s)
        s, _ = p_hashnav(s)
        s, n_href = p_hub_hrefs(s, G, fin, pend, today)
        if f == PAGES[0]: s, rep['hub'] = p_hub(s, G, fin, pend, today)
        if f == PAGES[1]:
            s, rep['bracket'] = p_bracket(s, G, fin, pend)
        if s != s0: open(p, 'w', encoding='utf-8').write(s)
        rep[f] = s != s0
        if n_href:
            rep.setdefault('hrefs', 0)
            rep['hrefs'] += n_href
    return rep
