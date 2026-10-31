# msm-hs-refresh
Auto-refresh of mtnsportsmedia.com `/high-school/*` (Utah 6A/5A playoffs) on Cloudflare Pages project `mountaingridiron`.

- `site/` = exact live lineage (last Production deploy). `state.json` = recorded live deployment id + input hash.
- `data/hs_schedule.json` = bracket games (QF Nov 6; SF Nov 12/13; finals Nov 20). Edit TBA kickoffs/sites here.
- `data/hs_scores.json` = sourced finals + `pending` (hand-held entries use `"hold": true`).
- Sources: KSL Sports prep roundups only (blocklist: MaxPreps, Deseret News, Yahoo, NFHS).

Flow (`tools/run.py`): window gate -> fetch KSL -> input-hash skip -> merge (new finals / conflicts -> pending + `hs-pending` issue) -> patch copy -> diff must be `high-school/*` only -> guard (CF canonical == state.live_id, base HTML == live) -> wrangler deploy -> bytecmp + Playwright smoke -> auto-rollback on failure (production) -> commit lineage.

Enable the cron: `gh variable set HS_SCHEDULE --body on -R kicktipmedia/msm-hs-refresh` (off = gated). Manual: Actions -> hs-refresh -> Run workflow (deploy_target none|preview|production).
Tests: `tests/run_tests.sh` (fixtures are fake and never deployed).
