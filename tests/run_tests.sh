#!/bin/bash
# Offline-safe test suite; each test runs on a throwaway copy of the repo (no deploy).
set -u; ROOT=$(cd "$(dirname "$0")/.." && pwd); OUT=${1:-/tmp/hs-tests}; rm -rf "$OUT"; mkdir -p "$OUT"; fail=0
# Drop a committed production hold. Offline tests must not inherit one; production
# still refuses to deploy when the root they are given actually has hold set.
fresh_state(){ jq 'del(.hold)' "$1" > "$2"; }
copy(){ rm -rf "$OUT/$1"; mkdir -p "$OUT/$1"; cp -a "$ROOT/site" "$ROOT/data" "$OUT/$1/"; fresh_state "$ROOT/state.json" "$OUT/$1/state.json"; }
run(){ name=$1; shift; copy $name; python3 "$ROOT/tools/run.py" --root "$OUT/$name" "$@" > "$OUT/$name.log" 2>&1; echo $? > "$OUT/$name.rc"; }
check(){ if eval "$2"; then echo "PASS $1"; else echo "FAIL $1"; fail=1; fi; }
# T1 frozen fixture of finals already in data/hs_scores.json: full path is a no-op.
# Do not drop --fixture. A live KSL fetch fails this check whenever KSL posts a new
# final, which fail-closes hs-refresh before the Refresh step can publish it.
# Clear the recorded input_hash in the throwaway copy so T1 always exercises the full
# read->build->diff path (otherwise a committed hash short-circuits to skip-unchanged).
# Run manually (not via run()) so the reset applies; T1b repeats the same fixture.
FX1="$ROOT/tests/fixtures/posted_r1.html"
copy t1_dry; jq '.input_hash=null' "$OUT/t1_dry/state.json" > "$OUT/t1_state.tmp" && mv "$OUT/t1_state.tmp" "$OUT/t1_dry/state.json"
# Overlay frozen R1-era hub/standings HTML. T1 --now is Oct 31 (QF still upcoming
# in the ticker). After site/ is synced to a later live snapshot (QF scores, SF
# ticker), the Oct 31 patcher would rewrite those pages and fail-close this check.
cp "$ROOT/tests/fixtures/posted_r1_hs_index.html" "$OUT/t1_dry/site/high-school/index.html"
cp "$ROOT/tests/fixtures/posted_r1_hs_standings.html" "$OUT/t1_dry/site/high-school/standings/index.html"
cp "$ROOT/tests/fixtures/posted_r1_hs_recruiting.html" "$OUT/t1_dry/site/high-school/recruiting/index.html"
# Keep T1 on the R1-only scores snapshot. Recorded later-round finals in
# data/hs_scores.json would patch this throwaway tree and fail-close the no-op.
cp "$ROOT/tests/fixtures/posted_r1_scores.json" "$OUT/t1_dry/data/hs_scores.json"
python3 "$ROOT/tools/run.py" --root "$OUT/t1_dry" --fixture "$FX1" --now 2026-10-31T07:05:00-06:00 --event dispatch > "$OUT/t1_dry.log" 2>&1; echo $? > "$OUT/t1_dry.rc"
check "T1 fixture dry run is no-op skip" "grep -q '\"status\": \"skip-nochange\"' $OUT/t1_dry/report.json && grep -q 'changed files \[\]' $OUT/t1_dry.log && grep -q 'sources: 1 pages, 16 score lines' $OUT/t1_dry.log"
# T1b second run with the same fixture hits cheap skip (hash, not a second live fetch)
python3 "$ROOT/tools/run.py" --root "$OUT/t1_dry" --fixture "$FX1" --now 2026-10-31T07:35:00-06:00 > "$OUT/t1b.log" 2>&1
check "T1b repeat run hits input-hash skip" "grep -q skip-unchanged $OUT/t1_dry/report.json && grep -q 'inputs unchanged since last run -> skip' $OUT/t1b.log"
# T2 scheduled run outside window
run t2_window --event schedule --now 2026-10-31T12:00:00-06:00
check "T2 schedule outside window skips before fetch" "grep -q skip-window $OUT/t2_window/report.json"
# T3 new final: synthetic unrecorded state final. Semifinals are already in
# data/hs_scores.json, so an SF fixture would conflict instead of patch.
run t3_newfinal --fixture "$ROOT/tests/fixtures/sf_final.html" --now 2026-11-07T07:05:00-07:00
check "T3 new final patches only high-school/*" "python3 -c \"import json;r=json.load(open('$OUT/t3_newfinal/report.json'));c=r['changed'];assert r['status']=='dry-run' and c and all(x.startswith('high-school/') for x in c),r\""
diff -ru "$ROOT/site" "$OUT/t3_newfinal/out" > "$OUT/t3_newfinal.diff"
check "T3 synthetic 6A final Skyridge 21-17 in bracket + ticker" "grep -q 'Skyridge 21' $OUT/t3_newfinal.diff && grep -q 'Corner Canyon 17' $OUT/t3_newfinal.diff"
# T4 conflict fixture
run t4_conflict --fixture "$ROOT/tests/fixtures/conflict_a.html" --fixture "$ROOT/tests/fixtures/conflict_b.html" --now 2026-11-07T07:05:00-07:00
check "T4 conflict -> pending + issue, no score published" "python3 -c \"import json;r=json.load(open('$OUT/t4_conflict/report.json'));s=json.load(open('$OUT/t4_conflict/data/hs_scores.json'));assert any(i['title'].startswith('HS pending: 5A-F') for i in r['issues']);assert any(p.get('class')=='5A' and p.get('rid')=='F' for p in s['pending']);assert not any(f.get('rid')=='F' for f in s['finals'])\""
check "T4 no conflict final score in output" "! diff -ru $ROOT/site $OUT/t4_conflict/out | grep -E '^\+.*(West 24|Orem 21|Orem 27)'"
# --- B1/B2 (mocked Cloudflare/wrangler/fetch via HS_MOCK; never touches network deploy) ---
L=$(jq -r .live_id "$ROOT/state.json"); FX="$ROOT/tests/fixtures/sf_final.html"; NOW=2026-11-07T07:05:00-07:00
gitinit(){ (cd "$OUT/$1" && git init -q && git add -A && git -c user.name=t -c user.email=t@t commit -qm base); }
# workflow failure step, copied from hs-refresh.yml
wf_fail(){ (cd "$OUT/$1" && git checkout -- data site && git clean -fdq data site && if jq -e .hold state.json >/dev/null && ! git diff --quiet -- state.json; then git add state.json && git -c user.name=t -c user.email=t@t commit -qm hold; else git checkout -- state.json; fi); }
echo "{\"canon\":[\"$L\",\"$L\"],\"verify_bad\":true}" > "$OUT/m_b1.json"
copy t5_b1; gitinit t5_b1
HS_MOCK="$OUT/m_b1.json" python3 "$ROOT/tools/run.py" --root "$OUT/t5_b1" --target production --fixture "$FX" --now $NOW > "$OUT/t5_b1.log" 2>&1; echo $? > "$OUT/t5_b1.rc"
check "B1 verify fail -> exit 16, rollback confirmed, hold set" "[ \$(cat $OUT/t5_b1.rc) = 16 ] && grep -q 'ROLLED BACK to .* confirmed' $OUT/t5_b1.log && jq -e '.hold.code==16' $OUT/t5_b1/state.json >/dev/null"
wf_fail t5_b1
check "B1 data/site not committed (HEAD~1..HEAD touches only state.json, tree clean)" "(cd $OUT/t5_b1 && [ \"\$(git diff --name-only HEAD~1 HEAD)\" = state.json ] && git diff --quiet HEAD -- data site)"
echo "{\"canon\":[\"$L\"]}" > "$OUT/m_ok.json"
HS_MOCK="$OUT/m_ok.json" python3 "$ROOT/tools/run.py" --root "$OUT/t5_b1" --target production --fixture "$FX" --now $NOW --force > "$OUT/t5_b1b.log" 2>&1; echo $? > "$OUT/t5_b1b.rc"
check "B1 hold blocks next production run (exit 18, no deploy)" "[ \$(cat $OUT/t5_b1b.rc) = 18 ] && ! grep -q deployed $OUT/t5_b1b.log && grep -q 'production on HOLD' $OUT/t5_b1/report.json"
# B2 rollback raises
echo "{\"canon\":[\"$L\"],\"verify_bad\":true,\"rollback_raises\":true}" > "$OUT/m_b2.json"
copy t6_b2
HS_MOCK="$OUT/m_b2.json" python3 "$ROOT/tools/run.py" --root "$OUT/t6_b2" --target production --fixture "$FX" --now $NOW > "$OUT/t6_b2.log" 2>&1; echo $? > "$OUT/t6_b2.rc"
check "B2 rollback exception -> exit 17 + report.json + PRODUCTION ROLLBACK FAILED issue + hold" "[ \$(cat $OUT/t6_b2.rc) = 17 ] && jq -e '.exit==17 and .status==\"fail-rollback\" and any(.issues[]; .title==\"PRODUCTION ROLLBACK FAILED\")' $OUT/t6_b2/report.json >/dev/null && jq -e '.hold.code==17' $OUT/t6_b2/state.json >/dev/null"
# B2b rollback 'succeeds' but canonical still the bad deploy
echo "{\"canon\":[\"$L\",\"deadbeef-bad\"],\"verify_bad\":true}" > "$OUT/m_b2b.json"
copy t6_b2b
HS_MOCK="$OUT/m_b2b.json" python3 "$ROOT/tools/run.py" --root "$OUT/t6_b2b" --target production --fixture "$FX" --now $NOW > "$OUT/t6_b2b.log" 2>&1; echo $? > "$OUT/t6_b2b.rc"
check "B2 rollback unconfirmed (live != pre-deploy) -> exit 17" "[ \$(cat $OUT/t6_b2b.rc) = 17 ] && grep -q 'deadbeef-bad != pre-deploy' $OUT/t6_b2b.log"
# wrangler fails but canonical moved -> rollback
echo "{\"canon\":[\"$L\",\"moved-1234\",\"$L\"],\"deploy\":{\"rc\":1,\"out\":\"boom\"}}" > "$OUT/m_w.json"
copy t7_wr
HS_MOCK="$OUT/m_w.json" python3 "$ROOT/tools/run.py" --root "$OUT/t7_wr" --target production --fixture "$FX" --now $NOW > "$OUT/t7_wr.log" 2>&1; echo $? > "$OUT/t7_wr.rc"
check "wrangler fail + canonical moved -> rollback confirmed, exit 15, hold" "[ \$(cat $OUT/t7_wr.rc) = 15 ] && grep -q 'ROLLED BACK to .* confirmed' $OUT/t7_wr.log && jq -e '.hold.code==15' $OUT/t7_wr/state.json >/dev/null"
# path guard catches deletions
copy t8_del; echo '{"delete":["robots.txt"]}' > "$OUT/m_del.json"
HS_MOCK="$OUT/m_del.json" python3 "$ROOT/tools/run.py" --root "$OUT/t8_del" --fixture "$FX" --now $NOW > "$OUT/t8_del.log" 2>&1; echo $? > "$OUT/t8_del.rc"
check "path guard: file missing from output (deletion) -> exit 14" "[ \$(cat $OUT/t8_del.rc) = 14 ] && grep -q 'DELETED robots.txt' $OUT/t8_del.log"
# Post-deploy fetch error and post-verify canonical read must roll back and hold (exit 16), not crash as rc 1.
echo "{\"canon\":[\"$L\",\"$L\"],\"verify_raises\":true}" > "$OUT/m_vr.json"
copy t_vr
HS_MOCK="$OUT/m_vr.json" python3 "$ROOT/tools/run.py" --root "$OUT/t_vr" --target production --fixture "$FX" --now $NOW > "$OUT/t_vr.log" 2>&1; echo $? > "$OUT/t_vr.rc"
check "verify fetch timeout -> rollback confirmed, hold, exit 16" "[ \$(cat $OUT/t_vr.rc) = 16 ] && grep -q 'verify fetch failed' $OUT/t_vr.log && grep -q 'ROLLED BACK to .* confirmed' $OUT/t_vr.log && jq -e '.hold.code==16' $OUT/t_vr/state.json >/dev/null"
echo "{\"canon\":[\"$L\",\"$L\"],\"canon_raises\":true,\"verify_match_out\":true}" > "$OUT/m_cr.json"
copy t_cr
HS_MOCK="$OUT/m_cr.json" python3 "$ROOT/tools/run.py" --root "$OUT/t_cr" --target production --fixture "$FX" --now $NOW > "$OUT/t_cr.log" 2>&1; echo $? > "$OUT/t_cr.rc"
check "post-verify canonical read timeout -> rollback confirmed, hold, exit 16" "[ \$(cat $OUT/t_cr.rc) = 16 ] && grep -q 'canonical read failed' $OUT/t_cr.log && grep -q 'ROLLED BACK to .* confirmed' $OUT/t_cr.log && jq -e '.hold.code==16' $OUT/t_cr/state.json >/dev/null"
# allowlist
check "allowlist KSL-only + https" "python3 -c \"import sys;sys.path.insert(0,'$ROOT/tools');import hs;a=hs.allowed;assert a('https://sports.ksl.com/prep/x') and a('https://www.ksl.com/a');assert not any(a(u) for u in ['https://uhsaa.org/x','https://evilksl.com','https://ksl.com.evil.io','https://www.maxpreps.com','http://sports.ksl.com/','https://x.k12.ut.us'])\""
# Committed state.json may carry a production hold. The suite copy must not.
copy t0_clean
printf '%s\n' '{"hold":{"code":16,"reason":"planted"},"live_id":"x"}' > "$OUT/planted-hold.json"
fresh_state "$OUT/planted-hold.json" "$OUT/planted-clean.json"
check "offline copy does not inherit a committed hold" "! jq -e .hold $OUT/t0_clean/state.json >/dev/null && ! jq -e .hold $OUT/planted-clean.json >/dev/null"
# production hold behavior itself stays: a root that actually has hold exits 18
copy t0_hold
jq '.hold={"code":16,"reason":"planted","at":"2026-11-13T18:55-07:00","live_id_expected":"x"}' "$OUT/t0_hold/state.json" > "$OUT/t0_hold/s" && mv "$OUT/t0_hold/s" "$OUT/t0_hold/state.json"
python3 "$ROOT/tools/run.py" --root "$OUT/t0_hold" --target production --fixture "$FX" --now $NOW > "$OUT/t0_hold.log" 2>&1; echo $? > "$OUT/t0_hold.rc"
check "planted production hold still blocks deploy (exit 18)" "[ \$(cat $OUT/t0_hold.rc) = 18 ] && grep -q 'production on HOLD' $OUT/t0_hold/report.json && ! grep -q deployed $OUT/t0_hold.log"
# Frozen KSL semifinal pages (no live fetch) plus a finals-style line and bytecmp/token checks.
python3 - << PY > "$OUT/ksl_parse.out" 2> "$OUT/ksl_parse.err"; echo $? > "$OUT/ksl_parse.rc"
import json, os, subprocess, sys
sys.path.insert(0, "$ROOT/tools")
import hs
from check_cf_token import classify, decide, judge, verify_urls
sched = json.load(open("$ROOT/data/hs_schedule.json"))
scores = json.load(open("$ROOT/data/hs_scores.json"))
pages = [
    ("$ROOT/tests/fixtures/ksl_578933_6a_sf.html", "https://sports.ksl.com/prep/6a-4a-semifinals-recap/578933"),
    ("$ROOT/tests/fixtures/ksl_578934_5a_sf.html", "https://sports.ksl.com/prep/uhsaa-playoffs-4a-5a-recap/578934"),
]
cands = []
for p, u in pages:
    cands += hs.parse_ksl(open(p, encoding="utf-8").read(), u)
assert not any(c["cls"] == "4A" for c in cands), cands
def pair(c):
    names = tuple(sorted([c["a"], c["b"]]))
    return (c["cls"], c["round"], tuple(sorted([c["a_score"], c["b_score"]])), names)
got = sorted(pair(c) for c in cands)
# Names may carry a single trailing mascot; scores and schools must be these four.
def schoolish(names, a, b):
    def hit(want):
        return any(n == want or n.endswith(" " + want) or n.startswith(want + " ") for n in names)
    return hit(a) and hit(b)
expect_scores = {("6A", "SF", (34, 35)), ("6A", "SF", (28, 34)), ("5A", "SF", (12, 29)), ("5A", "SF", (10, 56))}
assert {g[:3] for g in got} == expect_scores, got
by_score = {g[2]: g[3] for g in got}
assert schoolish(by_score[(34, 35)], "Skyridge", "Herriman")
assert schoolish(by_score[(28, 34)], "Corner Canyon", "Mountain Ridge")
assert schoolish(by_score[(12, 29)], "West", "Bountiful")
assert schoolish(by_score[(10, 56)], "Orem", "Woods Cross")
new, conflicts, unmatched = hs.merge(sched, scores, cands, "2026-11-14")
assert new == [] and conflicts == [] and unmatched == [], (new, conflicts, unmatched)
posted = {(f["class"], f["rid"], f["home"], f["home_score"], f["away"], f["away_score"]) for f in scores["finals"] if f.get("rid") == "SF"}
assert posted == {
    ("6A", "SF", "Skyridge", 35, "Herriman", 34),
    ("6A", "SF", "Mountain Ridge", 28, "Corner Canyon", 34),
    ("5A", "SF", "West", 29, "Bountiful", 12),
    ("5A", "SF", "Orem", 56, "Woods Cross", 10),
}
prot = {"field", "ridge", "cross"}
assert hs._label_hits("West Panthers", "West", prot)
assert not hs._label_hits("West Field", "West", prot)
assert hs._label_hits("West Field", "West Field", prot)
assert hs._label_hits("Woods Cross Wildcats", "Woods Cross", prot)
bad = "<h2>Class 6A semifinals</h2><h3>Skyridge beat Herriman</h3><p><strong>maybe 35-34</strong></p>"
assert hs.parse_ksl(bad, "fixture://unparseable") == []
fin = """<h2>Class 6A finals</h2><h3>No. 1 Skyridge 21, No. 3 Corner Canyon 17</h3>
<h3>Class 5A — Championship</h3>
<p><strong>No. 1 West Panthers 14, </strong><strong>No. 2 Orem Tigers 10 </strong></p>
<h2>Notes</h2><p><strong>No. 9 Nobody 1, No. 8 Else 2</strong></p>"""
rows = hs.parse_ksl(fin, "fixture://finals-style")
assert len(rows) == 2 and all(r["round"] == "F" for r in rows), rows
newF, confF, unF = hs.merge(sched, scores, rows, "2026-11-21")
assert confF == [] and unF == [] and len(newF) == 2, (newF, confF, unF)
assert {(n["class"], n["home"], n["home_score"], n["away"], n["away_score"]) for n in newF} == {
    ("6A", "Skyridge", 21, "Corner Canyon", 17),
    ("5A", "West", 14, "Orem", 10),
}
local = b'<p>Email <a href="mailto:huddle@mtnsportsmedia.com">huddle@mtnsportsmedia.com</a> thanks.</p>'
remote = b'<p>Email <a href="/cdn-cgi/l/email-protection#abc" class="__cf_email__" data-cfemail="abc">[email&#160;protected]</a><script data-cfasync="false" src="/cdn-cgi/scripts/5c5dd728/cloudflare-static/email-decode.min.js"></script> thanks.</p>'
remote2 = b'<p>Email <a class="__cf_email__" data-cfemail="abc" href="/cdn-cgi/l/email-protection">[email&#160;protected]</a> thanks.</p>'
assert hs.strip_cf_email(local) == hs.strip_cf_email(remote) == hs.strip_cf_email(remote2)
wrapped = b'<a href="/cdn-cgi/l/email-protection#abc"><span class="__cf_email__" data-cfemail="abc">[email&#160;protected]</span></a>'
assert hs.strip_cf_email(wrapped) == b'@'
assert hs.strip_cf_email(local) != hs.strip_cf_email(local.replace(b"thanks", b"thank you"))
kept = b'<script src="/cdn-cgi/scripts/other.js"></script><a href="/high-school/">HS</a>'
assert hs.strip_cf_email(kept) == kept
unclosed = b'<a href="mailto:huddle@mtnsportsmedia.com">email Skyridge 35 <a href="/high-school/">link</a>'
masked = hs.strip_cf_email(unclosed)
assert b'Skyridge 35' in masked and b'href="/high-school/"' in masked, masked
ot_line = {
    "(OT)": "No. 1 Skyridge 21, No. 3 Corner Canyon 17 (OT)",
    "(2OT)": "No. 1 Skyridge 21, No. 3 Corner Canyon 17 (2OT)",
    ", OT": "No. 1 Skyridge 21, No. 3 Corner Canyon 17, OT",
    "OT": "No. 1 Skyridge 21, No. 3 Corner Canyon 17 OT",
    "period": "No. 1 Skyridge 21, No. 3 Corner Canyon 17.",
}
for label, line in ot_line.items():
    got = hs.parse_ksl(f'<h3>Class 6A — Final</h3><p><strong>{line}</strong></p>', "fixture://ot")
    assert len(got) == 1 and (got[0]["a"], got[0]["a_score"], got[0]["b"], got[0]["b_score"]) == ("Skyridge", 21, "Corner Canyon", 17), (label, got)
assert hs.parse_ksl("<h3>Class 6A — Final</h3><h3>maybe 35-34</h3>", "fixture://nope") == []
kept_class = """<h2>Class 6A finals</h2>
<h3>maybe 35-34</h3>
<h3>No. 1 Skyridge 21, No. 3 Corner Canyon 17 (OT)</h3>
<p><strong>No. 3 Corner Canyon 10, No. 1 Skyridge 14.</strong></p>"""
kept_rows = hs.parse_ksl(kept_class, "fixture://keep-class")
assert [(r["a_score"], r["b_score"]) for r in kept_rows] == [(21, 17), (10, 14)], kept_rows
stale = "<h3>Class 6A — Final</h3><h3>Season series</h3><strong>No. 1 Skyridge 28, No. 3 Corner Canyon 14</strong>"
assert hs.parse_ksl(stale, "fixture://season-series") == []
digit_pages = [
    "<h3>Class 6A — Final</h3><p><strong>No. 1 Skyridge 3 5, No. 3 Corner Canyon 34</strong></p>",
    "<h3>Class 6A — Final</h3><p><strong>No. 1 Skyridge 21, No. 3 Corner Canyon 1 7</strong></p>",
]
for page in digit_pages:
    rows = hs.parse_ksl(page, "fixture://digit-mascot")
    assert len(rows) == 1, rows
    newD, confD, unD = hs.merge(sched, scores, rows, "2026-11-21")
    assert newD == [] and confD == [] and len(unD) == 1, (page, newD, confD, unD)
assert hs.parse_ksl(digit_pages[0], "fixture://digit-mascot")[0]["a_score"] == 5
assert hs.parse_ksl(digit_pages[1], "fixture://digit-mascot")[0]["b_score"] == 7
code, msg = classify(401, '{"success":false,"errors":[{"code":9109,"message":"Invalid access token"}]}')
assert code == 1 and "CLOUDFLARE_API_TOKEN is invalid" in msg and "9109" in msg and "Bearer" not in msg
active = '{"success":true,"result":{"status":"active"},"errors":[]}'
code, msg = classify(200, active)
assert code == 0 and "active" in msg
code, msg = classify(None, "", "URLError: <urlopen error [Errno -2] Name or service not known>")
assert code == 0 and "transient" in msg
assert judge(429, '{"success":false,"errors":[{"code":971,"message":"Rate limited"}]}')[0] == "transient"
assert judge(200, "<html>not json</html>")[0] == "transient"
urls = verify_urls("acct123")
assert urls[0].endswith("/accounts/acct123/tokens/verify") and urls[1].endswith("/user/tokens/verify")
assert verify_urls("") == [urls[1]]
acct_401 = judge(401, '{"success":false,"errors":[{"code":1000,"message":"Invalid API Token"}]}')
user_active = judge(200, active)
assert acct_401[0] == "invalid" and user_active[0] == "active"
assert decide([user_active])[0] == 0
assert decide([acct_401, user_active])[0] == 0
bad_both = decide([acct_401, judge(401, '{"success":false,"errors":[{"code":9109,"message":"Invalid access token"}]}')])
assert bad_both[0] == 1 and "9109" in bad_both[1]
assert decide([judge(429, "")])[0] == 0
assert decide([judge(200, "not-json")])[0] == 0
env = {k: v for k, v in os.environ.items() if k != "CLOUDFLARE_API_TOKEN"}
r = subprocess.run([sys.executable, "$ROOT/tools/check_cf_token.py"], env=env, capture_output=True, text=True)
assert r.returncode == 1 and "missing or empty" in r.stderr and "Bearer" not in r.stderr + r.stdout
print("parser, bytecmp, token classify ok")
PY
check "frozen KSL semis match the four posted rows; finals style parses; email norm is exact; bad token message" "[ \$(cat $OUT/ksl_parse.rc) = 0 ] && grep -q 'parser, bytecmp, token classify ok' $OUT/ksl_parse.out"
exit $fail
