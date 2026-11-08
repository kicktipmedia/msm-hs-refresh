# msm-hs-refresh
Auto-refresh of mtnsportsmedia.com `/high-school/*` (Utah 6A/5A playoffs) on Cloudflare Pages project `mountaingridiron`.

- `site/` = exact live lineage (last Production deploy). `state.json` = recorded live deployment id + input hash.
- `data/hs_schedule.json` = bracket games (QF Nov 6; SF Nov 12/13; finals Nov 20). Edit TBA kickoffs/sites here.
- `data/hs_scores.json` = sourced finals + `pending` (hand-held entries use `"hold": true`).
- Sources: KSL Sports prep roundups only (blocklist: MaxPreps, Deseret News, Yahoo, NFHS).

Flow (`tools/run.py`): window gate -> fetch KSL -> input-hash skip -> merge (new finals / conflicts -> pending + `hs-pending` issue) -> patch copy -> diff must be `high-school/*` only -> guard (CF canonical == state.live_id, base HTML == live) -> wrangler deploy -> bytecmp + Playwright smoke -> auto-rollback on failure (production) -> commit lineage.

Enable the cron: `gh variable set HS_SCHEDULE --body on -R kicktipmedia/msm-hs-refresh` (off = gated). Manual: Actions -> hs-refresh -> Run workflow (deploy_target none|preview|production).
Tests: `tests/run_tests.sh` (fixtures are fake and never deployed). The skip-nochange / input-hash checks read `tests/fixtures/posted_r1.html`, not live KSL, so a new final cannot fail the pre-publish job.

## Production hold (exit 16/17/15-with-rollback)
A failed production verify, a failed/unconfirmed rollback, or a wrangler failure that still moved canonical sets `hold` in `state.json` (committed alone; data/site changes from that run are discarded). While `hold` is set every production run exits 18 (`fail-hold`) and opens "HS refresh: production on HOLD". Preview runs still work.

### Clearing the hold (by hand only)
1. Confirm live: Cloudflare Pages `mountaingridiron` canonical == `hold.live_id_expected` (or re-sync `site/` + `live_id` to the new live).
2. Fix the cause (see the run's report.json / issue).
3. `jq 'del(.hold)' state.json > s && mv s state.json && git commit -am "clear hs hold" && git push`

Exit codes: 0 ok/skip, 12 guard mismatch, 13 stale base, 14 diff scope (incl. deletions), 15 deploy fail, 16 verify fail (rolled back + confirmed, hold), 17 PRODUCTION ROLLBACK FAILED (issue, hold), 18 refused: hold set.

Sources: KSL only (`sports.ksl.com`, `ksl.com`, `www.ksl.com`, https, re-checked after redirects). UHSAA/school sites are hand-entry only.
