import {
  type FocusEvent,
  type KeyboardEvent,
  useEffect,
  useId,
  useMemo,
  useState,
} from "react";
import { Check, LoaderCircle, Plus, Tag } from "lucide-react";

import { listTopicSuggestions, type TopicSuggestion } from "../api/client";

interface TopicComboboxProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  allowCreate?: boolean;
  disabled?: boolean;
  learningTrackId?: string;
}

function normalized(value: string): string {
  return value.trim().replace(/\s+/g, " ").toLocaleLowerCase();
}

function cleanDisplay(value: string): string {
  return value.trim().replace(/\s+/g, " ");
}

export function TopicCombobox({
  label,
  value,
  onChange,
  placeholder = "Work",
  allowCreate = true,
  disabled = false,
  learningTrackId,
}: TopicComboboxProps) {
  const listboxId = useId();
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<TopicSuggestion[]>([]);
  const [activeIndex, setActiveIndex] = useState(-1);

  useEffect(() => {
    if (!isOpen || disabled) return;
    let active = true;
    const timer = window.setTimeout(() => {
      setIsLoading(true);
      listTopicSuggestions(value, 20, learningTrackId)
        .then((response) => {
          if (!active) return;
          setSuggestions(response.items);
          setActiveIndex(-1);
        })
        .catch(() => {
          if (active) setSuggestions([]);
        })
        .finally(() => {
          if (active) setIsLoading(false);
        });
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [disabled, isOpen, learningTrackId, value]);

  const cleanedValue = cleanDisplay(value);
  const hasExactMatch = suggestions.some(
    (suggestion) => normalized(suggestion.name) === normalized(cleanedValue),
  );
  const canCreate = allowCreate && Boolean(cleanedValue) && !hasExactMatch;
  const optionCount = suggestions.length + (canCreate ? 1 : 0);

  const activeOptionId = useMemo(() => {
    if (activeIndex < 0) return undefined;
    return `${listboxId}-option-${activeIndex}`;
  }, [activeIndex, listboxId]);

  function selectTopic(topic: string) {
    onChange(cleanDisplay(topic));
    setIsOpen(false);
    setActiveIndex(-1);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Escape") {
      setIsOpen(false);
      setActiveIndex(-1);
      return;
    }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!isOpen) {
        setIsOpen(true);
        return;
      }
      if (!optionCount) return;
      setActiveIndex((current) => {
        if (event.key === "ArrowDown") return (current + 1) % optionCount;
        return current <= 0 ? optionCount - 1 : current - 1;
      });
      return;
    }
    if (event.key === "Enter" && isOpen && optionCount > 0) {
      event.preventDefault();
      const selectedIndex = activeIndex >= 0 ? activeIndex : 0;
      if (selectedIndex < suggestions.length) {
        selectTopic(suggestions[selectedIndex].name);
      } else if (canCreate) {
        selectTopic(cleanedValue);
      }
    }
  }

  function handleBlur(event: FocusEvent<HTMLDivElement>) {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
      setIsOpen(false);
      setActiveIndex(-1);
    }
  }

  return (
    <div className="topic-combobox" onBlur={handleBlur}>
      <label htmlFor={`${listboxId}-input`}>{label}</label>
      <div className="topic-input-wrap">
        <Tag size={16} aria-hidden="true" />
        <input
          id={`${listboxId}-input`}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={isOpen}
          aria-controls={listboxId}
          aria-activedescendant={activeOptionId}
          value={value}
          onChange={(event) => {
            onChange(event.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          maxLength={120}
          autoComplete="off"
          disabled={disabled}
        />
        {isLoading && <LoaderCircle className="topic-spinner" size={16} aria-label="Đang tải chủ đề" />}
      </div>

      {isOpen && (
        <div className="topic-options" id={listboxId} role="listbox">
          {suggestions.map((suggestion, index) => (
            <button
              id={`${listboxId}-option-${index}`}
              className={activeIndex === index ? "active" : ""}
              type="button"
              role="option"
              aria-selected={normalized(value) === normalized(suggestion.name)}
              key={normalized(suggestion.name)}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => selectTopic(suggestion.name)}
            >
              <span>
                <strong>{suggestion.name}</strong>
                <small>{suggestion.vocabulary_count} từ</small>
              </span>
              {normalized(value) === normalized(suggestion.name) && <Check size={16} />}
            </button>
          ))}
          {canCreate && (
            <button
              id={`${listboxId}-option-${suggestions.length}`}
              className={`topic-create-option ${activeIndex === suggestions.length ? "active" : ""}`}
              type="button"
              role="option"
              aria-selected="false"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => selectTopic(cleanedValue)}
            >
              <Plus size={16} /> Create “{cleanedValue}”
            </button>
          )}
          {!isLoading && suggestions.length === 0 && !canCreate && (
            <p className="topic-empty">Không có chủ đề phù hợp.</p>
          )}
        </div>
      )}
    </div>
  );
}
