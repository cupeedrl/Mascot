import unicodedata


def normalize_word(value: str) -> str:
    """Create a stable General English lookup form without changing display text."""
    return unicodedata.normalize("NFKC", value.strip()).casefold()
