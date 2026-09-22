# HSK meaning review guide

Review `meaning_review.csv` row by row. The source HSK level is authoritative and must not be changed.

Allowed `review_status` values:

- `approved`: the candidate meaning is already suitable; copy it into `final_english_meaning`.
- `resolved`: enter a concise, evidence-supported final English dictionary meaning.
- `deferred`: ambiguity remains or external research is needed.
- `rejected`: the source record is unsuitable or malformed.
- `pending`: not reviewed yet.

For variant/reference rows, follow the referenced dictionary entry only when the target, pronunciation, and sense are unambiguous. Do not infer a HSK sense from general knowledge.

For multiple pronunciations, use the existing Pinyin as the primary disambiguator. For multiple senses, retain closely related senses separated by semicolons, but do not combine unrelated lexical senses.

Final meanings must be concise, dictionary-style, semantically clear, and suitable for later Vietnamese translation. Leave `final_english_meaning` empty for pending, deferred, or rejected rows.

Validate the completed CSV without touching production data:

```powershell
python scripts/hsk31_meaning_review.py validate --review tmp/hsk31_meaning_audit/meaning_review.csv
```
