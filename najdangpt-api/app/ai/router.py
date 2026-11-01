"""Sanctumly adaptive text model router.

Primary text inference: Cloudflare Workers AI / Qwen3-30B-A3B-FP8.
Fallback/reasoning/research synthesis: Groq / GPT-OSS-120B.

Cloudflare is deliberately called non-streaming. Sanctumly's SSE endpoint
chunks the completed text downstream, avoiding upstream streaming adapter
issues and ensuring reasoning fields never leak into user-visible content.
"""
from dataclasses import dataclass
import logging
import re
import requests

from app.config import (
    CLOUDFLARE_ACCOUNT_ID,
    CLOUDFLARE_API_TOKEN,
    CLOUDFLARE_MODEL,
    CLOUDFLARE_NEURONS_PER_ESTIMATED_TOKEN,
    CLOUDFLARE_MIN_NEURON_RESERVATION,
    CLOUDFLARE_CREATOR_MAX_OUTPUT_TOKENS,
    CLOUDFLARE_FREE_MAX_OUTPUT_TOKENS,
    GROQ_MODEL,
)
from app.security.usage import (
    reserve_ai_budget,
    settle_ai_budget,
    estimate_chat_cost,
    calculate_chat_cost,
    estimate_input_tokens,
)
from app.ai.provider_state import (
    reserve_cloudflare_neurons,
    settle_cloudflare_neurons,
    release_cloudflare_reservation,
    cloudflare_provider_snapshot,
    mark_cloudflare_unavailable,
)

logger = logging.getLogger(__name__)


@dataclass
class RoutedCompletion:
    content: str
    provider: str
    model: str
    routing_reason: str
    fallback_used: bool
    neurons_used: float | None = None


class CloudflareProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        quota_exhausted: bool = False,
        neurons_used: float | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.quota_exhausted = quota_exhausted
        self.neurons_used = neurons_used


def _last_user_message(messages: list[dict]) -> str:
    for item in reversed(messages or []):
        if item.get("role") == "user":
            content = item.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return " ".join(
                    str(part.get("text", "")) for part in content if isinstance(part, dict)
                )
    return ""


def classify_complexity(messages: list[dict]) -> bool:
    """Conservative deterministic escalation for explicitly demanding tasks."""
    text = _last_user_message(messages).lower()
    high_reasoning_patterns = (
        r"\b(debug|debugging|traceback|stack trace|root cause|refactor|optimize|optimise)\b",
        r"\b(implement|build|architect|system design|technical design|production-ready)\b",
        r"\b(write|generate)\s+(code|a script|a program|a query|a function|a class)\b",
        r"\b(sql|python|gdscript|swift|swiftui|xcode)\b.{0,80}\b(debug|error|fix|implement|write|generate|build|query|script|code|refactor)\b",
        r"\b(comprehensive analysis|deep analysis|step[- ]by[- ]step reasoning|formal proof|derive)\b",
        r"\b(analy[sz]e|analysis|evaluate|assess)\b.{0,100}\b(in depth|deep|comprehensive|trade[- ]offs|scenarios)\b",
        r"\b(audit|security review|full qa|quality assurance)\b",
    )
    if any(re.search(pattern, text) for pattern in high_reasoning_patterns):
        return True
    # Long prompts with several explicit requirements are more likely to need
    # the reasoning model; a long ordinary conversation is not escalated solely
    # because its accumulated history is large.
    return len(text) > 1800 and (text.count("\n") >= 8 or text.count(";") >= 4)


def _with_qwen_no_think(messages: list[dict]) -> list[dict]:
    """Copy messages and disable Qwen's reasoning mode for user-facing chat."""
    copied = [dict(item) for item in messages]
    for item in reversed(copied):
        if item.get("role") == "user" and isinstance(item.get("content"), str):
            if "/no_think" not in item["content"]:
                item["content"] = "/no_think\n\n" + item["content"]
            break
    return copied


def _content_from_cloudflare(raw: dict) -> tuple[str, dict, str | None]:
    try:
        choice = raw["choices"][0]
        message = choice.get("message") or {}
    except (KeyError, IndexError, TypeError):
        raise CloudflareProviderError("Cloudflare returned an unexpected completion structure")

    usage = raw.get("usage") or {}
    measured_neurons = usage.get("neurons") if isinstance(usage, dict) else None
    try:
        measured_neurons = float(measured_neurons) if measured_neurons is not None else None
    except (TypeError, ValueError):
        measured_neurons = None

    content = message.get("content")
    if isinstance(content, list):
        content = "".join(
            str(part.get("text", "")) for part in content if isinstance(part, dict)
        )
    content = content.strip() if isinstance(content, str) else ""
    finish_reason = choice.get("finish_reason")
    if not content or finish_reason == "length":
        # Never return message.reasoning or message.reasoning_content as the
        # answer. A null content field or length-truncated completion is not a
        # usable final answer; record consumed Neurons and retry via GPT-OSS.
        problem = "no final answer" if not content else "answer was truncated at the token limit"
        raise CloudflareProviderError(
            f"Cloudflare returned an incomplete answer ({problem}; finish_reason={finish_reason})",
            neurons_used=measured_neurons,
        )
    return content, usage, finish_reason


def _cloudflare_error(response: requests.Response) -> CloudflareProviderError:
    try:
        body = response.json()
    except ValueError:
        body = {"error": response.text[:1000]}
    message = str(body)[:1800]
    lowered = message.lower()
    quota_terms = (
        "neuron", "daily quota", "daily limit", "quota exceeded",
        "free allocation", "usage limit exceeded", "exceeded your limit",
    )
    is_quota = response.status_code in {402, 403, 429} and any(term in lowered for term in quota_terms)
    # Cloudflare may encode account-level quota exhaustion as a non-429 error;
    # explicit quota language is sufficient to trip the shared circuit breaker.
    if any(term in lowered for term in quota_terms) and (
        response.status_code in {400, 402, 403, 429}
    ):
        is_quota = True
    return CloudflareProviderError(
        f"Cloudflare HTTP {response.status_code}: {message}",
        status_code=response.status_code,
        quota_exhausted=is_quota,
    )


def _call_cloudflare(messages: list[dict], max_output_tokens: int) -> tuple[str, float | None]:
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        raise CloudflareProviderError("Cloudflare credentials are not configured")

    endpoint = (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{CLOUDFLARE_ACCOUNT_ID}/ai/v1/chat/completions"
    )
    payload = {
        "model": CLOUDFLARE_MODEL,
        "messages": _with_qwen_no_think(messages),
        "stream": False,
        "max_tokens": max_output_tokens,
        "temperature": 0.7,
        "top_p": 0.8,
        "top_k": 20,
    }
    try:
        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}"},
            json=payload,
            timeout=(10, 120),
        )
    except requests.RequestException as exc:
        raise CloudflareProviderError(f"Cloudflare network error: {type(exc).__name__}") from exc

    if response.status_code >= 400:
        raise _cloudflare_error(response)
    try:
        raw = response.json()
    except ValueError as exc:
        raise CloudflareProviderError("Cloudflare returned invalid JSON") from exc

    content, usage, _finish_reason = _content_from_cloudflare(raw)
    neurons = usage.get("neurons")
    try:
        neurons = float(neurons) if neurons is not None else None
    except (TypeError, ValueError):
        neurons = None
    return content, neurons


def _estimate_neurons(messages: list[dict], max_output_tokens: int) -> float:
    # The existing character-based input estimator is intentionally
    # conservative, so discount it and reserve only a fraction of the output
    # ceiling. Actual Neurons from Cloudflare replace the estimate on success.
    estimated_input = estimate_input_tokens(messages) * 0.55
    expected_output = max(128, int(max_output_tokens * 0.45))
    estimated_tokens = estimated_input + expected_output
    return max(
        CLOUDFLARE_MIN_NEURON_RESERVATION,
        estimated_tokens * CLOUDFLARE_NEURONS_PER_ESTIMATED_TOKEN,
    )


def _call_groq(
    messages: list[dict], account, db, groq_client,
    *, is_creator: bool, max_output_tokens: int, routing_reason: str,
    fallback_used: bool,
) -> RoutedCompletion:
    reservation = reserve_ai_budget(
        account, db, estimate_chat_cost(messages, max_output_tokens, vision=False)
    )
    try:
        kwargs = {
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": 0.7,
            "top_p": 0.95,
        }
        if not is_creator:
            kwargs["max_tokens"] = max_output_tokens
        response = groq_client.chat.completions.create(**kwargs)
        message = response.choices[0].message
        response_text = getattr(message, "content", None) or ""
        if not response_text.strip():
            raise RuntimeError("Groq returned no final answer")
        actual_cost = calculate_chat_cost(
            getattr(response, "usage", None),
            vision=False,
            fallback_input_tokens=estimate_input_tokens(messages),
            fallback_output_tokens=max(1, len(response_text) // 3),
        )
        settle_ai_budget(db, reservation, actual_cost)
        reservation = None
        return RoutedCompletion(
            content=response_text,
            provider="groq",
            model=GROQ_MODEL,
            routing_reason=routing_reason,
            fallback_used=fallback_used,
        )
    except Exception:
        if reservation is not None:
            settle_ai_budget(db, reservation, 0.0)
        raise


def generate_text(
    messages: list[dict], account, db, groq_client,
    *, is_creator: bool, is_research: bool = False,
) -> RoutedCompletion:
    """Route one text completion; provider quota is global, app limits are per user."""
    max_output_tokens = (
        CLOUDFLARE_CREATOR_MAX_OUTPUT_TOKENS
        if is_creator else CLOUDFLARE_FREE_MAX_OUTPUT_TOKENS
    )

    # Research synthesis and explicitly complex work go to GPT-OSS directly.
    # They do not waste the shared Qwen daily Neuron allocation.
    if is_research:
        return _call_groq(
            messages, account, db, groq_client,
            is_creator=is_creator, max_output_tokens=max_output_tokens,
            routing_reason="research_synthesis", fallback_used=False,
        )
    if classify_complexity(messages):
        return _call_groq(
            messages, account, db, groq_client,
            is_creator=is_creator, max_output_tokens=max_output_tokens,
            routing_reason="high_complexity", fallback_used=False,
        )

    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        logger.warning("Cloudflare is not configured; routing text completion to Groq")
        return _call_groq(
            messages, account, db, groq_client,
            is_creator=is_creator, max_output_tokens=max_output_tokens,
            routing_reason="cloudflare_not_configured", fallback_used=True,
        )

    estimated_neurons = _estimate_neurons(messages, max_output_tokens)
    neuron_reservation = reserve_cloudflare_neurons(db, estimated_neurons)
    if neuron_reservation is None:
        snapshot = cloudflare_provider_snapshot(db)
        reason = (
            "cloudflare_quota_exhausted"
            if snapshot["status"] == "exhausted"
            else "cloudflare_temporarily_unavailable"
        )
        logger.info("Qwen skipped (%s); routing to GPT-OSS", reason)
        return _call_groq(
            messages, account, db, groq_client,
            is_creator=is_creator, max_output_tokens=max_output_tokens,
            routing_reason=reason, fallback_used=True,
        )

    try:
        response_text, actual_neurons = _call_cloudflare(messages, max_output_tokens)
        settle_cloudflare_neurons(db, neuron_reservation, actual_neurons)
        neuron_reservation = None
        return RoutedCompletion(
            content=response_text,
            provider="cloudflare",
            model=CLOUDFLARE_MODEL,
            routing_reason="primary_qwen",
            fallback_used=False,
            neurons_used=actual_neurons,
        )
    except CloudflareProviderError as exc:
        if exc.quota_exhausted:
            release_cloudflare_reservation(
                db, neuron_reservation, exhausted=True, error=str(exc)
            )
            neuron_reservation = None
            reason = "cloudflare_quota_exhausted"
        else:
            if exc.neurons_used is not None:
                settle_cloudflare_neurons(db, neuron_reservation, exc.neurons_used)
            elif exc.status_code is None or exc.status_code >= 500:
                # The request may have reached inference before a timeout or
                # server error. Count the reservation conservatively.
                settle_cloudflare_neurons(db, neuron_reservation, None)
            else:
                release_cloudflare_reservation(db, neuron_reservation, error=str(exc))
            neuron_reservation = None
            mark_cloudflare_unavailable(db, str(exc))
            reason = "cloudflare_provider_unavailable"
        logger.warning("Cloudflare Qwen failed; falling back to Groq: %s", type(exc).__name__)
        return _call_groq(
            messages, account, db, groq_client,
            is_creator=is_creator, max_output_tokens=max_output_tokens,
            routing_reason=reason, fallback_used=True,
        )
    except Exception as exc:
        if neuron_reservation is not None:
            release_cloudflare_reservation(
                db, neuron_reservation, error=type(exc).__name__, cooldown_seconds=60
            )
        mark_cloudflare_unavailable(db, type(exc).__name__)
        logger.exception("Unexpected Qwen routing failure; falling back to Groq")
        return _call_groq(
            messages, account, db, groq_client,
            is_creator=is_creator, max_output_tokens=max_output_tokens,
            routing_reason="cloudflare_provider_unavailable", fallback_used=True,
        )
