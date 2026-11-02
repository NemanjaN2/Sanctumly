"""Focused tests for Sanctumly's shared-provider model router."""
import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.provider_usage import ProviderDailyUsage
from app.models.usage import DailyUsage
from app.models.rate_limit import Settings
from app.models.ai_routing_event import AIRoutingEvent
from app.ai import router as ai_router
from app.ai.provider_state import (
    cloudflare_provider_snapshot,
    mark_cloudflare_exhausted,
    reserve_cloudflare_neurons,
    settle_cloudflare_neurons,
)


class FakeGroq:
    def __init__(self):
        self.last_kwargs = None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="GPT-OSS response"))],
            usage=SimpleNamespace(prompt_tokens=20, completion_tokens=10),
        )


class AdaptiveRouterTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            engine,
            tables=[ProviderDailyUsage.__table__, DailyUsage.__table__, Settings.__table__, AIRoutingEvent.__table__],
        )
        self.db = sessionmaker(bind=engine)()
        self.groq = FakeGroq()
        self.creator = SimpleNamespace(username="father", is_creator=True)
        self.regular = SimpleNamespace(username="alice", is_creator=False)
        self._original = {
            "account_id": ai_router.CLOUDFLARE_ACCOUNT_ID,
            "token": ai_router.CLOUDFLARE_API_TOKEN,
            "call": ai_router._call_cloudflare,
        }

    def tearDown(self):
        ai_router.CLOUDFLARE_ACCOUNT_ID = self._original["account_id"]
        ai_router.CLOUDFLARE_API_TOKEN = self._original["token"]
        ai_router._call_cloudflare = self._original["call"]
        self.db.close()

    def test_simple_requests_use_qwen_without_exposing_reasoning(self):
        ai_router.CLOUDFLARE_ACCOUNT_ID = "test-account"
        ai_router.CLOUDFLARE_API_TOKEN = "test-token"
        ai_router._call_cloudflare = lambda messages, max_tokens: ("Qwen answer", 12.5)

        result = ai_router.generate_text(
            [{"role": "user", "content": "Say hello."}],
            self.creator, self.db, self.groq, is_creator=True,
        )
        self.assertEqual(result.provider, "cloudflare")
        self.assertEqual(result.content, "Qwen answer")
        self.assertFalse(result.fallback_used)
        self.assertEqual(cloudflare_provider_snapshot(self.db)["used_neurons"], 12.5)
        event = self.db.query(AIRoutingEvent).one()
        self.assertEqual(event.provider, "cloudflare")
        self.assertEqual(event.routing_reason, "primary_qwen")
        self.assertEqual(event.account_type, "creator")

    def test_shared_qwen_exhaustion_falls_back_for_all_accounts(self):
        ai_router.CLOUDFLARE_ACCOUNT_ID = "test-account"
        ai_router.CLOUDFLARE_API_TOKEN = "test-token"
        ai_router._call_cloudflare = lambda messages, max_tokens: ("Qwen answer", 20.0)

        first = ai_router.generate_text(
            [{"role": "user", "content": "Hello."}],
            self.creator, self.db, self.groq, is_creator=True,
        )
        self.assertEqual(first.provider, "cloudflare")

        mark_cloudflare_exhausted(self.db, "simulated account-wide quota exhaustion")
        second = ai_router.generate_text(
            [{"role": "user", "content": "Hello from a regular account."}],
            self.regular, self.db, self.groq, is_creator=False,
        )
        self.assertEqual(second.provider, "groq")
        self.assertTrue(second.fallback_used)
        self.assertEqual(second.routing_reason, "cloudflare_quota_exhausted")

    def test_complexity_and_research_routes_skip_qwen(self):
        ai_router.CLOUDFLARE_ACCOUNT_ID = "test-account"
        ai_router.CLOUDFLARE_API_TOKEN = "test-token"
        def forbidden_qwen(*args, **kwargs):
            raise AssertionError("Qwen should not be called for direct Groq routes")
        ai_router._call_cloudflare = forbidden_qwen

        complex_result = ai_router.generate_text(
            [{"role": "user", "content": "Debug this Python traceback and implement a fix."}],
            self.creator, self.db, self.groq, is_creator=True,
        )
        research_result = ai_router.generate_text(
            [{"role": "user", "content": "Find current documentation."}],
            self.creator, self.db, self.groq, is_creator=True, is_research=True,
        )
        self.assertEqual(complex_result.routing_reason, "high_complexity")
        self.assertEqual(research_result.routing_reason, "research_synthesis")

    def test_incomplete_qwen_answer_records_neurons_before_groq_fallback(self):
        ai_router.CLOUDFLARE_ACCOUNT_ID = "test-account"
        ai_router.CLOUDFLARE_API_TOKEN = "test-token"

        def incomplete_qwen(messages, max_tokens):
            raise ai_router.CloudflareProviderError(
                "No final answer", neurons_used=11.75
            )

        ai_router._call_cloudflare = incomplete_qwen
        result = ai_router.generate_text(
            [{"role": "user", "content": "Say hello."}],
            self.creator, self.db, self.groq, is_creator=True,
        )
        self.assertEqual(result.provider, "groq")
        self.assertTrue(result.fallback_used)
        self.assertEqual(
            cloudflare_provider_snapshot(self.db)["used_neurons"], 11.75
        )
        self.assertEqual(
            cloudflare_provider_snapshot(self.db)["reserved_neurons"], 0.0
        )

    def test_cybersecurity_mode_routes_to_groq_with_high_effort(self):
        ai_router.CLOUDFLARE_ACCOUNT_ID = "test-account"
        ai_router.CLOUDFLARE_API_TOKEN = "test-token"
        def forbidden_qwen(*args, **kwargs):
            raise AssertionError("Cybersecurity mode should use GPT-OSS reasoning")
        ai_router._call_cloudflare = forbidden_qwen

        result = ai_router.generate_text(
            [
                {"role": "system", "content": "You are Sanctumly.\n\nMODE: Cybersecurity Agent"},
                {"role": "user", "content": "Explain this security finding."},
            ],
            self.creator, self.db, self.groq, is_creator=True,
        )
        self.assertEqual(result.provider, "groq")
        self.assertEqual(result.routing_reason, "cybersecurity_mode")
        self.assertEqual(result.reasoning_effort, "high")
        self.assertEqual(self.groq.last_kwargs["extra_body"]["reasoning_effort"], "high")
        self.assertNotIn("max_tokens", self.groq.last_kwargs)  # Creator output remains uncapped here.

    def test_groq_cache_and_reasoning_usage_are_persisted_for_control_center(self):
        class CachedGroq:
            def __init__(self):
                self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
            @staticmethod
            def create(**kwargs):
                return SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content="Cached GPT-OSS response"))],
                    usage=SimpleNamespace(
                        prompt_tokens=1000,
                        completion_tokens=100,
                        prompt_tokens_details=SimpleNamespace(cached_tokens=800),
                        completion_tokens_details=SimpleNamespace(reasoning_tokens=35),
                    ),
                )

        result = ai_router.generate_text(
            [
                {"role": "system", "content": "MODE: General assistant"},
                {"role": "user", "content": "Summarize this."},
            ],
            self.creator, self.db, CachedGroq(), is_creator=True, is_research=True,
        )
        self.assertEqual(result.prompt_tokens, 1000)
        self.assertEqual(result.cached_prompt_tokens, 800)
        self.assertEqual(result.completion_tokens, 100)
        self.assertEqual(result.reasoning_tokens, 35)
        self.assertEqual(result.reasoning_effort, "medium")
        self.assertGreater(result.cache_savings_usd, 0)
        event = self.db.query(AIRoutingEvent).one()
        self.assertEqual(event.cached_prompt_tokens, 800)
        self.assertEqual(event.reasoning_effort, "medium")
        self.assertGreater(event.cache_savings_usd, 0)

    def test_reasoning_effort_is_set_for_creator_and_regular_requests(self):
        ordinary = [{"role": "system", "content": "MODE: General assistant"}]
        deep = [{"role": "system", "content": "MODE: General assistant"}]
        cyber = [{"role": "system", "content": "MODE: Cybersecurity Agent"}]
        self.assertEqual(ai_router._select_groq_reasoning_effort(ordinary, "primary_fallback"), "low")
        self.assertEqual(ai_router._select_groq_reasoning_effort(deep, "research_synthesis"), "medium")
        self.assertEqual(ai_router._select_groq_reasoning_effort(cyber, "primary_fallback"), "high")

    def test_reasoning_is_not_used_as_final_answer(self):
        with self.assertRaises(ai_router.CloudflareProviderError) as caught:
            ai_router._content_from_cloudflare({
                "usage": {"neurons": 13.25},
                "choices": [{
                    "message": {
                        "content": None,
                        "reasoning": "not user-facing",
                        "reasoning_content": "not user-facing either",
                    },
                    "finish_reason": "length",
                }]
            })
        self.assertEqual(caught.exception.neurons_used, 13.25)

        with self.assertRaises(ai_router.CloudflareProviderError) as truncated:
            ai_router._content_from_cloudflare({
                "usage": {"neurons": 7.5},
                "choices": [{
                    "message": {"content": "An incomplete answer"},
                    "finish_reason": "length",
                }]
            })
        self.assertEqual(truncated.exception.neurons_used, 7.5)

    def test_manual_groq_override_is_expiring_and_records_event(self):
        from app.ai.control import set_provider_override

        ai_router.CLOUDFLARE_ACCOUNT_ID = "test-account"
        ai_router.CLOUDFLARE_API_TOKEN = "test-token"
        ai_router._call_cloudflare = lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("manual Groq override must not call Qwen")
        )
        set_provider_override(self.db, "groq", 60, updated_by="father")

        result = ai_router.generate_text(
            [{"role": "user", "content": "Say hello."}],
            self.creator, self.db, self.groq, is_creator=True,
        )
        self.assertEqual(result.provider, "groq")
        self.assertEqual(result.routing_reason, "manual_override_groq")
        self.assertFalse(result.fallback_used)
        event = self.db.query(AIRoutingEvent).one()
        self.assertEqual(event.provider, "groq")
        self.assertEqual(event.routing_reason, "manual_override_groq")

    def test_auto_override_restores_adaptive_routing(self):
        from app.ai.control import set_provider_override

        ai_router.CLOUDFLARE_ACCOUNT_ID = "test-account"
        ai_router.CLOUDFLARE_API_TOKEN = "test-token"
        ai_router._call_cloudflare = lambda messages, max_tokens: ("Qwen answer", 3.0)
        set_provider_override(self.db, "groq", 60, updated_by="father")
        set_provider_override(self.db, "auto", 60, updated_by="father")

        result = ai_router.generate_text(
            [{"role": "user", "content": "Say hello."}],
            self.creator, self.db, self.groq, is_creator=True,
        )
        self.assertEqual(result.provider, "cloudflare")
        self.assertEqual(result.routing_reason, "primary_qwen")


if __name__ == "__main__":
    unittest.main()
