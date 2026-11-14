#!/usr/bin/env python3
"""MSM HS refresh orchestrator. Exit codes: 0 ok/skip, 12 guard mismatch, 13 stale base, 14 diff scope, 15 deploy fail, 16 verify fail (rolled back, hold set), 17 rollback failed/unconfirmed (hold set), 18 production refused: hold set."""
import argparse, json, os, sys, shutil, hashlib, filecmp, subprocess, datetime, re, urllib.request
sys.path.insert(0, os.path.dirname(__file__)); import hs
ap = argparse.ArgumentParser()
ap.add_argument('--target', choices=['none', 'preview', 'production'], default='none')
ap.add_argument('--event', default='dispatch'); ap.add_argument('--force', action='store_true')
ap.add_argument('--ignore-window', action='store_true'); ap.add_argument('--now')
ap.add_argument('--fixture', action='append', help='local HTML file standing in for a KSL roundup (tests)')
ap.add_argument('--root', default='.'); ap.add_argument('--out', default='out')
ap.add_argument('--preview-branch', default='hs-auto')
A = ap.parse_args()
R = A.root; ACCT = os.environ.get('CLOUDFLARE_ACCOUNT_ID', ''); PROJ = 'mountaingridiron'
now = datetime.datetime.fromisoformat(A.now).astimezone(hs.MT) if A.now else datetime.datetime.now(hs.MT)
today = now.date().isoformat()
rep = dict(now=now.isoformat(timespec='minutes'), target=A.target, event=A.event, steps=[], issues=[])
def log(*a):
    m = ' '.join(str(x) for x in a); print(m, flush=True); rep['steps'].append(m)
def finish(code, status):
    rep['status'] = status; rep['exit'] = code
    json.dump(rep, open(os.path.join(R, 'report.json'), 'w'), indent=1)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        open(os.environ['GITHUB_STEP_SUMMARY'], 'a').write(f"## HS refresh: {status}\n\n```\n" + '\n'.join(rep['steps']) + '\n```\n')
    sys.exit(code)
J = lambda p: json.load(open(os.path.join(R, p)))
sched, scores, state = J('data/hs_schedule.json'), J('data/hs_scores.json'), J('state.json')
dates = {g['date'] for g in sched['games']}
import copy; state0 = copy.deepcopy(state)  # on-disk state at start; failure paths write only hold onto this

# 0. production hold (set on exit 16/17; cleared by hand, see README "Clearing the hold")
if A.target == 'production' and state.get('hold'):
    log('HOLD SET -> refusing production deploy', json.dumps(state['hold']))
    rep['issues'].append({'title': 'HS refresh: production on HOLD', 'body': 'state.json has a hold from a failed production verify/rollback. Check live, then clear by hand (README: Clearing the hold).\n\n' + json.dumps(state['hold'], indent=1)})
    finish(18, 'fail-hold')
def set_hold(code, why):
    h = dict(code=code, reason=why, at=rep['now'], live_id_expected=state0.get('live_id'))
    state0['hold'] = h; json.dump(state0, open(os.path.join(R, 'state.json'), 'w'), indent=1); log('HOLD SET', json.dumps(h))

# 1. window gate (scheduled runs only)
if A.event == 'schedule' and not A.ignore_window:
    hm = now.hour * 60 + now.minute; yday = (now.date() - datetime.timedelta(days=1)).isoformat()
    daily = now.hour == 7
    night = (today in dates and hm >= 18 * 60) or (yday in dates and hm <= 30)
    if not (daily or night): log(f'outside window ({now:%a %H:%M} MT); game days {sorted(d for d in dates if d >= today)[:3]}'); finish(0, 'skip-window')
    log('window', 'daily-7am' if daily else 'game-night')

# 2. fetch allowed sources
cands, srcsig = [], []
if A.fixture:
    for f in A.fixture:
        page = open(f, encoding='utf-8').read(); u = 'fixture://' + os.path.basename(f)
        c = hs.parse_ksl(page, u); cands += c; srcsig.append([u, c])
else:
    idx = hs.get('https://sports.ksl.com/prep/')
    for u in hs.ksl_discover(idx):
        c = hs.parse_ksl(hs.get(u), u); cands += c; srcsig.append([u, c])
log(f'sources: {len(srcsig)} pages, {len(cands)} score lines')

# 3. cheap skip
ih = hashlib.sha256(json.dumps([srcsig, scores, sched, state.get('live_id')], sort_keys=True).encode()).hexdigest()
rep['input_hash'] = ih
if ih == state.get('input_hash') and not A.force: log('inputs unchanged since last run -> skip'); finish(0, 'skip-unchanged')

# 4. merge
new, conflicts, unmatched = hs.merge(sched, scores, cands, today)
G, fin, pend, _ = hs.resolve(sched, scores)
for n in new: scores['finals'].append(n); log('NEW FINAL', n['class'], n['round'], n['game'], f"{n['away']} {n['away_score']} at {n['home']} {n['home_score']}", n['source_url'])
for c in conflicts:
    cls, rid, *rest = c['id'].split('-'); g = G[c['id']]
    if c['id'] not in pend and c['kind'] != 'disagrees with posted final':
        scores.setdefault('pending', []).append({'class': cls, 'rid': rid, 'round': hs.RNAME[rid], 'game': g['n'], 'home': g['home']['school'], 'away': g['away']['school'], 'winner': None, 'hold': True, 'note': f"auto: {c['kind']}: {c['seen']} from {c.get('sources')}"})
    rep['issues'].append({'title': f"HS pending: {c['id']} {c['kind']}", 'body': json.dumps(c, indent=1) + '\n\nResolve by hand in data/hs_scores.json (allowed sources only: UHSAA, school athletics, KSL), then remove the pending entry.'})
    log('CONFLICT -> pending', c['id'], c['kind'], c['seen'])
G, fin, pend, _ = hs.resolve(sched, scores)
# morning: finished games with no final
if now.hour >= 7:
    for g in G.values():
        if g.get('home') and g['date'] < today and g['id'] not in fin and g['id'] not in pend and not any(n for n in new if f"{n['class']}-{n['rid']}-{n['game']}" == g['id']):
            rep['issues'].append({'title': f"HS pending: {g['id']} no sourced final yet", 'body': f"{g['away']['school']} at {g['home']['school']} ({g['date']}) has no final in KSL roundups. Enter by hand from an allowed source."})
            log('MISSING', g['id'])
json.dump(scores, open(os.path.join(R, 'data/hs_scores.json'), 'w'), indent=1)

# 5. patch copy of live base
out = os.path.join(R, A.out); shutil.rmtree(out, ignore_errors=True); shutil.copytree(os.path.join(R, 'site'), out)
pr = hs.patch_site(out, sched, scores, today); log('patch', pr)
if os.environ.get('HS_MOCK'):  # test hook: simulate a patch step that drops a file
    for d in json.load(open(os.environ['HS_MOCK'])).get('delete', []): os.remove(os.path.join(out, d))
changed = []
for d, _, fs in os.walk(out):
    for f in fs:
        p = os.path.join(d, f); rel = os.path.relpath(p, out); b = os.path.join(R, 'site', rel)
        if not os.path.exists(b) or not filecmp.cmp(p, b, shallow=False): changed.append(rel)
for d, _, fs in os.walk(os.path.join(R, 'site')):  # deletions count as changes too
    for f in fs:
        rel = os.path.relpath(os.path.join(d, f), os.path.join(R, 'site'))
        if not os.path.exists(os.path.join(out, rel)): changed.append(rel); log('DELETED', rel)
rep['changed'] = sorted(changed); log('changed files', changed)
if any(not c.startswith('high-school/') for c in changed): log('DIFF SCOPE VIOLATION'); finish(14, 'fail-diff-scope')
state['input_hash'] = ih; state['last_run'] = rep['now']
def save_state(): json.dump(state, open(os.path.join(R, 'state.json'), 'w'), indent=1)
if not changed and not A.force: save_state(); log('no site change -> skip deploy'); finish(0, 'skip-nochange')
if A.target == 'none': log('dry run: not deploying'); finish(0, 'dry-run')

# 6. guard
TOK = os.environ.get('CLOUDFLARE_API_TOKEN')
MOCK = json.load(open(os.environ['HS_MOCK'])) if os.environ.get('HS_MOCK') else None  # offline tests only
_cseq = list(MOCK.get('canon', [])) if MOCK else []
def cf(path, method='GET'):
    if MOCK is not None:
        if path.endswith('/rollback'):
            if MOCK.get('rollback_raises'): raise RuntimeError('mock rollback error')
            return {}
        return {'canonical_deployment': {'id': _cseq.pop(0) if len(_cseq) > 1 else _cseq[0]}}
    return _cf(path, method)
def _cf(path, method='GET'):
    r = urllib.request.Request(f'https://api.cloudflare.com/client/v4/accounts/{ACCT}/pages/projects/{PROJ}{path}', method=method, headers={'Authorization': f'Bearer {TOK}'})
    return json.load(urllib.request.urlopen(r, timeout=60))['result']
canon = cf('')['canonical_deployment']['id']; rep['guard'] = canon
if canon != state['live_id']:
    rep['issues'].append({'title': 'HS refresh: live changed outside the HS job (guard mismatch)', 'body': f'canonical {canon} != recorded {state["live_id"]}. Re-sync site/ from the new live lineage and update state.json live_id.'})
    log('GUARD MISMATCH', canon, state['live_id']); finish(12, 'fail-guard')
UA = {'User-Agent': 'Mozilla/5.0 MSM-HS-Refresh'}
def fetch(u):
    if MOCK is not None:
        rel = u.split('://', 1)[1].split('/', 1)[1].split('?')[0]; rel = (rel + 'index.html') if (rel == '' or rel.endswith('/')) else rel
        if MOCK.get('verify_bad') and MOCK.get('_deployed'): return b'BAD'
        return open(os.path.join(R, 'site', rel), 'rb').read()
    return _fetch(u)
def _fetch(u): return urllib.request.urlopen(urllib.request.Request(u + ('&' if '?' in u else '?') + 'cb=' + str(os.getpid()), headers=UA), timeout=60).read()
BEACON = re.compile(rb'<!-- Cloudflare Pages Analytics -->|<script[^>]*static\.cloudflareinsights\.com[^>]*>\s*</script>\n?(<!-- Cloudflare Pages Analytics -->)?', re.S)
def norm(b): return hs.strip_cf_email(BEACON.sub(b'', b))  # CF edge injects analytics beacon + email obfuscation (decoder script, __cf_email__ / data-cfemail)
def same(local, remote): return norm(open(local, 'rb').read()) == norm(remote)
for rel in ('high-school/index.html', 'high-school/standings/index.html', 'index.html'):
    if not same(os.path.join(R, 'site', rel), fetch('https://mtnsportsmedia.com/' + rel.replace('index.html', ''))):
        log('STALE BASE', rel); rep['issues'].append({'title': 'HS refresh: repo base differs from live', 'body': rel}); finish(13, 'fail-stale-base')
log('guard ok', canon, '+ base == live')

# 7. deploy
br = 'main' if A.target == 'production' else A.preview_branch
def wrangler():
    if MOCK is not None:
        MOCK['_deployed'] = True; d = MOCK.get('deploy', {})
        return subprocess.CompletedProcess([], d.get('rc', 0), d.get('out', 'https://abcdef12.' + PROJ + '.pages.dev'), '')
    return subprocess.run(['wrangler', 'pages', 'deploy', out, '--project-name', PROJ, '--branch', br, '--commit-dirty=true'], capture_output=True, text=True)
def rollback_confirm(why):
    """Roll production back to the pre-deploy canonical and re-read it. Exits 17 (hold set) on any error or mismatch."""
    try:
        cf(f'/deployments/{canon}/rollback', 'POST'); now_id = cf('')['canonical_deployment']['id']
    except Exception as e:
        now_id = None; err = f'{type(e).__name__}: {e}'
    else:
        err = None if now_id == canon else f'canonical after rollback {now_id} != pre-deploy {canon}'
    rep['rollback'] = dict(target=canon, after=now_id, error=err)
    if err:
        log('ROLLBACK FAILED', err)
        rep['issues'].append({'title': 'PRODUCTION ROLLBACK FAILED', 'body': f'Reason for rollback: {why}\nError: {err}\nPre-deploy canonical: {canon}\nRoll back by hand in Cloudflare Pages (mountaingridiron) now.'})
        set_hold(17, why + ' / ' + err); finish(17, 'fail-rollback')
    log('ROLLED BACK to', canon, 'confirmed')
p = wrangler()
print(p.stdout[-1500:], p.stderr[-1500:])
m = re.search(r'https://([0-9a-f]{8})\.' + PROJ + r'\.pages\.dev', p.stdout + p.stderr)
if p.returncode or not m:
    log('DEPLOY FAILED rc', p.returncode)
    if A.target == 'production':
        try: after = cf('')['canonical_deployment']['id']
        except Exception as e: after = f'unknown ({type(e).__name__})'
        if after != canon:
            log('canonical changed despite deploy failure', after); rollback_confirm(f'wrangler failed but canonical moved to {after}')
            rep['issues'].append({'title': 'HS refresh: production deploy failed after creating a deployment, rolled back', 'body': after}); set_hold(15, 'deploy failed, rolled back')
    finish(15, 'fail-deploy')
rep['deploy_url'] = m.group(0); log('deployed', m.group(0), 'branch', br)
hosts = ['https://mtnsportsmedia.com', 'https://www.mtnsportsmedia.com'] if A.target == 'production' else [m.group(0), f'https://{br}.{PROJ}.pages.dev']

# 8. verify: bytecmp + smoke
import time; time.sleep(8); bad = []
for h in hosts:
    for rel in sorted(set(changed) | {'index.html'}):
        if not rel.endswith('.html'): continue
        if not same(os.path.join(out, rel), fetch(h + '/' + rel.replace('index.html', ''))): bad.append(h + '/' + rel)
log('bytecmp', 'ok' if not bad else bad)
sm = subprocess.CompletedProcess([], MOCK.get('smoke_rc', 0), 'mock smoke', '') if MOCK is not None else subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'smoke.py'), hosts[0]], capture_output=True, text=True)
print(sm.stdout[-3000:], sm.stderr[-1500:]); log('smoke', 'ok' if sm.returncode == 0 else 'FAIL')
if bad or sm.returncode:
    if A.target == 'production':
        rollback_confirm('production verify failed')
        set_hold(16, 'production verify failed, rolled back')
        rep['issues'].append({'title': 'HS refresh: production verify failed, rolled back', 'body': json.dumps({'bad': bad, 'smoke': sm.stdout[-1500:]}, indent=1)})
    finish(16, 'fail-verify')
if A.target == 'production':
    state['live_id'] = cf('')['canonical_deployment']['id']; shutil.rmtree(os.path.join(R, 'site')); shutil.copytree(out, os.path.join(R, 'site'))
    log('new live', state['live_id'], 'base updated')
    save_state()
finish(0, 'deployed-' + A.target)
