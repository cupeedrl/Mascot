// "Từ của hôm nay": one catalog word per day at the learner's level, the same
// for the whole day, using the existing catalog and save APIs.

import {
  getHskEntry,
  getVocabularySet,
  importVocabularyEntries,
  listHskEntries,
  listVocabularySets,
  saveHskSense,
  type LearningTrack,
} from "../../api/client";
import { HSK_BROWSE_LEVELS, formatSensePos } from "../hsk/hskPresentation";
import { PARTS_OF_SPEECH } from "../vocabulary/partsOfSpeech";
import { dailyIndex } from "./homeSummary";

export interface WordOfTheDay {
  headword: string;
  pronunciation: string | null;
  meaning: string;
  partOfSpeech: string | null;
  levelCode: string;
  saved: boolean;
  /** Saves the word to "Từ vựng của tôi". */
  save: () => Promise<void>;
}

/** "noun" -> "Danh từ", using the labels of the vocabulary editor. */
function englishPartOfSpeech(value: string): string | null {
  if (!value || value === "unspecified") return null;
  const option = PARTS_OF_SPEECH.find((item) => item.value === value);
  return option ? option.label.replace(/\s*\(.*\)$/, "") : value;
}

/** HSK 7, 8 and 9 are browsed together as "HSK7-9". */
export function hskBrowseLevel(levelCode: string): string {
  return (HSK_BROWSE_LEVELS as readonly string[]).includes(levelCode) ? levelCode : "HSK7-9";
}

async function hskWord(track: LearningTrack, levelCode: string, dateIso: string): Promise<WordOfTheDay | null> {
  const level = hskBrowseLevel(levelCode);
  const first = await listHskEntries(track.id, { level, page: 1, pageSize: 1 });
  if (first.total === 0) return null;
  // A few entries may still await a Vietnamese meaning; try the next ones.
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const index = (dailyIndex(dateIso, `${track.id}:${level}`, first.total) + attempt) % first.total;
    const page = await listHskEntries(track.id, { level, page: index + 1, pageSize: 1 });
    const item = page.items[0];
    if (!item) continue;
    const detail = await getHskEntry(track.id, item.id);
    for (const interpretation of detail.interpretations) {
      const sense = interpretation.senses.find((candidate) => candidate.gloss_vi && (candidate.saveable || candidate.saved_vocabulary_id));
      if (!sense) continue;
      return {
        headword: interpretation.headword,
        pronunciation: sense.pronunciations[0] ?? interpretation.pronunciations[0] ?? item.raw_pinyin,
        meaning: sense.gloss_vi ?? "",
        partOfSpeech: sense.pos.length ? formatSensePos(sense.pos) : null,
        levelCode: item.level_code,
        saved: Boolean(sense.saved_vocabulary_id),
        save: async () => {
          await saveHskSense(track.id, item.id, sense.mapping_id);
        },
      };
    }
  }
  return null;
}

async function cefrWord(track: LearningTrack, levelCode: string, dateIso: string): Promise<WordOfTheDay | null> {
  const sets = await listVocabularySets({
    language: track.language.code,
    learningTrack: track.id,
    level: levelCode,
    pageSize: 100,
  });
  const candidates = sets.items.filter((set) => set.entry_count > 0);
  if (!candidates.length) return null;
  const set = candidates[dailyIndex(dateIso, `${track.id}:${levelCode}:set`, candidates.length)];
  const detail = await getVocabularySet(set.id, track.id);
  if (!detail.entries.length) return null;
  const entry = detail.entries[dailyIndex(dateIso, `${set.id}:entry`, detail.entries.length)];
  return {
    headword: entry.word,
    pronunciation: entry.ipa,
    meaning: entry.translation || entry.meaning,
    partOfSpeech: englishPartOfSpeech(entry.part_of_speech),
    levelCode: set.level_code,
    saved: entry.is_added,
    save: async () => {
      await importVocabularyEntries([entry.id]);
    },
  };
}

export function loadWordOfTheDay(
  track: LearningTrack,
  levelCode: string | null,
  dateIso: string,
): Promise<WordOfTheDay | null> {
  const level = levelCode ?? track.level_codes[0];
  if (!level) return Promise.resolve(null);
  return track.level_framework === "HSK" ? hskWord(track, level, dateIso) : cefrWord(track, level, dateIso);
}
