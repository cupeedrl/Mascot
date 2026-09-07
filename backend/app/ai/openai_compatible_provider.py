from __future__ import annotations

import json
import logging
import time
from typing import Any, List

from pydantic import ValidationError

from app.ai.chat_schema import Message, ProviderResult, ProviderToolCall
from app.ai.prompts import (
    EXERCISE_GENERATOR_SYSTEM_PROMPT,
    VOCABULARY_ASSISTANT_SYSTEM_PROMPT,
    exercise_user_prompt,
    vocabulary_user_prompt,
)
from app.ai.provider import (
    AIProviderAuthenticationError,
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderNotConfiguredError,
    AIProviderQuotaError,
    AIProviderRateLimitError,
    AIProviderResponseError,
    AIProviderTimeoutError,
    ChatAIProvider,
    ExerciseAIProvider,
    VocabularyAIProvider,
)
from app.schemas.ai_exercise import AIFillInBlankBatch, AIMultipleChoiceBatch
from app.schemas.ai_vocabulary import VocabularyCandidate

logger = logging.getLogger(__name__)
usage_logger = logging.getLogger("ai_usage")

MAX_RETRIES = 2
INITIAL_BACKOFF_SECONDS = 0.5


class OpenAICompatibleVocabularyProvider(VocabularyAIProvider, ExerciseAIProvider, ChatAIProvider):
    """Base vocabulary provider using the OpenAI-compatible chat completions API."""

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
        feature: str,
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
            APIStatusError,
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

        start_time = time.perf_counter()
        attempts = 0
        backoff = INITIAL_BACKOFF_SECONDS

        while True:
            attempts += 1
            try:
                response = client.responses.parse(
                    model=self._model,
                    input=messages,
                    text_format=text_format,
                    max_output_tokens=max_output_tokens,
                )
                duration_ms = round((time.perf_counter() - start_time) * 1000)

                # Extract token usage if present
                usage: dict[str, Any] = {}
                raw_usage = getattr(response, "usage", None)
                if raw_usage:
                    usage = {
                        "prompt_tokens": getattr(raw_usage, "prompt_tokens", None),
                        "completion_tokens": getattr(raw_usage, "completion_tokens", None),
                        "total_tokens": getattr(raw_usage, "total_tokens", None),
                    }

                parsed = response.output_parsed
                if parsed is None:
                    logger.warning(
                        "AI structured response missing parsed output (stage=provider_parse, model=%s, schema=%s, status=%s)",
                        self._model,
                        text_format.__name__,
                        getattr(response, "status", "unknown"),
                    )
                    usage_logger.warning(
                        "AI call error: empty_parsed, feature=%s, model=%s, duration_ms=%s, tokens=%s, attempts=%s",
                        feature,
                        self._model,
                        duration_ms,
                        usage,
                        attempts,
                    )
                    raise AIProviderResponseError(
                        "provider_parse", "provider returned empty parsed structure"
                    )

                usage_logger.info(
                    "AI call success: feature=%s, model=%s, duration_ms=%s, tokens=%s, attempts=%s",
                    feature,
                    self._model,
                    duration_ms,
                    usage,
                    attempts,
                )
                return parsed

            except (AuthenticationError, PermissionDeniedError, NotFoundError) as exc:
                duration_ms = round((time.perf_counter() - start_time) * 1000)
                usage_logger.warning(
                    "AI call error: config/auth, feature=%s, model=%s, duration_ms=%s, error=%s",
                    feature,
                    self._model,
                    duration_ms,
                    type(exc).__name__,
                )
                raise AIProviderConfigurationError from exc

            except RateLimitError as exc:
                duration_ms = round((time.perf_counter() - start_time) * 1000)
                quota_codes = {
                    "insufficient_quota",
                    "credit_balance_exhausted",
                    "organization_spend_limit_exceeded",
                    "project_spend_limit_exceeded",
                    "organization_usage_limit_exceeded",
                }
                if getattr(exc, "code", None) in quota_codes or getattr(exc, "type", None) == "insufficient_quota":
                    usage_logger.warning(
                        "AI call error: quota_exhausted, feature=%s, model=%s, duration_ms=%s",
                        feature,
                        self._model,
                        duration_ms,
                    )
                    raise AIProviderQuotaError from exc

                if attempts <= MAX_RETRIES:
                    logger.info(
                        "Retrying AI call after rate limit (attempt=%s/%s, backoff=%ss, feature=%s)",
                        attempts,
                        MAX_RETRIES + 1,
                        backoff,
                        feature,
                    )
                    time.sleep(backoff)
                    backoff *= 2
                    continue

                usage_logger.warning(
                    "AI call error: rate_limit, feature=%s, model=%s, duration_ms=%s, attempts=%s",
                    feature,
                    self._model,
                    duration_ms,
                    attempts,
                )
                raise AIProviderRateLimitError from exc

            except APITimeoutError as exc:
                duration_ms = round((time.perf_counter() - start_time) * 1000)
                if attempts <= MAX_RETRIES:
                    logger.info(
                        "Retrying AI call after timeout (attempt=%s/%s, backoff=%ss, feature=%s)",
                        attempts,
                        MAX_RETRIES + 1,
                        backoff,
                        feature,
                    )
                    time.sleep(backoff)
                    backoff *= 2
                    continue

                usage_logger.warning(
                    "AI call error: timeout, feature=%s, model=%s, duration_ms=%s, attempts=%s",
                    feature,
                    self._model,
                    duration_ms,
                    attempts,
                )
                raise AIProviderTimeoutError from exc

            except (APIConnectionError, APIStatusError) as exc:
                duration_ms = round((time.perf_counter() - start_time) * 1000)
                is_server_error = isinstance(exc, APIStatusError) and exc.status_code >= 500
                is_connection_error = isinstance(exc, APIConnectionError)

                if (is_server_error or is_connection_error) and attempts <= MAX_RETRIES:
                    logger.info(
                        "Retrying AI call after network/server error (attempt=%s/%s, backoff=%ss, feature=%s, status=%s)",
                        attempts,
                        MAX_RETRIES + 1,
                        backoff,
                        feature,
                        getattr(exc, "status_code", "conn_error"),
                    )
                    time.sleep(backoff)
                    backoff *= 2
                    continue

                usage_logger.warning(
                    "AI call error: provider_network_or_5xx, feature=%s, model=%s, duration_ms=%s, attempts=%s, error=%s",
                    feature,
                    self._model,
                    duration_ms,
                    attempts,
                    type(exc).__name__,
                )
                raise AIProviderError from exc

            except ValidationError as exc:
                duration_ms = round((time.perf_counter() - start_time) * 1000)
                logger.warning(
                    "AI structured response parsing failed (stage=provider_parse, model=%s, schema=%s, validation_errors=%s)",
                    self._model,
                    text_format.__name__,
                    len(exc.errors()),
                )
                usage_logger.warning(
                    "AI call error: validation_error, feature=%s, model=%s, duration_ms=%s, errors=%s",
                    feature,
                    self._model,
                    duration_ms,
                    len(exc.errors()),
                )
                raise AIProviderResponseError(
                    "provider_parse", "provider response did not match the requested schema"
                ) from exc

            except OpenAIError as exc:
                duration_ms = round((time.perf_counter() - start_time) * 1000)
                usage_logger.warning(
                    "AI call error: general_openai_error, feature=%s, model=%s, duration_ms=%s, error=%s",
                    feature,
                    self._model,
                    duration_ms,
                    type(exc).__name__,
                )
                raise AIProviderError from exc

    def generate_vocabulary(
        self, word: str, part_of_speech: str, translation: str
    ) -> object:
        candidate = self._parse_structured(
            feature="vocabulary_enrichment",
            messages=[
                {"role": "system", "content": VOCABULARY_ASSISTANT_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": vocabulary_user_prompt(word, part_of_speech, translation),
                },
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
            feature=f"exercise_{exercise_type}",
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

    def generate_chat_response(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        if not self._api_key:
            raise AIProviderNotConfiguredError

        from openai import (
            APIConnectionError,
            APIStatusError,
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

        start_time = time.perf_counter()
        attempts = 0
        backoff = INITIAL_BACKOFF_SECONDS

        while True:
            attempts += 1
            try:
                response = client.chat.completions.create(
                    model=self._model,
                    messages=messages,  # type: ignore[arg-type]
                    max_tokens=self._max_output_tokens,
                )
                duration_ms = round((time.perf_counter() - start_time) * 1000)

                usage: dict[str, Any] = {}
                raw_usage = getattr(response, "usage", None)
                if raw_usage:
                    usage = {
                        "prompt_tokens": getattr(raw_usage, "prompt_tokens", None),
                        "completion_tokens": getattr(raw_usage, "completion_tokens", None),
                        "total_tokens": getattr(raw_usage, "total_tokens", None),
                    }

                content = response.choices[0].message.content
                if content is None:
                    raise AIProviderResponseError(
                        "chat_completion", "provider returned empty completion content"
                    )

                usage_logger.info(
                    "AI call success: feature=ai_chat, model=%s, duration_ms=%s, tokens=%s, attempts=%s",
                    self._model,
                    duration_ms,
                    usage,
                    attempts,
                )
                return content

            except (AuthenticationError, PermissionDeniedError, NotFoundError) as exc:
                duration_ms = round((time.perf_counter() - start_time) * 1000)
                usage_logger.warning(
                    "AI call error: config/auth, feature=ai_chat, model=%s, duration_ms=%s, error=%s",
                    self._model,
                    duration_ms,
                    type(exc).__name__,
                )
                raise AIProviderConfigurationError from exc

            except RateLimitError as exc:
                duration_ms = round((time.perf_counter() - start_time) * 1000)
                quota_codes = {
                    "insufficient_quota",
                    "credit_balance_exhausted",
                    "organization_spend_limit_exceeded",
                    "project_spend_limit_exceeded",
                    "organization_usage_limit_exceeded",
                }
                if getattr(exc, "code", None) in quota_codes or getattr(exc, "type", None) == "insufficient_quota":
                    usage_logger.warning(
                        "AI call error: quota_exhausted, feature=ai_chat, model=%s, duration_ms=%s",
                        self._model,
                        duration_ms,
                    )
                    raise AIProviderQuotaError from exc

                if attempts <= MAX_RETRIES:
                    time.sleep(backoff)
                    backoff *= 2
                    continue

                usage_logger.warning(
                    "AI call error: rate_limit, feature=ai_chat, model=%s, duration_ms=%s, attempts=%s",
                    self._model,
                    duration_ms,
                    attempts,
                )
                raise AIProviderRateLimitError from exc

            except APITimeoutError as exc:
                duration_ms = round((time.perf_counter() - start_time) * 1000)
                if attempts <= MAX_RETRIES:
                    time.sleep(backoff)
                    backoff *= 2
                    continue

                usage_logger.warning(
                    "AI call error: timeout, feature=ai_chat, model=%s, duration_ms=%s, attempts=%s",
                    self._model,
                    duration_ms,
                    attempts,
                )
                raise AIProviderTimeoutError from exc

            except (APIConnectionError, APIStatusError) as exc:
                duration_ms = round((time.perf_counter() - start_time) * 1000)
                is_server_error = isinstance(exc, APIStatusError) and exc.status_code >= 500
                is_connection_error = isinstance(exc, APIConnectionError)

                if (is_server_error or is_connection_error) and attempts <= MAX_RETRIES:
                    time.sleep(backoff)
                    backoff *= 2
                    continue

                usage_logger.warning(
                    "AI call error: provider_network_or_5xx, feature=ai_chat, model=%s, duration_ms=%s, attempts=%s, error=%s",
                    self._model,
                    duration_ms,
                    attempts,
                    type(exc).__name__,
                )
                raise AIProviderError from exc

            except OpenAIError as exc:
                duration_ms = round((time.perf_counter() - start_time) * 1000)
                usage_logger.warning(
                    "AI call error: general_openai_error, feature=ai_chat, model=%s, duration_ms=%s, error=%s",
                    self._model,
                    duration_ms,
                    type(exc).__name__,
                )
                raise AIProviderError from exc

    def generate_chat_response_with_tools(
        self,
        messages: List[Message],
        tool_definitions: List[dict],
    ) -> ProviderResult:
        if not self._api_key:
            raise AIProviderNotConfiguredError

        from openai import (
            APIConnectionError,
            APIStatusError,
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

        provider_messages: list[dict[str, Any]] = []
        for msg in messages:
            role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", None)
            if role == "system":
                content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", "")
                provider_messages.append({"role": "system", "content": content})
            elif role == "user":
                content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", "")
                provider_messages.append({"role": "user", "content": content})
            elif role == "assistant":
                content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
                raw_tool_calls = msg.get("tool_calls") if isinstance(msg, dict) else getattr(msg, "tool_calls", None)
                payload: dict[str, Any] = {"role": "assistant", "content": content}
                if raw_tool_calls:
                    payload["tool_calls"] = [
                        {
                            "id": tc.get("id") if isinstance(tc, dict) else getattr(tc, "id"),
                            "type": "function",
                            "function": {
                                "name": tc.get("name") if isinstance(tc, dict) else getattr(tc, "name"),
                                "arguments": tc.get("arguments") if isinstance(tc, dict) else getattr(tc, "arguments"),
                            },
                        }
                        for tc in raw_tool_calls
                    ]
                provider_messages.append(payload)
            elif role == "tool":
                call_id = msg.get("tool_call_id") if isinstance(msg, dict) else getattr(msg, "tool_call_id")
                content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", "")
                provider_messages.append({"role": "tool", "tool_call_id": call_id, "content": content})
            else:
                raise AIProviderResponseError(
                    "unsupported_chat_role",
                    f"Unsupported chat role: {role}",
                )

        provider_tools: list[dict[str, Any]] = []
        for tool in tool_definitions:
            name = tool.get("name") if isinstance(tool, dict) else getattr(tool, "name")
            desc = tool.get("description") if isinstance(tool, dict) else getattr(tool, "description")
            params = tool.get("parameters") if isinstance(tool, dict) else getattr(tool, "parameters")
            provider_tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": desc,
                    "parameters": params,
                },
            })

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": provider_messages,
            "max_tokens": self._max_output_tokens,
        }
        if provider_tools:
            kwargs["tools"] = provider_tools
            kwargs["tool_choice"] = "auto"

        start_time = time.perf_counter()
        attempts = 0
        backoff = INITIAL_BACKOFF_SECONDS

        while True:
            attempts += 1
            try:
                response = client.chat.completions.create(**kwargs)
                duration_ms = round((time.perf_counter() - start_time) * 1000)

                usage: dict[str, Any] = {}
                raw_usage = getattr(response, "usage", None)
                if raw_usage:
                    usage = {
                        "prompt_tokens": getattr(raw_usage, "prompt_tokens", None),
                        "completion_tokens": getattr(raw_usage, "completion_tokens", None),
                        "total_tokens": getattr(raw_usage, "total_tokens", None),
                    }

                if not response.choices:
                    raise AIProviderResponseError(
                        "empty_choices",
                        "Provider returned empty choices array",
                    )

                choice = response.choices[0]
                choice_msg = choice.message
                content = choice_msg.content

                parsed_tool_calls: list[ProviderToolCall] = []
                if choice_msg.tool_calls:
                    for tc in choice_msg.tool_calls:
                        f_name = tc.function.name if tc.function else ""
                        f_args = tc.function.arguments if tc.function else "{}"
                        if not isinstance(f_args, str):
                            f_args = json.dumps(f_args)
                        parsed_tool_calls.append({
                            "id": tc.id,
                            "name": f_name,
                            "arguments": f_args,
                        })

                if not content and not parsed_tool_calls:
                    raise AIProviderResponseError(
                        "empty_response",
                        "Provider returned neither text content nor tool calls",
                    )

                usage_logger.info(
                    "AI call success: feature=ai_chat_tools, model=%s, duration_ms=%s, tokens=%s, attempts=%s",
                    self._model,
                    duration_ms,
                    usage,
                    attempts,
                )

                result: ProviderResult = {}
                if content is not None:
                    result["content"] = content
                if parsed_tool_calls:
                    result["tool_calls"] = parsed_tool_calls
                return result

            except (AuthenticationError, PermissionDeniedError, NotFoundError) as exc:
                duration_ms = round((time.perf_counter() - start_time) * 1000)
                usage_logger.warning(
                    "AI call error: config/auth, feature=ai_chat_tools, model=%s, duration_ms=%s, error=%s",
                    self._model,
                    duration_ms,
                    type(exc).__name__,
                )
                raise AIProviderConfigurationError from exc

            except RateLimitError as exc:
                duration_ms = round((time.perf_counter() - start_time) * 1000)
                quota_codes = {
                    "insufficient_quota",
                    "credit_balance_exhausted",
                    "organization_spend_limit_exceeded",
                    "project_spend_limit_exceeded",
                    "organization_usage_limit_exceeded",
                }
                if getattr(exc, "code", None) in quota_codes or getattr(exc, "type", None) == "insufficient_quota":
                    usage_logger.warning(
                        "AI call error: quota_exhausted, feature=ai_chat_tools, model=%s, duration_ms=%s",
                        self._model,
                        duration_ms,
                    )
                    raise AIProviderQuotaError from exc

                if attempts <= MAX_RETRIES:
                    time.sleep(backoff)
                    backoff *= 2
                    continue

                usage_logger.warning(
                    "AI call error: rate_limit, feature=ai_chat_tools, model=%s, duration_ms=%s, attempts=%s",
                    self._model,
                    duration_ms,
                    attempts,
                )
                raise AIProviderRateLimitError from exc

            except APITimeoutError as exc:
                duration_ms = round((time.perf_counter() - start_time) * 1000)
                if attempts <= MAX_RETRIES:
                    time.sleep(backoff)
                    backoff *= 2
                    continue

                usage_logger.warning(
                    "AI call error: timeout, feature=ai_chat_tools, model=%s, duration_ms=%s, attempts=%s",
                    self._model,
                    duration_ms,
                    attempts,
                )
                raise AIProviderTimeoutError from exc

            except (APIConnectionError, APIStatusError) as exc:
                duration_ms = round((time.perf_counter() - start_time) * 1000)
                is_server_error = isinstance(exc, APIStatusError) and exc.status_code >= 500
                is_connection_error = isinstance(exc, APIConnectionError)

                if (is_server_error or is_connection_error) and attempts <= MAX_RETRIES:
                    time.sleep(backoff)
                    backoff *= 2
                    continue

                usage_logger.warning(
                    "AI call error: provider_network_or_5xx, feature=ai_chat_tools, model=%s, duration_ms=%s, attempts=%s, error=%s",
                    self._model,
                    duration_ms,
                    attempts,
                    type(exc).__name__,
                )
                raise AIProviderError from exc

            except OpenAIError as exc:
                duration_ms = round((time.perf_counter() - start_time) * 1000)
                usage_logger.warning(
                    "AI call error: general_openai_error, feature=ai_chat_tools, model=%s, duration_ms=%s, error=%s",
                    self._model,
                    duration_ms,
                    type(exc).__name__,
                )
                raise AIProviderError from exc
