from __future__ import annotations

import json
import logging
import time
from types import SimpleNamespace
from typing import Any, Callable, List, TypeVar

from pydantic import ValidationError

from app.ai.chat_schema import Message, ProviderResult, ProviderToolCall
from app.ai.prompts import (
    exercise_generator_system_prompt,
    VOCABULARY_ASSISTANT_SYSTEM_PROMPT,
    exercise_user_prompt,
    vocabulary_assistant_system_prompt,
    vocabulary_user_prompt,
)
from app.ai.provider import (
    AIProviderAuthenticationError,
    AIProviderConfigurationError,
    AIProviderError,
    AIProviderNotConfiguredError,
    AIProviderQuotaError,
    AIProviderRequestError,
    AIProviderRateLimitError,
    AIProviderResponseError,
    AIProviderTimeoutError,
    ChatAIProvider,
    ExerciseAIProvider,
    VocabularyAIProvider,
)
from app.ai.token_usage import record_provider_usage
from app.schemas.ai_exercise import AIFillInBlankBatch, AIMultipleChoiceBatch
from app.schemas.ai_vocabulary import VocabularyCandidate

logger = logging.getLogger(__name__)
usage_logger = logging.getLogger("ai_usage")

MAX_RETRIES = 2
INITIAL_BACKOFF_SECONDS = 0.5

QUOTA_ERROR_CODES = frozenset({
    "insufficient_quota",
    "credit_balance_exhausted",
    "organization_spend_limit_exceeded",
    "project_spend_limit_exceeded",
    "organization_usage_limit_exceeded",
})

_T = TypeVar("_T")

# Receives ("delta", text) and ("discard", "") while a chat reply streams.
StreamEventCallback = Callable[[str, str], None]


def _parse_chat_completion(response: Any) -> tuple[str | None, list[ProviderToolCall]]:
    if not response.choices:
        raise AIProviderResponseError(
            "empty_choices",
            "Provider returned empty choices array",
        )

    choice_msg = response.choices[0].message
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
    return choice_msg.content, parsed_tool_calls


def _consume_chat_stream(
    stream: Any, on_event: StreamEventCallback
) -> tuple[str | None, list[ProviderToolCall], Any]:
    """Read a streamed chat completion into the same shape as a non-streamed one.

    Text deltas are forwarded as they arrive. Tool calls arrive as fragments
    keyed by index (id and name first, arguments split across chunks) and are
    joined here. Returns (content, tool_calls, object with ``.usage`` or None).
    """
    content_parts: list[str] = []
    calls: dict[int, dict[str, str]] = {}
    usage_source: Any = None

    for chunk in stream:
        if getattr(chunk, "usage", None) is not None:
            usage_source = chunk
        # Groq reports usage on the final chunk under x_groq.usage instead.
        x_groq = getattr(chunk, "x_groq", None)
        groq_usage = (
            x_groq.get("usage") if isinstance(x_groq, dict) else getattr(x_groq, "usage", None)
        )
        if groq_usage is not None and usage_source is None:
            if isinstance(groq_usage, dict):
                groq_usage = SimpleNamespace(**groq_usage)
            usage_source = SimpleNamespace(usage=groq_usage)

        for choice in getattr(chunk, "choices", None) or []:
            delta = choice.delta
            if delta is None:
                continue
            if delta.content:
                content_parts.append(delta.content)
                on_event("delta", delta.content)
            for fragment in delta.tool_calls or []:
                slot = calls.setdefault(fragment.index, {"id": "", "name": "", "arguments": ""})
                if fragment.id:
                    slot["id"] = fragment.id
                if fragment.function is not None:
                    slot["name"] += fragment.function.name or ""
                    slot["arguments"] += fragment.function.arguments or ""

    tool_calls: list[ProviderToolCall] = [
        {"id": slot["id"], "name": slot["name"], "arguments": slot["arguments"]}
        for _, slot in sorted(calls.items())
    ]
    return ("".join(content_parts) or None), tool_calls, usage_source


class OpenAICompatibleVocabularyProvider(VocabularyAIProvider, ExerciseAIProvider, ChatAIProvider):
    """Base vocabulary provider using the OpenAI-compatible chat completions API."""

    # Stored in ai_usage_logs.provider for the calls this provider serves.
    provider_name = "openai_compatible"
    # generate_chat_response_with_tools accepts on_event (see ProviderChatModel).
    supports_streaming = True
    # Ask for a final usage chunk when streaming (stream_options.include_usage).
    stream_include_usage = True

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_output_tokens: int,
        exercise_max_output_tokens: int = 4000,
        base_url: str | None = None,
        exercise_reasoning_effort: str | None = None,
        exercise_model: str | None = None,
    ) -> None:
        self._api_key = api_key.strip()
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_output_tokens = max_output_tokens
        self._exercise_max_output_tokens = exercise_max_output_tokens
        self._exercise_reasoning_effort = exercise_reasoning_effort
        self._exercise_model = exercise_model or model
        self._base_url = base_url.rstrip("/") if base_url else None

    @property
    def has_api_key(self) -> bool:
        return bool(self._api_key)

    def _client(self) -> Any:
        from openai import OpenAI

        client_options: dict[str, object] = {
            "api_key": self._api_key,
            "timeout": self._timeout_seconds,
            "max_retries": 0,
        }
        if self._base_url is not None:
            client_options["base_url"] = self._base_url

        return OpenAI(**client_options)

    def _call_with_retries(
        self,
        feature: str,
        attempt: Callable[[int], _T],
        *,
        start_time: float,
        log_retries: bool = False,
    ) -> _T:
        """Run ``attempt(attempt_number)`` with Mascot's retry and error mapping.

        Rate limits, timeouts and 5xx/network errors are retried up to
        MAX_RETRIES times with exponential backoff; everything else maps to an
        AIProvider*Error at once. Exceptions raised by ``attempt`` that are not
        SDK errors (e.g. AIProviderResponseError) propagate unchanged.

        Other 4xx responses (not 401/403/404/429) become AIProviderRequestError
        with sanitized details: the request itself was rejected, so it is
        neither retried nor handed to a fallback provider. ``log_retries`` logs
        each retry; structured calls set it, chat calls do not.
        """
        from openai import (
            APIConnectionError,
            APIStatusError,
            APITimeoutError,
            AuthenticationError,
            NotFoundError,
            OpenAIError,
            PermissionDeniedError,
            RateLimitError,
        )

        attempts = 0
        backoff = INITIAL_BACKOFF_SECONDS

        while True:
            attempts += 1
            try:
                return attempt(attempts)

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
                if getattr(exc, "code", None) in QUOTA_ERROR_CODES or getattr(exc, "type", None) == "insufficient_quota":
                    usage_logger.warning(
                        "AI call error: quota_exhausted, feature=%s, model=%s, duration_ms=%s",
                        feature,
                        self._model,
                        duration_ms,
                    )
                    raise AIProviderQuotaError from exc

                if attempts <= MAX_RETRIES:
                    if log_retries:
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
                    if log_retries:
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
                if isinstance(exc, APIStatusError) and exc.status_code < 500:
                    body = getattr(exc, "body", None)
                    safe_details: dict[str, object] = {}
                    if isinstance(body, dict):
                        error = body.get("error")
                        if isinstance(error, dict):
                            for key in ("type", "message", "param", "code"):
                                if error.get(key) is not None:
                                    safe_details[key] = str(error[key])[:500]
                    usage_logger.warning(
                        "AI call error: provider_request, feature=%s, model=%s, status=%s, details=%s",
                        feature, self._model, exc.status_code, safe_details,
                    )
                    raise AIProviderRequestError(exc.status_code, safe_details) from exc
                is_server_error = isinstance(exc, APIStatusError) and exc.status_code >= 500
                is_connection_error = isinstance(exc, APIConnectionError)

                if (is_server_error or is_connection_error) and attempts <= MAX_RETRIES:
                    if log_retries:
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

    def _parse_structured(
        self,
        *,
        feature: str,
        messages: list[dict[str, str]],
        text_format: type[VocabularyCandidate]
        | type[AIMultipleChoiceBatch]
        | type[AIFillInBlankBatch],
        max_output_tokens: int,
        reasoning_effort: str | None = None,
        model: str | None = None,
    ) -> object:
        if not self._api_key:
            raise AIProviderNotConfiguredError

        client = self._client()
        start_time = time.perf_counter()

        def attempt(attempts: int) -> object:
            extra_options: dict[str, Any] = {}
            if reasoning_effort is not None:
                extra_options["reasoning"] = {"effort": reasoning_effort}
            response = client.responses.parse(
                model=model or self._model,
                input=messages,
                text_format=text_format,
                max_output_tokens=max_output_tokens,
                **extra_options,
            )
            duration_ms = round((time.perf_counter() - start_time) * 1000)

            # Count tokens even when the parsed output is unusable: they were billed.
            usage = record_provider_usage(response, model or self._model, self.provider_name)

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

        try:
            return self._call_with_retries(
                feature,
                attempt,
                start_time=start_time,
                log_retries=True,
            )
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

    def generate_vocabulary(
        self,
        word: str,
        part_of_speech: str,
        translation: str,
        learning_context: dict[str, object] | None = None,
    ) -> object:
        candidate = self._parse_structured(
            feature="vocabulary_enrichment",
            messages=[
                {
                    "role": "system",
                    "content": vocabulary_assistant_system_prompt(learning_context),
                },
                {
                    "role": "user",
                    "content": vocabulary_user_prompt(
                        word, part_of_speech, translation, learning_context
                    ),
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
            model=self._exercise_model,
            reasoning_effort=self._exercise_reasoning_effort,
            feature=f"exercise_{exercise_type}",
            messages=[
                {
                    "role": "system",
                    "content": exercise_generator_system_prompt(exercise_type),
                },
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

        client = self._client()
        start_time = time.perf_counter()

        def attempt(attempts: int) -> str:
            response = client.chat.completions.create(
                model=self._model,
                messages=messages,  # type: ignore[arg-type]
                max_tokens=self._max_output_tokens,
            )
            duration_ms = round((time.perf_counter() - start_time) * 1000)

            usage = record_provider_usage(response, self._model, self.provider_name)

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

        return self._call_with_retries("ai_chat", attempt, start_time=start_time)

    def generate_chat_response_with_tools(
        self,
        messages: List[Message],
        tool_definitions: List[dict],
        on_event: StreamEventCallback | None = None,
    ) -> ProviderResult:
        """One provider turn. With ``on_event`` the reply is streamed.

        Streamed text is reported as ``("delta", text)`` while it arrives and
        ``("discard", "")`` when a retry restarts the answer. Deltas are a
        display-only draft: the returned ProviderResult is still the complete,
        not yet validated result, exactly as without streaming.
        """
        if not self._api_key:
            raise AIProviderNotConfiguredError

        client = self._client()

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

        if on_event is not None:
            kwargs["stream"] = True
            if self.stream_include_usage:
                kwargs["stream_options"] = {"include_usage": True}

        def attempt(attempts: int) -> ProviderResult:
            if on_event is not None and attempts > 1:
                # A retry restarts the answer: drop any partial draft already shown.
                on_event("discard", "")
            response = client.chat.completions.create(**kwargs)
            if on_event is None:
                duration_ms = round((time.perf_counter() - start_time) * 1000)
                usage = record_provider_usage(response, self._model, self.provider_name)
                content, parsed_tool_calls = _parse_chat_completion(response)
            else:
                content, parsed_tool_calls, usage_source = _consume_chat_stream(
                    response, on_event
                )
                duration_ms = round((time.perf_counter() - start_time) * 1000)
                usage = record_provider_usage(usage_source, self._model, self.provider_name)

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

        return self._call_with_retries("ai_chat_tools", attempt, start_time=start_time)
