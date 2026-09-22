from __future__ import annotations

import re
import unicodedata
from typing import Literal


ResponseLanguageCode = Literal["vi", "en", "zh", "other"]

_VIETNAMESE_CHARACTERS = re.compile(
    r"[ăâđêôơưảãạằắẳẵặầấẩẫậẻẽẹềếểễệỉĩịỏõọồốổỗộờớởỡợ"
    r"ủũụừứửữựỷỹỵ]",
    re.IGNORECASE,
)
_HAN_CHARACTERS = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
_JAPANESE_KANA = re.compile(r"[\u3040-\u30ff]")
_OTHER_SCRIPT_CHARACTERS = re.compile(
    r"[\u0400-\u04ff\u0600-\u06ff\uac00-\ud7af]"
)
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)

_VIETNAMESE_WORDS = {
    "ai", "bằng", "bao", "cần", "cho", "có", "của", "đang", "được",
    "giải", "gì", "hiện", "học", "hơn", "là", "mấy", "ngắn", "nghĩa",
    "nào", "ôn", "thế", "thêm", "thích", "tiến", "tiếng", "tôi", "trung",
    "từ", "vào", "việt",
}
_ENGLISH_WORDS = {
    "add", "another", "between", "can", "could", "current", "define", "does",
    "english", "example", "explain", "give", "how", "is", "learning", "many",
    "mean", "means", "my", "need", "please", "progress", "review", "sentence",
    "tell", "the", "to", "use", "vocabulary", "what", "words", "you",
}


def detect_response_language(message: str) -> ResponseLanguageCode:
    """Classify the latest user turn without another model call.

    The classifier intentionally favors Vietnamese for short or uncertain Latin
    input. Target-language words embedded in an otherwise clear Vietnamese or
    English sentence do not control the response language.
    """
    normalized = unicodedata.normalize("NFKC", message).strip().casefold()
    if not normalized:
        return "vi"

    words = _WORD.findall(normalized)
    word_set = set(words)
    vietnamese_score = len(word_set & _VIETNAMESE_WORDS)
    english_score = len(word_set & _ENGLISH_WORDS)

    if _VIETNAMESE_CHARACTERS.search(normalized) or vietnamese_score >= 2:
        return "vi"
    if english_score >= 2 or (english_score >= 1 and len(words) >= 2):
        return "en"
    if _JAPANESE_KANA.search(normalized):
        return "other"
    if len(_HAN_CHARACTERS.findall(normalized)) >= 2:
        return "zh"
    if _OTHER_SCRIPT_CHARACTERS.search(normalized) or (
        len(words) >= 2 and any(ord(char) > 127 for char in normalized)
    ):
        return "other"
    return "vi"


def response_language_system_hint(language_code: ResponseLanguageCode) -> str:
    instructions = {
        "vi": "Respond in Vietnamese.",
        "en": "Respond in English.",
        "zh": "Respond in Chinese.",
        "other": (
            "Respond in the same recognizable language as the latest user message "
            "where practical; if uncertain, respond in Vietnamese."
        ),
    }
    return (
        "Backend-owned response-language policy for this turn: "
        f"{instructions[language_code]} "
        "This is determined from the latest meaningful user message. The active "
        "learning track, earlier turns, and tool output must not change it. Keep "
        "target-language vocabulary and examples in the language being learned."
    )


def localized_action_copy(
    language_code: ResponseLanguageCode, word: str
) -> tuple[str, str]:
    if language_code == "en":
        return (
            f'Add "{word}" to My Vocabulary',
            f'I prepared "{word}" for your vocabulary. Review the details and use Confirm or Cancel below.',
        )
    if language_code == "zh":
        return (
            f'将“{word}”添加到我的词汇表',
            f'我已准备好将“{word}”添加到你的词汇表。请检查详情，然后使用下方的确认或取消按钮。',
        )
    return (
        f'Thêm “{word}” vào Từ vựng của tôi',
        f'Mình đã chuẩn bị từ “{word}”. Hãy kiểm tra thông tin rồi dùng nút Xác nhận hoặc Hủy bên dưới.',
    )
