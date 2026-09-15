"""Small, safe Groq connectivity diagnostic; intentionally not part of app paths."""
from __future__ import annotations

import importlib.metadata
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict


def load_env() -> None:
    for path in (Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env", Path(__file__).resolve().parents[1] / ".env"):
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key in {"GROQ_API_KEY", "GROQ_BASE_URL", "GROQ_MODEL"}:
                os.environ.setdefault(key, value)


def safe_proxy(value: str | None) -> dict[str, object]:
    if not value:
        return {"set": False}
    parsed = urlsplit(value if "://" in value else f"http://{value}")
    return {"set": True, "host": parsed.hostname or "<unparseable>"}


def safe_failure(exc: BaseException) -> dict[str, object]:
    response = getattr(exc, "response", None)
    return {
        "exception_class": type(exc).__name__,
        "message": str(exc)[:500],
        "cause_class": type(exc.__cause__).__name__ if exc.__cause__ else None,
        "cause_message": str(exc.__cause__)[:500] if exc.__cause__ else None,
        "http_status": getattr(response, "status_code", None),
    }


def strict_body(model: str, strict: bool = True) -> dict[str, object]:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": "Return exactly the value requested."},
            {"role": "user", "content": "Return the string ok."},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "tiny_response",
                "strict": strict,
                "schema": {
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                    "required": ["value"],
                    "additionalProperties": False,
                },
            },
        },
    }


class TinyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str


class TranslationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    word: str
    translation: str


class TranslationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    translations: list[TranslationItem]


def strict_completion(client, model: str, schema: type[BaseModel], prompt: str):
    return client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=32,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "strict": True,
                "schema": schema.model_json_schema(),
            },
        },
    )


def main() -> None:
    load_env()
    from openai import OpenAI

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
    client = OpenAI(api_key=api_key, base_url=base_url, timeout=20, max_retries=0)
    body = strict_body(model)
    report: dict[str, object] = {
        "provider": "groq",
        "base_url": base_url,
        "model": model,
        "openai_version": importlib.metadata.version("openai"),
        "httpx_version": importlib.metadata.version("httpx"),
        "proxies": {key: safe_proxy(os.getenv(key)) for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")},
        "certificates": {key: {"set": bool(os.getenv(key))} for key in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE")},
    }
    report["sanitized_request_body"] = body
    try:
        response = client.chat.completions.create(**body)
        content = response.choices[0].message.content or ""
        report["openai_strict"] = {"success": True, "content": content[:100]}
        print(report)
        return
    except Exception as exc:
        report["openai_strict"] = {"success": False, **safe_failure(exc)}

    raw_result: dict[str, object]
    try:
        request = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            raw_result = {"success": True, "status": response.status, "body": response.read().decode("utf-8")[:500]}
    except Exception as exc:
        raw_result = {"success": False, **safe_failure(exc)}
        if isinstance(exc, urllib.error.HTTPError):
            raw_result["body"] = exc.read().decode("utf-8", errors="replace")[:500]
    report["raw_http_strict"] = raw_result

    if not raw_result.get("success"):
        best_effort_body = strict_body(model, strict=False)
        try:
            response = client.chat.completions.create(**best_effort_body)
            report["openai_best_effort"] = {"success": True, "content": (response.choices[0].message.content or "")[:100]}
        except Exception as exc:
            report["openai_best_effort"] = {"success": False, **safe_failure(exc)}
    print(report)


if __name__ == "__main__":
    main()
