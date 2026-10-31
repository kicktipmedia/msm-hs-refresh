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
exit $fail
