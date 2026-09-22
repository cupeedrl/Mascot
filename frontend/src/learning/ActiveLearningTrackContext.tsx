import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { getLearningTracks, type LearningTrack } from "../api/client";
import { selectInitialTrack } from "./trackMetadata";

const STORAGE_KEY = "mascot.activeLearningTrackId";

interface ActiveLearningTrackValue {
  tracks: LearningTrack[];
  activeTrack: LearningTrack | null;
  setActiveTrackId: (trackId: string) => void;
  isLoading: boolean;
}

const ActiveLearningTrackContext = createContext<ActiveLearningTrackValue | null>(null);

export function ActiveLearningTrackProvider({ children }: { children: ReactNode }) {
  const [tracks, setTracks] = useState<LearningTrack[]>([]);
  const [activeTrackId, setActiveTrackIdState] = useState(
    () => localStorage.getItem(STORAGE_KEY) ?? "",
  );
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let active = true;
    getLearningTracks()
      .then((items) => {
        if (!active) return;
        setTracks(items);
        setActiveTrackIdState((storedId) => {
          const selected = selectInitialTrack(items, storedId);
          if (selected) localStorage.setItem(STORAGE_KEY, selected.id);
          return selected?.id ?? "";
        });
      })
      .catch(() => {
        if (active) setTracks([]);
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => { active = false; };
  }, []);

  const value = useMemo<ActiveLearningTrackValue>(() => ({
    tracks,
    activeTrack: tracks.find((item) => item.id === activeTrackId) ?? null,
    setActiveTrackId: (trackId) => {
      if (!tracks.some((item) => item.id === trackId)) return;
      localStorage.setItem(STORAGE_KEY, trackId);
      setActiveTrackIdState(trackId);
    },
    isLoading,
  }), [activeTrackId, isLoading, tracks]);

  return (
    <ActiveLearningTrackContext.Provider value={value}>
      {children}
    </ActiveLearningTrackContext.Provider>
  );
}

export function useActiveLearningTrack(): ActiveLearningTrackValue {
  const value = useContext(ActiveLearningTrackContext);
  if (!value) throw new Error("useActiveLearningTrack must be used inside its provider");
  return value;
}

export { pronunciationLabel } from "./trackMetadata";
