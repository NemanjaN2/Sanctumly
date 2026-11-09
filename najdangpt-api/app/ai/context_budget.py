"""Conservative character-based token budgeting for retrieved context/history.

No tokenizer dependency is required. The estimate deliberately matches the
backend's existing conservative estimate_input_tokens ratio (2.5 chars/token).
The budget is per request, not a user quota; Creator accounts retain unlimited
request access while avoiding unbounded historical-context growth.
"""
from __future__ import annotations

import math
from typing import Iterable

CHARS_PER_ESTIMATED_TOKEN = 2.5


def estimate_text_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / CHARS_PER_ESTIMATED_TOKEN))


def truncate_text_to_tokens(text: str, token_budget: int) -> str:
    """Keep the beginning of a source block within an estimated token budget."""
    if not text or token_budget <= 0:
        return ""
    marker = "\n[truncated]"
    max_chars = max(1, int(token_budget * CHARS_PER_ESTIMATED_TOKEN))
    if len(text) <= max_chars:
        return text
    content_limit = max(1, max_chars - len(marker))
    clipped = text[:content_limit]
    # Avoid cutting in the middle of a word where a nearby boundary exists.
    boundary = clipped.rfind(" ")
    if boundary >= int(content_limit * 0.8):
        clipped = clipped[:boundary]
    return clipped.rstrip() + marker


def fit_context_sections(
    sections: Iterable[tuple[str, str, int]], total_token_budget: int
) -> tuple[str, int, dict[str, int]]:
    """Fit named sections into one shared budget, including headings."""
    remaining = max(0, int(total_token_budget))
    output: list[str] = []
    usage: dict[str, int] = {}
    for heading, text, per_section_cap in sections:
        if not text or remaining <= 0:
            continue
        allowance = min(remaining, max(0, int(per_section_cap)))
        if allowance <= 0:
            continue

        prefix = f"\n\n{heading}:\n"
        prefix_tokens = estimate_text_tokens(prefix)
        content_allowance = allowance - prefix_tokens
        if content_allowance <= 0:
            continue
        fitted = truncate_text_to_tokens(text, content_allowance)
        rendered = prefix + fitted
        # Account for headings and truncation markers, which are part of the
        # actual prompt and therefore part of the budget too.
        while fitted and estimate_text_tokens(rendered) > allowance and content_allowance > 1:
            content_allowance -= max(1, estimate_text_tokens(rendered) - allowance)
            fitted = truncate_text_to_tokens(text, content_allowance)
            rendered = prefix + fitted
        section_tokens = estimate_text_tokens(rendered) if fitted else 0
        if fitted and section_tokens <= allowance:
            output.append(rendered)
            usage[heading] = section_tokens
            remaining = max(0, remaining - section_tokens)
    suffix = "".join(output)
    return suffix, sum(usage.values()), usage


def select_recent_history(
    newest_first_rows: list,
    *,
    token_budget: int,
    max_chars_per_message: int,
) -> tuple[list, list[dict], int, int]:
    """Select newest complete history messages first within a token budget.

    The database rows are expected newest-first. The return value preserves
    that order for legacy helper calls, and returns provider messages in
    chronological order. The newest message may be truncated if it alone is
    larger than the whole history budget; older messages are never partially
    retained after the budget is exhausted.
    """
    selected_newest_first = []
    remaining = max(0, int(token_budget))
    trimmed_count = 0

    for row in newest_first_rows:
        raw = row.content or ""
        content = raw
        if max_chars_per_message > 0 and len(content) > max_chars_per_message:
            content = content[:max_chars_per_message].rsplit(" ", 1)[0] + " [...]"
            trimmed_count += 1

        estimated = estimate_text_tokens(content)
        if estimated <= remaining:
            selected_newest_first.append((row, content))
            remaining -= estimated
            continue

        # If the latest item cannot fit, preserve a bounded prefix of that
        # latest item rather than returning no conversational context.
        if not selected_newest_first and remaining > 0:
            content = truncate_text_to_tokens(content, remaining)
            if content:
                selected_newest_first.append((row, content))
                trimmed_count += 1
        break

    provider_messages = [
        {
            "role": "user" if row.role == "user" else "assistant",
            "content": content,
        }
        for row, content in reversed(selected_newest_first)
    ]
    selected_rows = [row for row, _content in selected_newest_first]
    used_tokens = sum(estimate_text_tokens(item["content"]) for item in provider_messages)
    return selected_rows, provider_messages, used_tokens, trimmed_count
