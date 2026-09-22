import type { LearningTrack } from "../api/client";

export function selectInitialTrack(
  tracks: LearningTrack[],
  persistedTrackId?: string | null,
): LearningTrack | null {
  return tracks.find((track) => track.id === persistedTrackId)
    ?? tracks.find((track) => track.language.code === "en")
    ?? tracks[0]
    ?? null;
}

export function pronunciationLabel(track: LearningTrack | null): string {
  return track?.language.code === "zh" ? "Pinyin" : "IPA";
}
