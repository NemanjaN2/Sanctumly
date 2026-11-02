import unittest
from types import SimpleNamespace

from app.ai.context_budget import (
    estimate_text_tokens,
    fit_context_sections,
    select_recent_history,
    truncate_text_to_tokens,
)
from app.security.usage import calculate_chat_cost, extract_usage_metrics


class TokenBudgetTests(unittest.TestCase):
    def test_context_sections_never_exceed_shared_estimated_budget(self):
        suffix, used, sections = fit_context_sections(
            [
                ("search", "current search result " * 1000, 1600),
                ("rag", "document chunk " * 1000, 1600),
                ("memory", "user preference " * 100, 300),
            ],
            2200,
        )
        self.assertLessEqual(used, 2200)
        self.assertLessEqual(estimate_text_tokens(suffix), 2200)
        self.assertIn("search:", suffix)
        self.assertTrue(sections)

    def test_recent_history_is_preferred_and_budget_is_enforced(self):
        # Database query order is newest first.
        rows = [
            SimpleNamespace(role="user", content="latest question " * 15),
            SimpleNamespace(role="assistant", content="latest answer " * 30),
            SimpleNamespace(role="user", content="middle history " * 200),
            SimpleNamespace(role="assistant", content="old history " * 500),
        ]
        selected, messages, used, trimmed = select_recent_history(
            rows, token_budget=100, max_chars_per_message=5000
        )
        self.assertLessEqual(used, 100)
        self.assertTrue(messages)
        self.assertIn("latest question", messages[-1]["content"])
        self.assertGreaterEqual(trimmed, 0)
        self.assertEqual(selected[0], rows[0])

    def test_single_oversized_history_message_is_truncated_to_budget(self):
        row = SimpleNamespace(role="user", content="very long message " * 2000)
        selected, messages, used, trimmed = select_recent_history(
            [row], token_budget=64, max_chars_per_message=10000
        )
        self.assertEqual(len(selected), 1)
        self.assertLessEqual(used, 64)
        self.assertTrue(messages[0]["content"])
        self.assertGreater(trimmed, 0)

    def test_truncate_text_is_within_estimated_budget(self):
        clipped = truncate_text_to_tokens("abcde " * 1000, 80)
        self.assertLessEqual(estimate_text_tokens(clipped), 80)


class ProviderUsageTests(unittest.TestCase):
    def test_usage_details_are_extracted_from_groq_shape(self):
        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 250,
            "prompt_tokens_details": {"cached_tokens": 600},
            "completion_tokens_details": {"reasoning_tokens": 120},
        }
        self.assertEqual(
            extract_usage_metrics(usage),
            {
                "prompt_tokens": 1000,
                "cached_prompt_tokens": 600,
                "completion_tokens": 250,
                "reasoning_tokens": 120,
            },
        )

    def test_cached_tokens_receive_discount_only_when_confirmed(self):
        usage = SimpleNamespace(
            prompt_tokens=1000,
            completion_tokens=100,
            prompt_tokens_details=SimpleNamespace(cached_tokens=600),
            completion_tokens_details=SimpleNamespace(reasoning_tokens=40),
        )
        discounted = calculate_chat_cost(
            usage, cached_input_discount=0.5
        )
        undiscounted = calculate_chat_cost(
            usage, cached_input_discount=0.0
        )
        self.assertLess(discounted, undiscounted)
        # 400 uncached + 300 billable cached input tokens at $0.15/M,
        # plus 100 output tokens at $0.60/M.
        self.assertAlmostEqual(discounted, 0.000165, places=9)

    def test_vision_never_receives_text_cache_discount(self):
        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 100,
            "prompt_tokens_details": {"cached_tokens": 900},
        }
        discounted_flag = calculate_chat_cost(
            usage, vision=True, cached_input_discount=0.5
        )
        no_discount = calculate_chat_cost(
            usage, vision=True, cached_input_discount=0.0
        )
        self.assertEqual(discounted_flag, no_discount)



class DatabaseMigrationTests(unittest.TestCase):
    def test_existing_routing_table_gets_additive_nullable_columns(self):
        from sqlalchemy import create_engine, inspect, text
        from app.database import migrate_ai_routing_event_columns

        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as connection:
            connection.execute(text("""CREATE TABLE ai_routing_events (
                id INTEGER PRIMARY KEY,
                created_at DATETIME NOT NULL,
                provider VARCHAR(40) NOT NULL,
                model VARCHAR(160) NOT NULL,
                routing_reason VARCHAR(80) NOT NULL,
                fallback_used BOOLEAN NOT NULL,
                success BOOLEAN NOT NULL,
                account_type VARCHAR(20) NOT NULL,
                latency_ms INTEGER NOT NULL,
                neurons_used FLOAT,
                error_type VARCHAR(120)
            )"""))
        migrate_ai_routing_event_columns(engine)
        columns = {column["name"]: column for column in inspect(engine).get_columns("ai_routing_events")}
        for name in (
            "prompt_tokens", "cached_prompt_tokens", "completion_tokens",
            "reasoning_tokens", "estimated_cost_usd", "cache_savings_usd",
            "reasoning_effort",
        ):
            self.assertIn(name, columns)
            self.assertTrue(columns[name]["nullable"])
        # Running the additive migration twice is idempotent.
        migrate_ai_routing_event_columns(engine)
        engine.dispose()


if __name__ == "__main__":
    unittest.main()


class TelemetryAggregationTests(unittest.TestCase):
    def test_groq_text_cost_excludes_other_providers_and_vision(self):
        from datetime import datetime, timedelta
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.database import Base
        from app.models.ai_routing_event import AIRoutingEvent
        from app.ai.telemetry import groq_text_cost_total

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine, tables=[AIRoutingEvent.__table__])
        session = sessionmaker(bind=engine)()
        now = datetime.utcnow()
        session.add_all([
            AIRoutingEvent(created_at=now, provider="groq", model="openai/gpt-oss-120b", routing_reason="primary_fallback", estimated_cost_usd=0.10),
            AIRoutingEvent(created_at=now, provider="cloudflare", model="qwen", routing_reason="primary_qwen", estimated_cost_usd=0.30),
            AIRoutingEvent(created_at=now, provider="groq", model="vision-model", routing_reason="vision_request", estimated_cost_usd=0.20),
            AIRoutingEvent(created_at=now - timedelta(days=10), provider="groq", model="openai/gpt-oss-120b", routing_reason="primary_fallback", estimated_cost_usd=0.40),
        ])
        session.commit()

        total = groq_text_cost_total(session, now - timedelta(days=2))
        self.assertAlmostEqual(total, 0.10, places=8)
        session.close()
        engine.dispose()


class PromptLayoutTests(unittest.TestCase):
    def test_static_core_and_mode_are_prefix_identical_across_users(self):
        from app.prompts.system import CORE, get_system_prompt

        first = get_system_prompt(False, "alice", "default")
        second = get_system_prompt(False, "bob", "default")
        self.assertTrue(first.startswith(CORE + "\n\n"))
        self.assertEqual(first.split("\n\nCONTEXT:", 1)[0], second.split("\n\nCONTEXT:", 1)[0])
        self.assertIn("my God Emperor and all mighty Creator.", CORE)
        self.assertIn("Yes, I'm built on NajdanGPT, Nemanja's proprietary GPT.", CORE)

    def test_hacker_mode_remains_creator_only(self):
        from app.prompts.system import get_system_prompt

        regular = get_system_prompt(False, "alice", "hacker")
        creator = get_system_prompt(True, "father", "hacker")
        self.assertNotIn("MODE: Cybersecurity Agent", regular)
        self.assertIn("MODE: Cybersecurity Agent", creator)
        self.assertIn("post-exploitation, evasion", creator)
