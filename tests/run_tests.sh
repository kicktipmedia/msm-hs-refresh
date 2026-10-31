#!/bin/bash
# Offline-safe test suite; each test runs on a throwaway copy of the repo (no deploy).
set -u; ROOT=$(cd "$(dirname "$0")/.." && pwd); OUT=${1:-/tmp/hs-tests}; rm -rf "$OUT"; mkdir -p "$OUT"; fail=0
copy(){ rm -rf "$OUT/$1"; mkdir -p "$OUT/$1"; cp -a "$ROOT/site" "$ROOT/data" "$ROOT/state.json" "$OUT/$1/"; }
run(){ name=$1; shift; copy $name; python3 "$ROOT/tools/run.py" --root "$OUT/$name" "$@" > "$OUT/$name.log" 2>&1; echo $? > "$OUT/$name.rc"; }
check(){ if eval "$2"; then echo "PASS $1"; else echo "FAIL $1"; fail=1; fi; }
# T1 live KSL, today: no-op
run t1_live_dry --now 2026-10-31T07:05:00-06:00 --event dispatch
check "T1 live dry run is no-op skip" "grep -q '\"status\": \"skip-nochange\"' $OUT/t1_live_dry/report.json && grep -q 'changed files \[\]' $OUT/t1_live_dry.log"
# T1b second run with same inputs hits cheap skip
python3 "$ROOT/tools/run.py" --root "$OUT/t1_live_dry" --now 2026-10-31T07:35:00-06:00 > "$OUT/t1b.log" 2>&1
check "T1b repeat run hits input-hash skip" "grep -q skip-unchanged $OUT/t1_live_dry/report.json"
# T2 scheduled run outside window
run t2_window --event schedule --now 2026-10-31T12:00:00-06:00
check "T2 schedule outside window skips before fetch" "grep -q skip-window $OUT/t2_window/report.json"
# T3 new final fixture (Nov 7 morning)
run t3_newfinal --fixture "$ROOT/tests/fixtures/qf_final.html" --now 2026-11-07T07:05:00-07:00
check "T3 new final patches only high-school/*" "python3 -c \"import json;r=json.load(open('$OUT/t3_newfinal/report.json'));c=r['changed'];assert r['status']=='dry-run' and c and all(x.startswith('high-school/') for x in c),r\""
diff -ru "$ROOT/site" "$OUT/t3_newfinal/out" > "$OUT/t3_newfinal.diff"
check "T3 Skyridge 35-14 in bracket + ticker" "grep -q 'Skyridge' $OUT/t3_newfinal.diff && grep -q '35' $OUT/t3_newfinal.diff"
# T4 conflict fixture
run t4_conflict --fixture "$ROOT/tests/fixtures/conflict_a.html" --fixture "$ROOT/tests/fixtures/conflict_b.html" --now 2026-11-07T07:05:00-07:00
check "T4 conflict -> pending + issue, no score published" "python3 -c \"import json;r=json.load(open('$OUT/t4_conflict/report.json'));s=json.load(open('$OUT/t4_conflict/data/hs_scores.json'));assert any(i['title'].startswith('HS pending: 5A-QF-4') for i in r['issues']);assert any(p.get('game')==4 and p.get('rid')=='QF' for p in s['pending']);assert not any(f.get('rid')=='QF' for f in s['finals'])\""
check "T4 no Alta score in output" "! diff -ru $ROOT/site $OUT/t4_conflict/out | grep -E '^\+.*(28|31)[^0-9].*Alta|Alta[^<]*(28|31)'"
# --- B1/B2 (mocked Cloudflare/wrangler/fetch via HS_MOCK; never touches network deploy) ---
L='664ce5e0-d481-4beb-9522-69c2dc049703'; FX="$ROOT/tests/fixtures/qf_final.html"; NOW=2026-11-07T07:05:00-07:00
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
# allowlist
check "allowlist KSL-only + https" "python3 -c \"import sys;sys.path.insert(0,'$ROOT/tools');import hs;a=hs.allowed;assert a('https://sports.ksl.com/prep/x') and a('https://www.ksl.com/a');assert not any(a(u) for u in ['https://uhsaa.org/x','https://evilksl.com','https://ksl.com.evil.io','https://www.maxpreps.com','http://sports.ksl.com/','https://x.k12.ut.us'])\""
exit $fail
