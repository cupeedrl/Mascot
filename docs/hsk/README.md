# HSK 3.0 vocabulary in Mascot — start here

Learners study Chinese the same way as English: **level → topic → words**. The levels follow HSK 3.0: HSK 1–6, plus the combined HSK 7–9 band, as published. Topics come from the official 2025 topic syllabus (话题大纲).

## Documents

| File | What it covers |
|---|---|
| [OWNER_DECISIONS.md](OWNER_DECISIONS.md) | The owner's decision on using the official list, and the product shape (level → topic) |
| [HSK_CATALOG_IMPLEMENTATION_PLAN.md](HSK_CATALOG_IMPLEMENTATION_PLAN.md) | Data model, guarantees, and what was deliberately deferred |
| [HSK_CATALOG_STATUS.md](HSK_CATALOG_STATUS.md) | What works, verification results, open decisions, runbook |
| [HSK_IMPORT_REPORT.md](HSK_IMPORT_REPORT.md) | Source counts per level (10,999 records, serial gap 2472, missing POS) |
| `../architecture/` | Earlier design proposals (Revision 8 and the independent reviews). This is history: the implementation is a smaller slice of that design |

## Content status by level

| Level | Official words | Topic cards with words (official + Mascot) | Meanings and topic assignment | Loaded locally |
|---|---|---|---|---|
| HSK 1 | 300 | 15 + 1 | Done, 300/300 | Yes |
| HSK 2 | 200 | 15 + 1 (3 official cards have no words: 工作情况, 职业, 饮食文化) | Done, 200/200 | Yes |
| HSK 3 | 500 | 21 + 1 (教育问题 has no words) | Done, 500/500 | Yes |
| HSK 4 | 1,000 | 31 + 1 | Done, 1,000/1,000 | Yes |
| HSK 5 | 1,599 | 29 + 1 | Done, 1,599/1,599 | Yes |
| HSK 6 | 1,800 | 24 + 1 (古代科技 has no words) | Done, 1,800/1,800 | Yes |
| HSK 7–9 | 5,600 | 29 + 1 | Done, 5,600/5,600 (430 four-character idioms glossed by their figurative meaning) | Yes |

All meanings are Mascot AI drafts (Claude, 2026-11-11), shown in the app as the meaning source. HSK 2–6 and HSK 7–9 were each drafted in 12 parallel batches. Each batch was validated for complete ids, 4 non-empty fields and valid topic codes (0 problems), and homographs were checked by hand (for example 等1 "đợi" vs 等2 "vân vân", 乘1 "đi (xe)" vs 乘2 "nhân"). The local release is `hsk-2025-hsk1-9` (10,999 words, 652 topics, 0 import issues). Large topics are split in the app into study-sized parts of at most 50 words (near-equal, in official serial order), shown as "Phần k/n" cards. For example HSK 7–9 人际交往 (1,006 words) becomes 21 parts of 47–48 words. After splitting there are 18/16/24/39/50/48/130 cards for HSK 1/2/3/4/5/6/7–9, and none has more than 49 words. Topic cards without words are hidden in the app.

The official topic tree for all seven levels is extracted and verified against the counts printed in the syllabus. Vietnamese topic names exist for all levels.

## Where the data lives (outside git)

`D:\IERP\Projects\Mascot\_recovery\sources\` contains:
- `official/`: CTI word-list snapshot and the 2025 syllabus PDF, both unchanged.
- `derived/hsk-2025/topic_tree.json`: the official topic tree for all levels.
- `derived/hsk-2025/content/`:
  - `hsk1.tsv`: `record id|topic code|English|Vietnamese`;
  - `topic_codes.json`;
  - `topic_names_vi.json`.
- `derived/hsk-2025/release-hsk1/`: the built importer dataset (`manifest.json`, `review.json`).

## Adding a level

1. Add `<level>.tsv` (for example `hsk2.tsv` or `hsk79.tsv`), topic codes for the level in `topic_codes.json`, and Vietnamese topic names in `topic_names_vi.json`.
2. Build the dataset (from `backend/`):
   ```bash
   python -m scripts.build_hsk_dataset --cti <CTI json> --tree <topic_tree.json> --content <content dir> --levels HSK1 HSK2 --release-code hsk-2025-hsk1-2 --out <out dir>
   ```
3. Validate without a database:
   ```bash
   python -m scripts.import_hsk_release validate <out dir> --report-dir <report dir>
   ```
4. Import into the target database (always created as a draft), then publish. Publishing retires the previous release; saved words and learning progress are kept.
   ```bash
   python -m scripts.import_hsk_release import <out dir> --database-url <url>
   ```
   ```bash
   python -m scripts.import_hsk_release publish --track general-chinese --release <code> --database-url <url>
   ```

## Rules the data follows

- Official fields (word, pinyin, POS, level, serial) are stored exactly as published. A missing POS stays missing, and parenthesized POS labels are not used.
- Meanings are labelled with their source (`Mascot AI draft (Claude), 2026-11-11` for HSK 1) and are shown in the app.
- A word is assigned only to topics of its own level; the database enforces this.
- Function words that no official communicative topic covers go into one Mascot topic, "Từ vựng nền tảng → Đại từ & hư từ", marked `source = mascot`.
