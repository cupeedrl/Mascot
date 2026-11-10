# HSK 1–6 import report (2026-11-10)

All numbers are produced by `backend/app/catalog/hsk_import.py` and are not hand-entered.

## A. Frozen CTI snapshot: validation dry run only (nothing stored)

- File: `D:\IERP\Projects\Mascot\_recovery\sources\official\CTI_HSK3_vocab_API_2026-10-30.json`, which is **outside the repository**.
- SHA-256: `926f4e932527bf0c478c7c8232b0200ae0ea305e5b25882ef8ad87da5ab804ab` (1,203,282 bytes).
- Command: `python -m scripts.import_hsk_release validate <dir> --report-dir <scratch> --counts-only`. This needs no database connection. The manifest declared `data_origin = third_party` and set all four permissions to `unknown`.
- The data was **not** loaded into any database, migration, seed, fixture or API. No per-record content is reproduced here.

Records in file: **10,999**. Excluded because the primary level is out of scope (HSK 7–9): **5,600**. Serial gap: **2472**, which falls between two HSK 5 records. It is preserved as an anomaly and no row is synthesized. API `id` and `sort` are stored separately and are never derived from each other.

| Level | Source rows | Accepted¹ | Ambiguous² | Awaiting review³ | Rejected | Duplicate | Missing POS⁴ | Missing serial (within level) | Mapped⁵ | Publicly eligible⁶ |
|---|---|---|---|---|---|---|---|---|---|---|
| HSK1 | 300 | 300 | 24 | 276 | 0 | 0 | 6 | 0 | 0 | 0 |
| HSK2 | 200 | 200 | 34 | 166 | 0 | 0 | 4 | 0 | 0 | 0 |
| HSK3 | 500 | 500 | 37 | 463 | 0 | 0 | 6 | 0 | 0 | 0 |
| HSK4 | 1000 | 1000 | 54 | 946 | 0 | 0 | 6 | 0 | 0 | 0 |
| HSK5 | 1599 | 1599 | 45 | 1554 | 0 | 0 | 12 | 1 | 0 | 0 |
| HSK6 | 1800 | 1800 | 31 | 1769 | 0 | 0 | 19 | 0 | 0 | 0 |
| **Total** | **5399** | **5399** | **225** | **5174** | **0** | **0** | **53** | **1** | **0** | **0** |

Flag counts (one record can carry several flags):

| Level | homograph suffix (`点1`) | multiple readings (`a/b`) | POS key absent | POS blank | POS with parentheses | repeated surface form |
|---|---|---|---|---|---|---|
| HSK1 | 6 | 1 | 3 | 3 | 15 | 3 |
| HSK2 | 9 | 0 | 2 | 2 | 22 | 8 |
| HSK3 | 5 | 0 | 2 | 4 | 21 | 11 |
| HSK4 | 10 | 1 | 4 | 2 | 32 | 17 |
| HSK5 | 19 | 0 | 11 | 1 | 9 | 17 |
| HSK6 | 12 | 0 | 16 | 3 | 3 | 17 |

1. Accepted: passed source-identity, level and required-field validation, so the record would be stored with its raw official fields.
2. Ambiguous: carries at least one flag that needs a human decision before interpretation (homograph suffix, multiple readings, repeated surface form, parenthesized POS).
3. Awaiting review: valid, with no ambiguity flags, but no reviewed lexical/sense mapping exists. **The CTI payload contains no meanings**, so every record needs editorial senses before it can be saved.
4. Missing POS: `cixing` key absent plus empty-string `cixing`. These are stored as NULL and never filled in.
5. Mapped: has at least one approved review mapping. There is no approved review dataset, so this is 0.
6. Publicly eligible: mapped **and** the release's four permissions are approved. All four are `unknown`, so this is 0.

## B. Synthetic fixture release (loaded in tests)

The source is `backend/tests/hsk_fixtures.py`: Mascot-authored, labelled `data_origin = synthetic_fixture`, **not official HSK**. It has 16 records in file, 1 excluded (HSK7-9), 1 rejected with an unknown level (`十级`, which cannot be attributed to a level row), and serial gap 6.

| Level | Source rows | Accepted | Ambiguous | Awaiting review | Rejected | Duplicate | Missing POS | Missing serial (within level) | Mapped | Publicly eligible |
|---|---|---|---|---|---|---|---|---|---|---|
| HSK1 | 3 | 2 | 0 | 0 | 0 | 1 | 0 | 0 | 2 | 2 |
| HSK2 | 3 | 2 | 0 | 0 | 1 | 0 | 0 | 0 | 2 | 2 |
| HSK3 | 2 | 2 | 0 | 0 | 0 | 0 | 1 | 1 | 2 | 2 |
| HSK4 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 2 |
| HSK5 | 2 | 2 | 0 | 1 | 0 | 0 | 0 | 0 | 1 | 1 |
| HSK6 | 2 | 2 | 1 | 0 | 0 | 0 | 1 | 0 | 1 | 1 |

Review-file rejections: 2 lexical entries (a sense reading not belonging to its lexical entry; a POS code outside the list) and 4 mappings (a reading not in the lexical entry, an unknown source record, an excluded HSK7-9 record, and an unlinked sense/reading pair). There is also 1 duplicate mapping. These counts are asserted in `backend/tests/test_hsk_import_validation.py`.
