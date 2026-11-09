"""Sanctumly adaptive text model router.

Primary text inference: Cloudflare Workers AI / Google Gemma 4 26B A4B.
Fallback/reasoning/research synthesis: Groq / GPT-OSS-120B.

Cloudflare is deliberately called non-streaming. Sanctumly's SSE endpoint
chunks the completed text downstream, preserving the existing client contract
and ensuring any model-side reasoning fields never reach the user.
"""
from dataclasses import dataclass
from time import perf_counter
import logging
import os
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
    GROQ_REASONING_DEFAULT,
    GROQ_REASONING_DEEP,
    GROQ_REASONING_CYBER,
    GROQ_PROMPT_CACHE_DISCOUNT,
)
from app.security.usage import (
    reserve_ai_budget,
    settle_ai_budget,
    estimate_chat_cost,
    calculate_chat_cost,
    estimate_input_tokens,
    extract_usage_metrics,
)
from app.ai.control import get_provider_override
from app.models.ai_routing_event import AIRoutingEvent

_VALID_GROQ_REASONING = {"low", "medium", "high"}


def _validated_reasoning_effort(value: str, default: str) -> str:
    candidate = (value or "").strip().lower()
    return candidate if candidate in _VALID_GROQ_REASONING else default


GROQ_REASONING_DEFAULT = _validated_reasoning_effort(GROQ_REASONING_DEFAULT, "low")
GROQ_REASONING_DEEP = _validated_reasoning_effort(GROQ_REASONING_DEEP, "medium")
GROQ_REASONING_CYBER = _validated_reasoning_effort(GROQ_REASONING_CYBER, "high")
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
    prompt_tokens: int | None = None
    cached_prompt_tokens: int | None = None
    completion_tokens: int | None = None
    reasoning_tokens: int | None = None
    estimated_cost_usd: float | None = None
    cache_savings_usd: float | None = None
    reasoning_effort: str | None = None


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


def _call_cloudflare(messages: list[dict], max_output_tokens: int) -> tuple[str, float | None, dict]:
    if not CLOUDFLARE_ACCOUNT_ID or not CLOUDFLARE_API_TOKEN:
        raise CloudflareProviderError("Cloudflare credentials are not configured")

    endpoint = (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{CLOUDFLARE_ACCOUNT_ID}/ai/v1/chat/completions"
    )
    # Gemma 4 accepts chat_template_kwargs on Cloudflare's OpenAI-compatible
    # endpoint. Disable its optional thinking mode for ordinary chat; requests
    # classified as complex/research are routed directly to Groq GPT-OSS.
    # Do not inject Qwen-specific /no_think text or unsupported top_k params.
    payload = {
        "model": CLOUDFLARE_MODEL,
        "messages": [dict(item) for item in messages],
        "stream": False,
        "max_completion_tokens": max_output_tokens,
        "temperature": 0.7,
        "top_p": 0.8,
        "chat_template_kwargs": {"enable_thinking": False},
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
    return content, neurons, extract_usage_metrics(usage)


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


def _select_groq_reasoning_effort(messages: list[dict], routing_reason: str) -> str:
    """Choose GPT-OSS reasoning effort by selected mode and request route."""
    system_text = ""
    if messages and isinstance(messages[0], dict):
        system_text = str(messages[0].get("content") or "")
    if re.search(r"(?m)^MODE: Cybersecurity Agent\b", system_text):
        return GROQ_REASONING_CYBER
    if routing_reason in {"research_synthesis", "high_complexity"}:
        return GROQ_REASONING_DEEP
    return GROQ_REASONING_DEFAULT


def _call_groq(
    messages: list[dict], account, db, groq_client,
    *, is_creator: bool, max_output_tokens: int, routing_reason: str,
    fallback_used: bool,
) -> RoutedCompletion:
    reservation = reserve_ai_budget(
        account, db, estimate_chat_cost(messages, max_output_tokens, vision=False)
    )
    reasoning_effort = _select_groq_reasoning_effort(messages, routing_reason)
    try:
        kwargs = {
            "model": GROQ_MODEL,
            "messages": messages,
            "temperature": 0.7,
            "top_p": 0.95,
            # Provider-side reasoning is explicitly controlled for Creator and
            # standard accounts. This does not impose a Creator usage quota.
        }
        if GROQ_MODEL.lower() in {"openai/gpt-oss-120b", "openai/gpt-oss-20b"}:
            kwargs["extra_body"] = {"reasoning_effort": reasoning_effort}
        else:
            reasoning_effort = None
        if not is_creator:
            kwargs["max_tokens"] = max_output_tokens
        response = groq_client.chat.completions.create(**kwargs)
        message = response.choices[0].message
        response_text = getattr(message, "content", None) or ""
        if not response_text.strip():
            raise RuntimeError("Groq returned no final answer")

        usage = getattr(response, "usage", None)
        usage_metrics = (
            extract_usage_metrics(usage) if usage is not None else {
                "prompt_tokens": None,
                "cached_prompt_tokens": None,
                "completion_tokens": None,
                "reasoning_tokens": None,
            }
        )
        # Groq automatic cache discount is supported for GPT-OSS models. Apply
        # it only to cached tokens explicitly reported in the response usage.
        cache_supported = GROQ_MODEL.lower() in {"openai/gpt-oss-120b", "openai/gpt-oss-20b"}
        cost_args = {
            "vision": False,
            "fallback_input_tokens": estimate_input_tokens(messages),
            "fallback_output_tokens": max(1, len(response_text) // 3),
        }
        actual_cost = calculate_chat_cost(
            usage,
            **cost_args,
            cached_input_discount=GROQ_PROMPT_CACHE_DISCOUNT if cache_supported else 0.0,
        )
        uncached_cost = calculate_chat_cost(usage, **cost_args, cached_input_discount=0.0)
        cache_savings = max(0.0, uncached_cost - actual_cost) if cache_supported else 0.0
        settle_ai_budget(db, reservation, actual_cost)
        reservation = None
        return RoutedCompletion(
            content=response_text,
            provider="groq",
            model=GROQ_MODEL,
            routing_reason=routing_reason,
            fallback_used=fallback_used,
            prompt_tokens=usage_metrics["prompt_tokens"],
            cached_prompt_tokens=usage_metrics["cached_prompt_tokens"],
            completion_tokens=usage_metrics["completion_tokens"],
            reasoning_tokens=usage_metrics["reasoning_tokens"],
            estimated_cost_usd=actual_cost,
            cache_savings_usd=cache_savings,
            reasoning_effort=reasoning_effort,
        )
    except Exception:
        if reservation is not None:
            settle_ai_budget(db, reservation, 0.0)
        raise


def _generate_text_auto(
    messages: list[dict], account, db, groq_client,
    *, is_creator: bool, is_research: bool = False,
) -> RoutedCompletion:
    """Route one text completion; provider quota is global, app limits are per user."""
    max_output_tokens = (
        CLOUDFLARE_CREATOR_MAX_OUTPUT_TOKENS
        if is_creator else CLOUDFLARE_FREE_MAX_OUTPUT_TOKENS
    )

    # Cybersecurity mode is Creator-only and uses GPT-OSS with an explicit
    # high reasoning setting instead of the lightweight Gemma primary route.
    system_text = str(messages[0].get("content") or "") if messages else ""
    if re.search(r"(?m)^MODE: Cybersecurity Agent\b", system_text):
        return _call_groq(
            messages, account, db, groq_client,
            is_creator=is_creator, max_output_tokens=max_output_tokens,
            routing_reason="cybersecurity_mode", fallback_used=False,
        )

    # Research synthesis and explicitly complex work go to GPT-OSS directly.
    # They do not consume the shared Cloudflare daily Neuron allocation.
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
        logger.info("Gemma skipped (%s); routing to GPT-OSS", reason)
        return _call_groq(
            messages, account, db, groq_client,
            is_creator=is_creator, max_output_tokens=max_output_tokens,
            routing_reason=reason, fallback_used=True,
        )

    try:
        cloudflare_result = _call_cloudflare(messages, max_output_tokens)
        # Backward-compatible with provider stubs used by older tests.
        if len(cloudflare_result) == 2:
            response_text, actual_neurons = cloudflare_result
            usage_metrics = {}
        else:
            response_text, actual_neurons, usage_metrics = cloudflare_result
        usage_metrics = usage_metrics or {}
        settle_cloudflare_neurons(db, neuron_reservation, actual_neurons)
        neuron_reservation = None
        return RoutedCompletion(
            content=response_text,
            provider="cloudflare",
            model=CLOUDFLARE_MODEL,
            routing_reason="primary_gemma",
            fallback_used=False,
            neurons_used=actual_neurons,
            prompt_tokens=usage_metrics.get("prompt_tokens"),
            cached_prompt_tokens=usage_metrics.get("cached_prompt_tokens"),
            completion_tokens=usage_metrics.get("completion_tokens"),
            reasoning_tokens=usage_metrics.get("reasoning_tokens"),
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
        logger.warning("Cloudflare Gemma failed; falling back to Groq: %s", type(exc).__name__)
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
        logger.exception("Unexpected Cloudflare routing failure; falling back to Groq")
        return _call_groq(
            messages, account, db, groq_client,
            is_creator=is_creator, max_output_tokens=max_output_tokens,
            routing_reason="cloudflare_provider_unavailable", fallback_used=True,
        )

def _record_routing_event(db, account, result: RoutedCompletion | None, latency_ms: int, error: Exception | None = None) -> None:
    """Persist routing telemetry without storing prompts or account identifiers."""
    try:
        event = AIRoutingEvent(
            provider=result.provider if result else "unknown",
            model=result.model if result else "",
            routing_reason=result.routing_reason if result else "routing_error",
            fallback_used=bool(result.fallback_used) if result else False,
            success=result is not None,
            account_type="creator" if getattr(account, "is_creator", False) and getattr(account, "username", "").lower() == "father" else "standard",
            latency_ms=max(0, int(latency_ms)),
            neurons_used=result.neurons_used if result else None,
            prompt_tokens=result.prompt_tokens if result else None,
            cached_prompt_tokens=result.cached_prompt_tokens if result else None,
            completion_tokens=result.completion_tokens if result else None,
            reasoning_tokens=result.reasoning_tokens if result else None,
            estimated_cost_usd=result.estimated_cost_usd if result else None,
            cache_savings_usd=result.cache_savings_usd if result else None,
            reasoning_effort=result.reasoning_effort if result else None,
            error_type=type(error).__name__[:120] if error else None,
        )
        db.add(event)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not persist AI routing telemetry")


def generate_text(
    messages: list[dict], account, db, groq_client,
    *, is_creator: bool, is_research: bool = False,
) -> RoutedCompletion:
    """Apply temporary Creator override, route inference, and record metadata."""
    started = perf_counter()
    result = None
    try:
        override = get_provider_override(db)
        if override.get("active") and override.get("mode") == "groq":
            max_output_tokens = (
                CLOUDFLARE_CREATOR_MAX_OUTPUT_TOKENS
                if is_creator else CLOUDFLARE_FREE_MAX_OUTPUT_TOKENS
            )
            result = _call_groq(
                messages, account, db, groq_client,
                is_creator=is_creator, max_output_tokens=max_output_tokens,
                routing_reason="manual_override_groq", fallback_used=False,
            )
        else:
            result = _generate_text_auto(
                messages, account, db, groq_client,
                is_creator=is_creator, is_research=is_research,
            )
        return result
    except Exception as exc:
        _record_routing_event(db, account, None, (perf_counter() - started) * 1000, exc)
        raise
    finally:
        if result is not None:
            _record_routing_event(db, account, result, (perf_counter() - started) * 1000)

