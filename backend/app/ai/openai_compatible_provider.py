from __future__ import annotations

import json

from pydantic import ValidationError

from app.ai.prompts import (
    EXERCISE_GENERATOR_SYSTEM_PROMPT,
    VOCABULARY_ASSISTANT_SYSTEM_PROMPT,
    exercise_user_prompt,
    vocabulary_user_prompt,
)
from app.ai.provider import (
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderNotConfiguredError,
    AIProviderQuotaError,
    AIProviderRateLimitError,
    AIProviderResponseError,
    AIProviderTimeoutError,
)
from app.schemas.ai_exercise import AIFillInBlankBatch, AIMultipleChoiceBatch
from app.schemas.ai_vocabulary import VocabularyCandidate


class OpenAICompatibleVocabularyProvider:
    """Vocabulary provider for OpenAI-compatible Responses APIs."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_output_tokens: int,
        exercise_max_output_tokens: int = 4000,
        base_url: str | None = None,
    ) -> None:
        self._api_key = api_key.strip()
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_output_tokens = max_output_tokens
        self._exercise_max_output_tokens = exercise_max_output_tokens
        self._base_url = base_url.rstrip("/") if base_url else None

    def _parse_structured(
        self,
        *,
        messages: list[dict[str, str]],
        text_format: type[VocabularyCandidate]
        | type[AIMultipleChoiceBatch]
        | type[AIFillInBlankBatch],
        max_output_tokens: int,
    ) -> object:
        if not self._api_key:
            raise AIProviderNotConfiguredError

        from openai import (
            APIConnectionError,
            APITimeoutError,
            AuthenticationError,
            NotFoundError,
            OpenAI,
            OpenAIError,
            PermissionDeniedError,
            RateLimitError,
        )

        client_options: dict[str, object] = {
            "api_key": self._api_key,
            "timeout": self._timeout_seconds,
            "max_retries": 0,
        }
        if self._base_url is not None:
            client_options["base_url"] = self._base_url

        client = OpenAI(**client_options)
        try:
            response = client.responses.parse(
                model=self._model,
                input=messages,
                text_format=text_format,
                max_output_tokens=max_output_tokens,
            )
        except APITimeoutError as exc:
            raise AIProviderTimeoutError from exc
        except APIConnectionError as exc:
            raise AIProviderError from exc
        except RateLimitError as exc:
            quota_codes = {
                "insufficient_quota",
                "credit_balance_exhausted",
                "organization_spend_limit_exceeded",
                "project_spend_limit_exceeded",
                "organization_usage_limit_exceeded",
            }
            if exc.code in quota_codes or exc.type == "insufficient_quota":
                raise AIProviderQuotaError from exc
            raise AIProviderRateLimitError from exc
        except (AuthenticationError, PermissionDeniedError, NotFoundError) as exc:
            raise AIProviderConfigurationError from exc
        except ValidationError as exc:
            raise AIProviderResponseError from exc
        except OpenAIError as exc:
            raise AIProviderError from exc

        parsed = response.output_parsed
        if parsed is None:
            raise AIProviderResponseError
        return parsed

    def generate_vocabulary(self, word: str) -> object:
        candidate = self._parse_structured(
            messages=[
                {"role": "system", "content": VOCABULARY_ASSISTANT_SYSTEM_PROMPT},
                {"role": "user", "content": vocabulary_user_prompt(word)},
            ],
            text_format=VocabularyCandidate,
            max_output_tokens=self._max_output_tokens,
        )
        return candidate.model_dump()

    def generate_exercises(
        self,
        vocabulary_context: list[dict[str, object]],
        exercise_type: str,
        count: int,
    ) -> object:
        if exercise_type == "multiple_choice":
            response_format = AIMultipleChoiceBatch
        elif exercise_type == "fill_in_blank":
            response_format = AIFillInBlankBatch
        else:
            raise AIProviderResponseError

        vocabulary_json = json.dumps(
            vocabulary_context,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        batch = self._parse_structured(
            messages=[
                {"role": "system", "content": EXERCISE_GENERATOR_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": exercise_user_prompt(
                        vocabulary_json,
                        exercise_type,
                        count,
                    ),
                },
            ],
            text_format=response_format,
            max_output_tokens=self._exercise_max_output_tokens,
        )
        return batch.model_dump(mode="json")
