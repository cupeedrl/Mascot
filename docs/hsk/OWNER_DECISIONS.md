# HSK catalog — owner decisions

These are product-owner decisions recorded for release manifests (`permission_evidence`). They are not legal conclusions.

## OD-11: use of the official HSK 3.0 word list (2026-11-10)

- **Decided by:** project owner (Chu Quoc Dat), in the Claude Code session of 2026-11-10.
- **Source:** CTI HSK 3.0 vocabulary API snapshot `CTI_HSK3_vocab_API_2026-10-30.json`, SHA-256 `926f4e932527bf0c478c7c8232b0200ae0ea305e5b25882ef8ad87da5ab804ab`; topic syllabus from `HSK_Examination_Syllabus_2025.pdf` (CLEC, published 2025-11, effective 2026-07).
- **Owner statement (verbatim, Vietnamese):**
  > "t muốn dựa vào đấy để làm các app của t thôi, t đã có biến đổi theo để học theo nhóm từ mà. với lại từ vựng cũng đâu có thuộc bản quyền của ai, có phải t bê nguyên vào đâu. t muốn chia từ vựng theo từng cấp độ có các chủ đề con như phần học tiếng anh ý"
- **Recorded meaning:** the owner authorizes storing the list, transforming it (Mascot-authored meanings, translations, examples and topic grouping), and using the result in the owner's own apps, including the web product. Each of the four release permissions is set to `approved`, with this decision as evidence.
- **Not covered by this decision:** content from other sources that carry their own licence terms. CC-CEDICT, for example, is CC BY-SA. `leonsilicon/hsk3.1` has no licence file and is **not used**. `ivankra/hsk30` is not used either.
- **Advice given before the decision:** an individual word is generally not anyone's property, but a complete compiled list and other people's definitions may be. Publishing a verbatim copy of the full list is riskier than personal study. The owner made this decision after that advice.

## Product shape (2026-11-10)

- Vocabulary is grouped **by level, then by topic**, like the English (CEFR) library.
- Topics come from the official 2025 topic syllabus for each level (话题大纲). Assigning a word to a topic is Mascot editorial work, labelled as an AI suggestion where it was AI-generated.
