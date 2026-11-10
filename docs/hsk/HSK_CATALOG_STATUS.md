# HSK catalog — status, decisions and runbook (updated 2026-11-11)

**Verdict (2026-11-11):** learners browse HSK by **level → topic → words**, with the same design as English. The owner approved using the official list (see `OWNER_DECISIONS.md`). **HSK 1–9 (all 10,999 official words) is loaded and published in the local test environment** as `hsk-2025-hsk1-9`. Nothing is in production; the data lives outside git (see `README.md`).

### 2026-11-11 additions

| Change | Detail |
|---|---|
| Migration `20261111_0016` | `catalog_topics` (per release and level; 3-level tree; a parent topic must be in the same level) and `catalog_entry_topics` (a word may join only topics of a level it belongs to). Additive; downgrade drops only catalog data. |
| Official topic tree | Extracted from the syllabus PDF by cell position and verified against the printed counts for every level: HSK1 5/15/30, HSK2 5/18/34, HSK3 6/22/54, HSK4 7/31/77, HSK5 7/29/72, HSK6 7/25/68, HSK7–9 5/29/92. |
| HSK 7–9 | One combined level, as published. `HSK7-9` is accepted as a personal level code without changing the listed HSK1–HSK9 codes, because existing tests assert that list. |
| API | `levels` returns topic groups and cards with word and saved counts; `entries?topic_id=`; `POST /topics/{id}/save-all` saves one approved meaning per word ("Học cả chủ đề"). A saved word gets its topic name as its personal topic, so "Practice by topic" works. |
| UI | Same design as the English library. The Learn page shows level tabs HSK 1–6 and 7–9 (English colour ramp, word counts), a topic filter, and one grid of topic cards. Each card has its own icon and colour (all 82 syllabus topic names are mapped) and the name "Vietnamese (中文 smaller)". The topic page (`HskTopicPage.tsx`) reuses the English set-page layout: header with progress and "Bắt đầu học cả bộ", the selection toolbar, and one tickable row per meaning (word, pinyin, POS, English, Vietnamese, example). The source of the meanings appears in one small line. Official-field details are on the search page `/app/learn/hsk` only. |
| HSK 1 dataset | 300/300 words: an AI-drafted English and Vietnamese meaning, the official POS, and one topic each. 15 official topic cards plus 1 Mascot card ("Đại từ & hư từ"). Validation reported 0 rejected, 0 issues. |
| Verification | Backend 604 passed / 7 skipped (SQLite); PostgreSQL 16 7/7, including 3 new topic constraint checks; frontend 91/91 and build OK. In the browser: HSK 1 topic cards (counts sum to 300), the "Ăn uống" topic page, "Học cả chủ đề" saved 18 words, a single save carries the topic name "Mua sắm", and the meaning source is shown. |

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
- Meanings and topic assignments exist for all levels. They are AI drafts, not human-reviewed.
- Topics with more than 50 words are split into parts (`PART_SIZE = 50` in `app/services/hsk_catalog.py`); this is presentation only, so the catalog data is unchanged. A split is not a semantic subtopic: parts follow the official serial order.
- Topic assignments use the second topic level (cards). Assigning words to third-level subtopics is not done yet.

## 4. Blocked on owner decisions

| ID | Decision needed | Recommendation | What it unblocks |
|---|---|---|---|
| OD-11 | **Decided 2026-11-10** by the owner: use the list for the owner's apps (see `OWNER_DECISIONS.md`). | — | — |
| Senses source | HSK 1 uses Mascot AI drafts, labelled in the app. Not decided: whether the owner wants human review before production, or a different source for HSK 2 → 7–9 | Keep AI drafts labelled; review the most common words first | Production confidence |
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
