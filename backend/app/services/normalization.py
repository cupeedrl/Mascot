import unicodedata


def clean_display_text(value: str) -> str:
    """Normalize Unicode and whitespace while preserving user-facing casing."""
    normalized = unicodedata.normalize("NFKC", value.strip())
    return " ".join(normalized.split())


def normalize_text(value: str) -> str:
    """Create a stable comparison form for learner-owned text metadata."""
    return clean_display_text(value).casefold()


def normalize_word(value: str) -> str:
    """Create a stable General English lookup form without changing display text."""
    return normalize_text(value)


def clean_topic(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = clean_display_text(value)
    return cleaned or None


def normalize_topic(value: str) -> str:
    return normalize_text(value)
