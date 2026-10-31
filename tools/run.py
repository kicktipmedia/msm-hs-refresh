#!/usr/bin/env python3
"""MSM HS refresh orchestrator. Exit codes: 0 ok/skip, 12 guard mismatch, 13 stale base, 14 diff scope, 15 deploy fail, 16 verify fail (rolled back)."""
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
changed = []
for d, _, fs in os.walk(out):
    for f in fs:
        p = os.path.join(d, f); rel = os.path.relpath(p, out); b = os.path.join(R, 'site', rel)
        if not os.path.exists(b) or not filecmp.cmp(p, b, shallow=False): changed.append(rel)
rep['changed'] = sorted(changed); log('changed files', changed)
if any(not c.startswith('high-school/') for c in changed): log('DIFF SCOPE VIOLATION'); finish(14, 'fail-diff-scope')
state['input_hash'] = ih; state['last_run'] = rep['now']
def save_state(): json.dump(state, open(os.path.join(R, 'state.json'), 'w'), indent=1)
if not changed and not A.force: save_state(); log('no site change -> skip deploy'); finish(0, 'skip-nochange')
if A.target == 'none': log('dry run: not deploying'); finish(0, 'dry-run')

# 6. guard
TOK = os.environ.get('CLOUDFLARE_API_TOKEN')
def cf(path, method='GET'):
    r = urllib.request.Request(f'https://api.cloudflare.com/client/v4/accounts/{ACCT}/pages/projects/{PROJ}{path}', method=method, headers={'Authorization': f'Bearer {TOK}'})
    return json.load(urllib.request.urlopen(r, timeout=60))['result']
canon = cf('')['canonical_deployment']['id']; rep['guard'] = canon
if canon != state['live_id']:
    rep['issues'].append({'title': 'HS refresh: live changed outside the HS job (guard mismatch)', 'body': f'canonical {canon} != recorded {state["live_id"]}. Re-sync site/ from the new live lineage and update state.json live_id.'})
    log('GUARD MISMATCH', canon, state['live_id']); finish(12, 'fail-guard')
UA = {'User-Agent': 'Mozilla/5.0 MSM-HS-Refresh'}
def fetch(u): return urllib.request.urlopen(urllib.request.Request(u + ('&' if '?' in u else '?') + 'cb=' + str(os.getpid()), headers=UA), timeout=60).read()
NORM = re.compile(rb'<a href="(?:mailto:[^"]*|/cdn-cgi/l/email-protection[^"]*)">.*?</a>', re.S)
BEACON = re.compile(rb'<!-- Cloudflare Pages Analytics -->|<script[^>]*static\.cloudflareinsights\.com[^>]*>\s*</script>\n?(<!-- Cloudflare Pages Analytics -->)?', re.S)
def norm(b): return NORM.sub(b'@', BEACON.sub(b'', b))
def same(local, remote): return norm(open(local, 'rb').read()) == norm(remote)  # CF edge injects analytics beacon + email obfuscation
for rel in ('high-school/index.html', 'high-school/standings/index.html', 'index.html'):
    if not same(os.path.join(R, 'site', rel), fetch('https://mtnsportsmedia.com/' + rel.replace('index.html', ''))):
        log('STALE BASE', rel); rep['issues'].append({'title': 'HS refresh: repo base differs from live', 'body': rel}); finish(13, 'fail-stale-base')
log('guard ok', canon, '+ base == live')

# 7. deploy
br = 'main' if A.target == 'production' else A.preview_branch
p = subprocess.run(['wrangler', 'pages', 'deploy', out, '--project-name', PROJ, '--branch', br, '--commit-dirty=true'], capture_output=True, text=True)
print(p.stdout[-1500:], p.stderr[-1500:])
m = re.search(r'https://([0-9a-f]{8})\.' + PROJ + r'\.pages\.dev', p.stdout + p.stderr)
if p.returncode or not m: log('DEPLOY FAILED rc', p.returncode); finish(15, 'fail-deploy')
rep['deploy_url'] = m.group(0); log('deployed', m.group(0), 'branch', br)
hosts = ['https://mtnsportsmedia.com', 'https://www.mtnsportsmedia.com'] if A.target == 'production' else [m.group(0), f'https://{br}.{PROJ}.pages.dev']

# 8. verify: bytecmp + smoke
import time; time.sleep(8); bad = []
for h in hosts:
    for rel in sorted(set(changed) | {'index.html'}):
        if not rel.endswith('.html'): continue
        if not same(os.path.join(out, rel), fetch(h + '/' + rel.replace('index.html', ''))): bad.append(h + '/' + rel)
log('bytecmp', 'ok' if not bad else bad)
sm = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), 'smoke.py'), hosts[0]], capture_output=True, text=True)
print(sm.stdout[-3000:], sm.stderr[-1500:]); log('smoke', 'ok' if sm.returncode == 0 else 'FAIL')
if bad or sm.returncode:
    if A.target == 'production':
        cf(f'/deployments/{canon}/rollback', 'POST'); log('ROLLED BACK to', canon)
        rep['issues'].append({'title': 'HS refresh: production verify failed, rolled back', 'body': json.dumps({'bad': bad, 'smoke': sm.stdout[-1500:]}, indent=1)})
    finish(16, 'fail-verify')
if A.target == 'production':
    state['live_id'] = cf('')['canonical_deployment']['id']; shutil.rmtree(os.path.join(R, 'site')); shutil.copytree(out, os.path.join(R, 'site'))
    log('new live', state['live_id'], 'base updated')
    save_state()
finish(0, 'deployed-' + A.target)
