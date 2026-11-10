# HSK 1–6 catalog — status, decisions and runbook (2026-11-10)

**Verdict: implementation ready for approved data. HSK 1–6 is NOT published.** No CTI or other third-party HSK record is in any migration, seed, fixture, database or API.

## 1. Verification

| Check | Result |
|---|---|
| Backend suite (SQLite, `pytest`) | **604 passed, 7 skipped.** The 7 skipped tests are the new PostgreSQL module, which needs a server. All pre-existing tests still pass. |
| New HSK tests on SQLite | 23 passed: validator (`test_hsk_import_validation.py`) and API/learner flow (`test_hsk_catalog_api.py`) |
| `ruff check .` | clean |
| Chatbot evals | 100% on all categories |
| CTI dry-run validation (no DB) | done; see `HSK_IMPORT_REPORT.md` |
| **PostgreSQL 16 integration tests** | **7 passed** on a disposable `postgres:16-alpine` (16.15) container with no host port. Covered: single linear head; CEFR, Chinese development data and user progress (vocabulary counters, review dates, exercise, attempt) identical across upgrade; lossless downgrade with no saves, refused downgrade after a save; 21 named constraint-violation checks; importer run twice with identical row identities; third-party release blocked from publishing; changed source needs a new release; HSK 1–6 browse, search, save, review and exercise; a new release that edits and retires catalog data leaves snapshots and progress unchanged. Each test database is dropped afterwards. |
| ORM ↔ migration drift (PostgreSQL) | **0 differences** (Alembic `compare_metadata`, `compare_type=True`) on a freshly migrated database |
| Frontend `npm test` | **89/89 passed** (including 5 new `hskPresentation` tests), in `node:22-alpine` |
| Frontend `npm run build` | **passes** (`tsc -b && vite build`). The >500 kB chunk warning already existed at HEAD (602 kB → 612 kB). |
| Live browser run (disposable stack) | API on `127.0.0.1:18080` against a disposable PostgreSQL 16 database, frontend on `localhost:15173`; the synthetic release was imported and published with the real CLI. In the browser: registered a test user, switched to the Chinese track, opened HSK 1–6 (2 entries per level), viewed 长 (two readings, two senses, 長 variant, HSK 4 annotation, record 103 / serial 3), viewed 行1 (raw POS shown verbatim, sense POS shown as missing), saved "cháng – long", and found it in My Vocabulary and the review queue; a review session completed. After publishing release v2, the saved row was unchanged (status, counters, next review, snapshot pointing to v1), the v2 entry showed the sense as already saved, and the retired sense was hidden. Exercises were not exercised in the UI (no AI key in the demo); they are covered by the API and PostgreSQL tests with a fake provider. The stack has been torn down. |

## 2. What works locally (tested on PostgreSQL 16 and SQLite)

- Additive migration `20261110_0015` (single head after `20260908_0014`). Downgrade is lossless while no learner has saved a catalog sense, and refuses after that.
- Normalized model: releases with four independent permission statuses and a DB publication gate; source records keep raw official fields plus a payload hash; primary and annotation level membership; lexical entries, readings, senses, multi-POS, sense–reading links, variants and examples; release-scoped source→lexical mappings with same-release and same-lexical composite FKs.
- Importer/validator (`app/catalog/hsk_import.py`, CLI `scripts/import_hsk_release.py`): SHA-256 check; id and serial kept independent; serial gaps reported; duplicates, levels, missing POS, multi-readings and homographs flagged; review mappings validated; idempotent upserts; always creates a `draft` release; never touches `vocabularies`; DB commands require an explicit `--database-url`.
- Read API `/api/v1/catalog/hsk/{track_id}/levels|entries|entries/{id}` serves only the single published release, with no fallback. Admins can preview a draft with `release_id`.
- Save API `POST …/entries/{id}/save {mapping_id}` copies one approved sense into `vocabularies` with a JSON provenance snapshot. Existing review and exercise flows work unchanged on the saved Chinese words.
- Duplicate rule: one row per (user, sense). This holds across releases in the service and per (user, source record, sense) in the DB with `NULLS NOT DISTINCT`. Senses that are NULL/unspecialized, draft, or missing a Vietnamese gloss cannot be saved (409). A save that would duplicate an existing personal word returns `overlapping_personal_word`.
- Catalog edits, sense retirement, source retirement and replacement by a new release leave saved rows, counters, review dates and attempts unchanged (tested on PostgreSQL 16 and SQLite).
- Frontend: `/app/learn/hsk` (`HskCatalogPage.tsx`) offers level tabs HSK 1–6, search, and a detail view with official fields, readings, senses, POS (labelled "missing" when absent), variants and examples, plus per-sense save. A link to it appears on the Learn page for HSK tracks.
- The legacy v1 `/vocabulary-sets`, the CEFR catalog and the 8 Chinese development cards are untouched.

## 3. Still draft / not done

- Admin UI for releases and review: import and publish are CLI only.
- No reviewed HSK 1–6 sense dataset exists. The CTI payload has no meanings, so even with permission every record would load as "awaiting review" until a human-reviewed `review.json` is produced.

## 4. Blocked on owner decisions

| ID | Decision needed | Recommendation | What it unblocks |
|---|---|---|---|
| OD-11 | For the CTI snapshot (SHA-256 above), record **separately**: storage, transformation/enrichment, redistribution, and publication in the web product, each with authority, scope, date and evidence. | Obtain written evidence for each one. Approving one does not imply the others. | Loading real HSK 1–6 into any environment, then publishing it |
| Senses source | Which meanings/translations to use, and under what licence: Mascot-authored, CC-CEDICT (CC BY-SA, which carries attribution and share-alike obligations), or another. The older `scripts/*hsk31*` tooling references `@leonsilicon/hsk3.1`, `ivankra/hsk30` (whose README itself questions the data's copyright status) and CC-CEDICT. | Decide the licence before any enrichment is imported | Mapped and saveable entries |
| OD-02 | POS policy: is the 17-code controlled list (`app/models/hsk_catalog.py`) acceptable, and how should CTI labels like `名、（动）` be interpreted? | Keep raw labels verbatim and add only reviewed sense-level codes | Editorial POS |
| OD-12 | Lexical identity: whether homographs (`点1/点2`) and repeated surfaces become separate lexical entries, and how splits/merges are handled | One lexical entry per distinct reading and meaning group, decided in review | 225 ambiguous CTI rows |
| OD-03 | Whether the 8 legacy Chinese development cards are migrated into a normalized `mascot_owned` release | Leave them as legacy until real data exists; their origin is Mascot-authored migration `0012` and they are no evidence of HSK rights | Retiring the legacy HSK set |
| OD-04 | Who may publish a release, and when | CLI publish by a named operator after the permission and review gates | Production activation |

## 5. Needed before production publication

Owner decisions OD-11 and the senses licence; a reviewed dataset; confirming the actual production PostgreSQL version (Neon was never inspected; these tests ran only on 16.15); an applied-migration rehearsal on a production-sized copy with timing and lock measurement (OD-10); a backup and restore plan; an explicit request to touch Neon/Render/Vercel. None of these were done.

## 6. Runbook: disposable PostgreSQL 16 (after Docker works)

```bash
docker network create mascot-hsk-test
docker run -d --rm --name mascot-hsk-pg16 --network mascot-hsk-test -e POSTGRES_PASSWORD=disposable postgres:16-alpine
docker run --rm --network mascot-hsk-test -v "$PWD/backend:/src:ro" -e MASCOT_PG_TEST_DISPOSABLE=1 -e MASCOT_PG_TEST_ADMIN_URL=postgresql+psycopg://postgres:disposable@mascot-hsk-pg16:5432/postgres python:3.12-slim sh -c "mkdir /work && tar -C /src --exclude=.venv -cf - . | tar -C /work -xf - && cd /work && pip install -q '.[dev]' && pytest tests/postgres -v"
docker stop mascot-hsk-pg16
```

The container publishes no host port, so it cannot collide with the PostgreSQL on `localhost:5432`.
