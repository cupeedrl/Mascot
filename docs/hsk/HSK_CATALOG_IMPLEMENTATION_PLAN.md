# HSK 1–6 normalized catalog — implementation plan (milestone 1)

> Status: implemented locally and tested on a disposable PostgreSQL 16 container. **Not deployed, committed or published.**
> This plan supersedes nothing in `docs/architecture/HSK_SCHEMA_DESIGN.md` (Revision 8). Revision 8 is still an unapproved proposal. This milestone takes a deliberately smaller slice of it.

## 1. Observed starting point (audit)

| Area | What exists | File evidence |
|---|---|---|
| Chinese track | `zh` language and `general-chinese` track (`level_framework = HSK`) are seeded by a migration | `backend/alembic/versions/20260908_0011_seed_chinese_hsk_track.py` |
| Chinese catalog | One legacy set `hsk1-daily-foundations` with 8 Mascot-authored development cards (word, pinyin in `ipa`, English gloss, Vietnamese gloss, one example) | `backend/alembic/versions/20260908_0012_seed_chinese_sample_catalog.py`, `backend/app/catalog/data/zh/hsk1.json` |
| Catalog model | One flat card per row in `vocabulary_entries` (word, `ipa`, one POS string, one meaning, one translation). There is no release, source identity, level membership, multiple readings or multiple senses | `backend/app/models/vocabulary_entry.py`, `vocabulary_set.py` |
| Personal vocabulary | `vocabularies` is a user-owned snapshot with copied fields and progress counters, plus a nullable `source_vocabulary_entry_id` (`ON DELETE SET NULL`) | `backend/app/models/vocabulary.py` |
| Library API | `/vocabulary-sets`, `/vocabulary-entries/import`, `/vocabulary-sets/{id}/start-learning` | `backend/app/api/v1/routes/vocabulary_library.py` |
| Review and exercises | Operate only on `vocabularies` rows. They do not read catalog tables except for an optional eager load of the legacy entry | `backend/app/services/review.py`, `exercise.py` |
| HSK 3.x data scripts | Offline enrichment/audit scripts. They reference third-party sources (`@leonsilicon/hsk3.1`, `ivankra/hsk30`, CC-CEDICT) and write only to `tmp/` | `backend/scripts/*hsk31*` |
| Frozen source | `D:\IERP\Projects\Mascot\_recovery\sources\official\CTI_HSK3_vocab_API_2026-10-30.json` sits outside the repository. It contains no provenance or permission file | — |

### Blockers for HSK 1–6 in the current model

1. A CTI record can carry several readings (`谁 shéi/shuí`), several POS values (`动、名`), and level annotations (`一级（三级）`). The flat card cannot represent these without flattening or fabricating.
2. The CTI snapshot contains **no meanings**. Every sense, gloss, Vietnamese translation and example therefore has to come from editorial or third-party enrichment, and each of those needs its own review and rights.
3. There is no release or publication state, so a partial import would be visible to users immediately.
4. Personal provenance is lost when a catalog row is deleted (`SET NULL`).
5. There is no permission evidence for the CTI source (see section 4).

### CTI snapshot facts (read-only inspection; no data copied into the repository)

- 10,999 records. API `id` is a string and `sort` is an integer. In this snapshot `id == sort` for every row, but the importer stores them independently and never derives one from the other.
- `sort` runs from 1 to 11000; **serial 2472 is missing**. It is preserved as a reported anomaly and no row is synthesized.
- POS (`cixing`): the key is absent on 460 rows and an empty string on 35.
- Raw words include homograph suffixes (`点1`, `点2`), and 57 surface forms repeat across records.
- Two rows have slash-separated multiple readings in `pinyin`.
- `levelName` has 28 distinct values, including annotated forms such as `一级（二级）（四级）` and the band `七-九级`.

## 2. Smallest coherent model (implemented)

All tables are new except for nullable additive columns on `vocabularies`. Migration: `backend/alembic/versions/20261110_0015_create_normalized_hsk_catalog.py`.

| Table | Purpose | Key guarantees (PostgreSQL) |
|---|---|---|
| `catalog_releases` | One immutable source capture per track: code, source name/version, SHA-256, manifest, `data_origin`, status, four independent permission statuses plus evidence | `UNIQUE(track, code)`; `UNIQUE(id, track)`; status/origin/permission CHECKs; **publication gate CHECK**: a `third_party` release can be `published` only when all four permissions are `approved`; **at most one published release per track** (partial unique index) |
| `catalog_source_entries` | One row per source record, with official raw fields kept verbatim (`raw_word`, `raw_pinyin`, `raw_pos` nullable, `raw_level_name`, `raw_payload`, `payload_sha256`) | `UNIQUE(release, id_type, id_value)`; partial `UNIQUE(release, official_serial)`; `UNIQUE(id, release)`; review-status CHECK |
| `catalog_source_entry_levels` | Level membership: one `primary` plus ordered `annotation` levels | Composite FK `(source_entry_id, release_id)` → source entry (prevents cross-release membership); one primary per source entry; level CHECK `HSK1..HSK6, HSK7-9` |
| `lexical_entries` | Release-independent lexical identity (`lexical_key`, simplified headword, optional traditional form, status) | `UNIQUE(language, lexical_key)` |
| `lexical_pronunciations` | Readings of a lexical entry | `UNIQUE(lexical, pinyin)`; `UNIQUE(id, lexical)` |
| `lexical_senses` | Reviewed meanings (`gloss_en`, `gloss_vi`, gloss source, review status, active/retired) | `UNIQUE(lexical, sense_key)`; `UNIQUE(id, lexical)`; at least one gloss |
| `lexical_sense_pos` | Zero or more POS annotations per sense. Missing POS means no rows; nothing is fabricated | PK `(sense, pos_code)`; controlled POS code CHECK |
| `lexical_sense_pronunciations` | Which reading(s) a sense uses | Composite FKs to sense and pronunciation **of the same lexical entry** |
| `lexical_variants` | Traditional or alternate forms, optionally tied to a reading | Composite FK `(pronunciation, lexical)` |
| `lexical_sense_examples` | Examples per sense, with their source | — |
| `catalog_source_mappings` | Source record → lexical entry (± reading, ± sense), with review status | Composite FK to source entry `(id, release)`; same-lexical composite FKs for reading and sense; composite FK `(sense, reading)` → sense–reading link when both are present; `UNIQUE NULLS NOT DISTINCT(source, lexical, reading, sense)` |
| `vocabularies` (+columns) | `catalog_source_entry_id`, `catalog_mapping_id`, `catalog_sense_id`, `catalog_pronunciation_id`, `catalog_snapshot` | All `ON DELETE RESTRICT`; composite FKs `(mapping, source)` and `(mapping, sense)`; `(sense, reading)` → link; CHECK that a catalog save has a mapping, sense and snapshot; partial `UNIQUE NULLS NOT DISTINCT(user, source, sense)` |

### Current-release mechanism (smaller replacement for Revision 8 pointer/cutover ledger)

- At most one `published` release per track, enforced by a partial unique index.
- The HSK read API serves **only** that release. If none exists, it returns an empty catalog with `release = null`. There is **no fallback** to drafts or to "all active sets".
- An admin may preview a draft by passing `release_id` explicitly. Ordinary users cannot.
- Switching releases is one transaction that retires the old release and publishes the new one; the unique index rejects two concurrent publishes.
- The legacy `/vocabulary-sets` (v1) API is untouched and does not read the new tables, so CEFR behaviour cannot change.

## 3. Import pipeline

`backend/app/catalog/hsk_import.py` plus the CLI `backend/scripts/import_hsk_release.py`.

- Input is a dataset directory containing `manifest.json` (release metadata, declared source SHA-256, permissions/evidence, data origin), `source.json` (CTI API shape or a plain record list) and an optional `review.json` (explicit, human-reviewed lexical/reading/sense/POS/variant/example mappings keyed by source record id).
- Validation covers manifest hash vs file hash; record id presence and uniqueness; serial type and uniqueness; serial gaps (reported, never filled); required word and pinyin; level parsing (unknown levels rejected, out-of-scope primary levels excluded); POS missing (absent and blank counted separately, stored as NULL); multi-reading pinyin and homograph suffixes (reported); review mappings must reference known records, readings must match a source reading, and sense–reading pairs must belong to the same lexical entry. Unparseable or ambiguous review rows are rejected and reported, never guessed.
- Records without an approved mapping stay **awaiting review**: their raw official fields are stored, and they have no senses.
- Imports are idempotent: upserts use natural keys, and re-importing a source record whose payload hash changed is rejected, because corrections require a new release. A rerun produces identical row counts and IDs.
- Releases are always created as `draft`. A separate `publish` command refuses to publish when the permission gate fails, when the import is incomplete, or (by default) when in-scope records are awaiting review.
- The importer never touches `vocabularies`.
- `--dry-run` validates and reports with no database connection at all. It is used for the real CTI counts.

## 4. Permission gate (decision required; nothing imported)

| Activity | Evidence found | Status |
|---|---|---|
| Store the CTI snapshot | None in the repository or in `_recovery/sources` (no licence or terms file; Revision 8 lists this as **UNKNOWN**) | **Not established** |
| Transform/enrich it | None | **Not established** |
| Redistribute it | None | **Not established** |
| Publish source or derived data in the product | None | **Not established** |

Therefore the CTI data is **not** in any migration, seed, fixture, database or API in this change. Tests use Mascot-authored synthetic records labelled `data_origin = synthetic_fixture`.

## 5. Explicitly deferred

Revision 8 SECURITY DEFINER functions and roles, actor contexts, append-only review events, the cutover ledger, and the 47/89/40 inventory. Also deferred: language composite FKs (OD-01), a global vs. Chinese POS policy (OD-02: this milestone uses a small controlled list), migrating the 8 legacy dev cards (OD-03: left as they are), lexical split/merge workflow (OD-12), HSK 7–9, a refresh-snapshot UX, and production rollout controls (OD-10).
