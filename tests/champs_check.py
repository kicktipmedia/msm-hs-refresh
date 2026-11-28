"""Offline checks: sourced 6A/5A state finals stay on the HS ticker through the offseason.
They roll off once the next season has a posted game. Earlier rounds keep the 7-day rule.
When the ticker shows only those state finals, the pill reads STATE CHAMPS; otherwise UP NEXT."""
import copy, datetime, json, re, shutil, sys, tempfile
from pathlib import Path

C6 = '<b>6A State final</b> · <a class="tml" href="/high-school/#hs-6a-final">Corner Canyon 45, Skyridge 44</a>'
C5 = '<b>5A State final</b> · <a class="tml" href="/high-school/#hs-5a-final">West 30, Orem 21</a>'

def pill_css(html):
    m = re.search(r'<style id="hs-polish"[^>]*>(.*?)</style>', html, re.S)
    return m.group(1) if m else ''

def pill_label(html):
    return 'STATE CHAMPS' if 'content:"STATE CHAMPS"' in pill_css(html) else 'UP NEXT'

def main(root):
    root = Path(root)
    sys.path.insert(0, str(root / "tools"))
    import hs
    sched0 = json.load(open(root / "data/hs_schedule.json"))
    scores0 = json.load(open(root / "data/hs_scores.json"))

    def items(today, sched=None, scores=None):
        sched = sched or sched0; scores = scores or scores0
        G, fin, pend, win = hs.resolve(copy.deepcopy(sched), copy.deepcopy(scores))
        return hs.ticker_items(G, fin, pend, win, today, False)

    def resolved(today, sched=None, scores=None):
        sched = sched or sched0; scores = scores or scores0
        return hs.resolve(copy.deepcopy(sched), copy.deepcopy(scores))

    # 1. Champions are shown on Nov 28 and Dec 15 (no next-season game), same markup, copy and links as before.
    for today in ("2026-11-28", "2026-12-15", "2027-03-01"):
        h = items(today)
        assert C6 in h and C5 in h, (today, h)
        assert h.count('<span data-kt=') == 2, (today, h)
        # data-kt must be in the future, or hs-ticker.js (removes items 3h past data-kt) would hide them client-side.
        for kt in re.findall(r'data-kt="([^"]+)"', h):
            end = datetime.datetime.fromisoformat(kt) + datetime.timedelta(hours=3)
            now = datetime.datetime.fromisoformat(today + "T23:59:00").replace(tzinfo=hs.MT)
            assert end > now, (today, kt)
        assert not re.search(r'(?i)\b(bet|betting|wager|parlay|odds|pick|favored|predict|should|market)\b', h)
        assert not re.search(r'[\U0001F300-\U0001FAFF\u2600-\u27BF]', h)
        G, fin, pend, win = resolved(today)
        assert hs.ticker_pill_label(G, fin, pend, win, today) == hs.PILL_CHAMPS, today
    # stable: identical bytes on consecutive days so the daily cron does not redeploy
    assert items("2026-11-28") == items("2026-11-29") == items("2026-12-15")
    # Pill override is HS-specific and does not edit the shared ticker-pill-v2.css the cron does not own.
    css = hs.polish_css(hs.PILL_CHAMPS)
    assert 'html body .ticker[data-lvl=hs]::before{content:"STATE CHAMPS"}' in css
    assert f'>.tkmask{{width:{hs.PILL_CHAMPS_MASK_PX}px}}' in css
    assert f'>div{{padding-left:{hs.PILL_CHAMPS_PAD_PX}px}}' in css
    assert not re.search(r'(?i)\b(bet|betting|wager|parlay|odds|pick|favored|predict|should|market)\b', css)
    # Default polish (UP NEXT) stays byte-identical to POLISH_CSS so T1 / non-champs patches are no-ops.
    assert hs.polish_css() == hs.POLISH_CSS
    assert hs.polish_css(hs.PILL_UP) == hs.POLISH_CSS
    assert 'STATE CHAMPS' not in hs.POLISH_CSS

    # 2. Rolled off once a next-season game is posted.
    nxt = copy.deepcopy(sched0)
    nxt['games'].append(dict(id='6A-R1-1x', cls='6A', round='R1', n=1, date='2027-08-27', kickoff='19:00', site='TBA',
                             home={'seed': 1, 'school': 'Skyridge'}, away={'seed': 16, 'school': 'Riverton'}, status='scheduled'))
    for today in ("2026-12-15", "2027-08-20", "2027-08-27"):
        assert items(today, sched=nxt) == '', today   # a later-season row is enough, even before its date
        G, fin, pend, win = resolved(today, nxt)
        assert hs.ticker_pill_label(G, fin, pend, win, today) == hs.PILL_UP
    # a row dated today or later that is not a state final rolls them off ...
    same = copy.deepcopy(sched0)
    same['games'].append(dict(id='6A-QF-9', cls='6A', round='QF', n=9, date='2026-12-15', kickoff='19:00', site='TBA',
                              home=None, away=None, status='tba'))
    assert items('2026-12-15', sched=same) == ''
    G, fin, pend, win = resolved('2026-12-15', same)
    assert hs.ticker_pill_label(G, fin, pend, win, '2026-12-15') == hs.PILL_UP
    # ... but a state final dated in the future is not a next-season game.
    fin_row = copy.deepcopy(sched0)
    for g in fin_row['games']:
        if g['id'] == '6A-F': g['date'] = '2026-12-20'
    h = items('2026-12-15', sched=fin_row)
    assert C5 in h and 'Corner Canyon 45, Skyridge 44' in h, h

    # 3. Non-state-final rounds keep the 7-day rule and the UP NEXT pill.
    qf = copy.deepcopy(sched0); qf['games'] = [g for g in qf['games'] if g['round'] in ('R1', 'QF')]
    qs = copy.deepcopy(scores0); qs['finals'] = [f for f in qs['finals'] if f.get('rid') in (None, 'R1', 'QF')]
    h = items('2026-11-12', qf, qs)
    assert 'QF final' in h, h
    assert items('2026-11-14', qf, qs) == '', items('2026-11-14', qf, qs)
    G, fin, pend, win = resolved('2026-11-12', qf, qs)
    assert hs.ticker_pill_label(G, fin, pend, win, '2026-11-12') == hs.PILL_UP
    G, fin, pend, win = resolved('2026-11-14', qf, qs)
    assert hs.ticker_pill_label(G, fin, pend, win, '2026-11-14') == hs.PILL_UP  # empty ticker
    # a state final that is only a hand-held pending winner (not sourced) is not kept
    ps = copy.deepcopy(scores0)
    ps['finals'] = [f for f in ps['finals'] if f.get('rid') != 'F']
    ps['pending'] = [dict(**{'class': c, 'rid': 'F', 'round': 'Final', 'game': 1, 'home': h_, 'away': a_, 'winner': h_, 'hold': True}) for c, h_, a_ in (('6A', 'Corner Canyon', 'Skyridge'), ('5A', 'West', 'Orem'))]
    assert 'advances' in items('2026-11-27', scores=ps)
    assert items('2026-11-28', scores=ps) == ''

    # 4. patch_site on the live-lineage pages: restores the champions and STATE CHAMPS pill, then is a no-op the next day.
    td = Path(tempfile.mkdtemp(prefix="champs-"))
    try:
        shutil.copytree(root / "site", td / "site")
        pages = [td / "site" / p for p in hs.PAGES]
        for p in pages:   # simulate the emptied ticker shipped on Nov 28
            s = p.read_text(encoding="utf-8")
            s = re.sub(r'(<span class="tkh"[^>]*>)(?:<span data-kt.*?</span>)*</span>', r'\1</span>', s)
            p.write_text(s, encoding="utf-8")
        hs.patch_site(str(td / "site"), copy.deepcopy(sched0), copy.deepcopy(scores0), "2026-11-28")
        for p in pages:
            s = p.read_text(encoding="utf-8")
            assert C6 in s and C5 in s, p
            assert pill_label(s) == 'STATE CHAMPS', p
            css = pill_css(s)
            assert f'width:{hs.PILL_CHAMPS_MASK_PX}px' in css and f'padding-left:{hs.PILL_CHAMPS_PAD_PX}px' in css
            assert 'ticker-pill-v2.css' in s  # shared sheet unchanged; HS rule wins by specificity
        before = [p.read_bytes() for p in pages]
        rep = hs.patch_site(str(td / "site"), copy.deepcopy(sched0), copy.deepcopy(scores0), "2026-11-29")
        assert [p.read_bytes() for p in pages] == before and not any(rep[x] for x in hs.PAGES), rep
        assert rep.get('pill') == hs.PILL_CHAMPS
        # Next-season row: ticker clears and the polish override is removed (back to UP NEXT).
        hs.patch_site(str(td / "site"), copy.deepcopy(nxt), copy.deepcopy(scores0), "2026-12-15")
        for p in pages:
            s = p.read_text(encoding="utf-8")
            assert C6 not in s and pill_label(s) == 'UP NEXT', p
            assert 'content:"STATE CHAMPS"' not in pill_css(s)
            assert 'width:67px' in pill_css(s)
    finally:
        shutil.rmtree(td, ignore_errors=True)
    print("ok")

if __name__ == "__main__":
    main(sys.argv[1])
