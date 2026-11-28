# msm-hs-refresh
Auto-refresh of mtnsportsmedia.com `/high-school/*` (Utah 6A/5A playoffs) on Cloudflare Pages project `mountaingridiron`.

- `site/` = exact live lineage (last Production deploy). `state.json` = recorded live deployment id + input hash.
- `data/hs_schedule.json` = bracket games (QF Nov 6; SF Nov 12/13; finals Nov 20). Edit TBA kickoffs/sites here.
- `data/hs_scores.json` = sourced finals + `pending` (hand-held entries use `"hold": true`).
- Sources: KSL Sports prep roundups only (blocklist: MaxPreps, Deseret News, Yahoo, NFHS).

Flow (`tools/run.py`): window gate -> fetch KSL -> input-hash skip -> merge (new finals / conflicts -> pending + `hs-pending` issue) -> patch copy -> diff must be `high-school/*` only -> guard (CF canonical == state.live_id, base HTML == live) -> wrangler deploy -> bytecmp + Playwright smoke -> auto-rollback on failure (production) -> commit lineage.

Enable the cron: `gh variable set HS_SCHEDULE --body on -R kicktipmedia/msm-hs-refresh` (off = gated). Manual: Actions -> hs-refresh -> Run workflow (deploy_target none|preview|production).
Tests: `tests/run_tests.sh` (fixtures are fake and never deployed). The skip-nochange / input-hash checks read `tests/fixtures/posted_r1.html` plus frozen first-round hub/standings HTML and scores, not live KSL or the current `site/` / `hs_scores.json` snapshot, so a new final or later-round sync cannot fail the pre-publish job. T3 uses a synthetic unrecorded state-final score on a throwaway scores snapshot with the live 6A-F/5A-F rows removed, because those finals are now in `data/hs_scores.json`. T4's conflict is the 5A final on the same stripped snapshot and does not publish a score. Once those finals are sourced, `p_hub` rewrites the /high-school/ `.c1w` grids from quarterfinal cards to state-final cards so a later cron run cannot revert them. Later-pass polish (full school names on narrow hub cards, scroll-margin so the sticky header does not cover a 6A/5A heading or tab, and leftover R1/QF bracket hrefs retargeted to `#hs-6a-final` / `#hs-5a-final` or `#hub-6a` / `#hub-5a`) also lives in `tools/hs.py` so a cron run cannot drop it.

## Production hold (exit 16/17/15-with-rollback)
A failed production verify, a failed/unconfirmed rollback, or a wrangler failure that still moved canonical sets `hold` in `state.json` (committed alone; data/site changes from that run are discarded). While `hold` is set every production run exits 18 (`fail-hold`) and opens "HS refresh: production on HOLD". Preview runs still work.

### Clearing the hold (by hand only)
1. Confirm live: Cloudflare Pages `mountaingridiron` canonical == `hold.live_id_expected` (or re-sync `site/` + `live_id` to the new live).
2. Fix the cause (see the run's report.json / issue).
3. `jq 'del(.hold)' state.json > s && mv s state.json && git commit -am "clear hs hold" && git push`

Exit codes: 0 ok/skip, 12 guard mismatch, 13 stale base, 14 diff scope (incl. deletions), 15 deploy fail, 16 verify fail (rolled back + confirmed, hold), 17 PRODUCTION ROLLBACK FAILED (issue, hold), 18 refused: hold set.

Sources: KSL only (`sports.ksl.com`, `ksl.com`, `www.ksl.com`, https, re-checked after redirects). UHSAA/school sites are hand-entry only.

## Ticker: state champions stay up through the offseason
Sourced state finals (round F, recorded in `data/hs_scores.json`) stay on the HS ticker after the 7-day window. Their `data-kt` is the final date plus 365 days at 6 PM MT, a fixed value so the daily patch stays byte-identical and `hs-ticker.js` (which drops items 3 hours past `data-kt`) does not hide them. They roll off when the next season has a posted game: any schedule row dated in a later calendar year than the final, or any row dated today or later that is not a state final. Earlier rounds, and a final that exists only as a hand-held pending winner, keep the 7-day rule. See `champs_rolled` / `ticker_items` in `tools/hs.py` and `tests/champs_check.py`.
