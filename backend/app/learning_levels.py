from __future__ import annotations

from types import MappingProxyType

CEFR_LEVEL_CODES = ("A1", "A2", "B1", "B2", "C1", "C2")
HSK_LEVEL_CODES = tuple(f"HSK{number}" for number in range(1, 10))

LEVEL_CODES_BY_FRAMEWORK = MappingProxyType(
    {
        "CEFR": CEFR_LEVEL_CODES,
        "HSK": HSK_LEVEL_CODES,
    }
)


def get_level_codes(level_framework: str) -> tuple[str, ...]:
    """Return the ordered level codes supported by a learning framework."""
    return LEVEL_CODES_BY_FRAMEWORK.get(level_framework.strip().upper(), ())


# Extra codes accepted on personal vocabulary without changing the listed
# levels: HSK 3.0 publishes levels 7-9 as one combined band ("HSK7-9").
EXTRA_VALID_LEVEL_CODES = MappingProxyType({"HSK": ("HSK7-9",)})


def is_valid_level(level_framework: str, level_code: str) -> bool:
    code = level_code.strip().upper()
    framework = level_framework.strip().upper()
    return code in get_level_codes(framework) or code in EXTRA_VALID_LEVEL_CODES.get(framework, ())
