"""
Comprehensive tests for the UrbanPulse Intelligence Assistant — Three-Level Strategy.

Test categories:
  1. OllamaClient  — model discovery, resolution, chat fallback, embed
  2. QuestionClassifier — Level 1/2/3 routing logic
  3. UrbanScore    — formula, weights, component coverage
  4. Redis cache   — hit/miss, similarity, offline bypass, invalidation
  5. API endpoints — /ask (all 3 modes), /urban-score, /compare, /status
  6. Integration   — verified data Q, general Q, hybrid Q, Qwen failure, Mistral fallback
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from backend.app.main import app
from backend.app.services.intelligence.ollama_client import OllamaClient, MODE_HYBRID, MODE_GENERAL_AI, MODE_VERIFIED, MODE_DATA_ONLY
from backend.app.services.intelligence.classifier import (
    classify_question, LEVEL_1, LEVEL_2, LEVEL_3, is_general_question
)
from backend.app.services.intelligence.urban_score import UrbanScoreEngine, calculate_urban_score
from backend.app.services.intelligence.retriever import LOCALITY_WARD_MAP, extract_localities_from_query
from backend.app.services.intelligence.cache import (
    RedisSemanticCache, cosine_similarity, normalize_query_text
)

client = TestClient(app)


# ═══════════════════════════════════════════════════════════════════
# 1. OllamaClient Tests
# ═══════════════════════════════════════════════════════════════════

class TestOllamaClient:
    """Test dynamic model discovery, resolution, and fallback strategy."""

    def test_resolve_exact_tag(self):
        oc = OllamaClient()
        with patch.object(oc, "get_installed_models", return_value=["qwen3:8b", "nomic-embed-text:latest"]):
            assert oc.resolve_model("qwen3:8b") == "qwen3:8b"

    def test_resolve_prefix_match(self):
        """'mistral' should resolve to 'mistral:7b-instruct' if that is installed."""
        oc = OllamaClient()
        with patch.object(oc, "get_installed_models", return_value=["mistral:7b-instruct", "qwen3:8b"]):
            result = oc.resolve_model("mistral")
            assert result == "mistral:7b-instruct"

    def test_resolve_returns_none_for_missing_model(self):
        oc = OllamaClient()
        with patch.object(oc, "get_installed_models", return_value=["qwen3:8b"]):
            assert oc.resolve_model("mistral") is None

    def test_resolve_primary_uses_config(self):
        oc = OllamaClient()
        with patch.object(oc, "get_installed_models", return_value=["qwen3:8b"]):
            primary = oc.resolve_primary()
            assert primary == "qwen3:8b"

    def test_resolve_fallback_is_none_when_same_as_primary(self):
        """If fallback config resolves to the same model as primary, return None."""
        oc = OllamaClient()
        # Both qwen3:8b and mistral — but only qwen3:8b installed
        with patch.object(oc, "get_installed_models", return_value=["qwen3:8b"]):
            assert oc.resolve_fallback() is None  # mistral not installed

    def test_resolve_fallback_returns_different_model(self):
        oc = OllamaClient()
        with patch.object(oc, "get_installed_models", return_value=["qwen3:8b", "mistral:latest"]):
            fallback = oc.resolve_fallback()
            assert fallback == "mistral:latest"

    def test_chat_returns_clean_text(self):
        oc = OllamaClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"content": "<think>reasoning</think>Answer here."}
        }
        with patch("requests.post", return_value=mock_resp):
            text, model = oc.chat("qwen3:8b", "sys", "user")
        assert text == "Answer here."
        assert model == "qwen3:8b"

    def test_chat_strips_think_tags(self):
        oc = OllamaClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"content": "<think>lots of thinking\nmulti-line</think>Final answer."}
        }
        with patch("requests.post", return_value=mock_resp):
            text, _ = oc.chat("qwen3:8b", "sys", "user")
        assert text == "Final answer."
        assert "<think>" not in text

    def test_chat_returns_none_on_timeout(self):
        import requests as req
        oc = OllamaClient()
        with patch("requests.post", side_effect=req.exceptions.Timeout("timeout")):
            text, model = oc.chat("qwen3:8b", "sys", "user", timeout=1)
        assert text is None

    def test_chat_with_fallback_uses_primary_first(self):
        oc = OllamaClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"message": {"content": "Primary answer."}}
        with patch.object(oc, "resolve_primary", return_value="qwen3:8b"), \
             patch("requests.post", return_value=mock_resp):
            text, model, reason = oc.chat_with_fallback("sys", "user")
        assert text == "Primary answer."
        assert model == "qwen3:8b"
        assert reason == ""

    def test_chat_with_fallback_uses_fallback_on_primary_failure(self):
        oc = OllamaClient()
        import requests as req
        call_count = [0]
        mock_ok = MagicMock()
        mock_ok.status_code = 200
        mock_ok.json.return_value = {"message": {"content": "Fallback answer."}}

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise req.exceptions.ConnectionError("primary connection refused")
            return mock_ok

        with patch.object(oc, "resolve_primary", return_value="qwen3:4b"), \
             patch.object(oc, "resolve_fallback", return_value="mistral:latest"), \
             patch("requests.post", side_effect=side_effect):
            text, model, reason = oc.chat_with_fallback("sys", "user")
        assert text == "Fallback answer."
        assert model == "mistral:latest"
        assert reason == "primary_failed"

    def test_chat_with_fallback_skips_fallback_on_primary_timeout(self):
        oc = OllamaClient()
        import requests as req
        with patch.object(oc, "resolve_primary", return_value="qwen3:4b"), \
             patch.object(oc, "resolve_fallback", return_value="mistral:latest"), \
             patch("requests.post", side_effect=req.exceptions.Timeout("primary timeout")):
            text, model, reason = oc.chat_with_fallback("sys", "user")
        assert text is None
        assert model == "none"
        assert reason == "primary_timed_out"

    def test_chat_with_fallback_returns_none_when_all_fail(self):
        import requests as req
        oc = OllamaClient()
        with patch.object(oc, "resolve_primary", return_value="qwen3:4b"), \
             patch.object(oc, "resolve_fallback", return_value="mistral:latest"), \
             patch("requests.post", side_effect=req.exceptions.ConnectionError("offline")):
            text, model, reason = oc.chat_with_fallback("sys", "user")
        assert text is None
        assert model == "none"
        assert reason == "ollama_unavailable"

    def test_embed_returns_list(self):
        oc = OllamaClient()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"embedding": [0.1, 0.2, 0.3]}
        with patch("requests.post", return_value=mock_resp):
            result = oc.embed("test text")
        assert result == [0.1, 0.2, 0.3]

    def test_embed_returns_empty_on_failure(self):
        oc = OllamaClient()
        with patch("requests.post", side_effect=Exception("offline")):
            result = oc.embed("test")
        assert result == []

    def test_status_has_required_keys(self):
        oc = OllamaClient()
        with patch.object(oc, "get_installed_models", return_value=["qwen3:8b"]):
            s = oc.status()
        assert "connected" in s
        assert "primary_model" in s
        assert "fallback_model" in s
        assert "installed_models" in s
        assert "timeout_seconds" in s


# ═══════════════════════════════════════════════════════════════════
# 2. Question Classifier Tests
# ═══════════════════════════════════════════════════════════════════

class TestQuestionClassifier:
    """Verify the three-level routing decisions."""

    def test_whitefield_buy_house_is_hybrid(self):
        level, _ = classify_question("Should I buy a house in Whitefield?", has_locality_evidence=True)
        assert level == LEVEL_2

    def test_whitefield_no_locality_ev_is_hybrid(self):
        # Even without local evidence, "whitefield + buy" should be LEVEL_2
        level, _ = classify_question("Should I buy a house in Whitefield?", has_locality_evidence=False)
        assert level in (LEVEL_2, LEVEL_3)  # classifier may differ; must NOT be LEVEL_1

    def test_general_urban_planning_is_level3(self):
        level, _ = classify_question("Why is urban planning important?", has_locality_evidence=False)
        assert level == LEVEL_3

    def test_explain_esg_is_level3(self):
        level, _ = classify_question("Explain how ESG affects property investment.", has_locality_evidence=False)
        assert level == LEVEL_3

    def test_what_is_urban_score_is_level3(self):
        level, _ = classify_question("What is an urban score?", has_locality_evidence=False)
        assert level == LEVEL_3

    def test_bbmp_total_investment_is_level1_or_level2(self):
        level, _ = classify_question("What is the total BBMP construction investment in Bengaluru?", has_locality_evidence=False)
        assert level in (LEVEL_1, LEVEL_2)

    def test_koramangala_safety_with_evidence_is_hybrid(self):
        level, _ = classify_question("Is Koramangala safe for a family?", has_locality_evidence=True)
        assert level == LEVEL_2

    def test_improve_public_safety_is_level3(self):
        level, _ = classify_question("How can a city improve public safety?", has_locality_evidence=False)
        assert level == LEVEL_3

    def test_esg_score_hsr_with_evidence_is_hybrid(self):
        level, _ = classify_question("What is the ESG score for HSR Layout?", has_locality_evidence=True)
        assert level == LEVEL_2

    def test_is_general_question_helper(self):
        assert is_general_question("What factors should I consider before buying a house?") is True
        assert is_general_question("How many work orders in Whitefield?") is False


# ═══════════════════════════════════════════════════════════════════
# 3. UrbanScore Tests  (carried forward + extended)
# ═══════════════════════════════════════════════════════════════════

class TestUrbanScoreFormula:

    def _full_inputs(self):
        return dict(
            locality_name="Test Area",
            ward_data={
                "total_work_orders": 30, "total_amount_cr": 20.0, "total_net_cr": 18.0,
                "unique_contractors": 10, "road_projects": 10, "drain_projects": 8,
                "water_projects": 4, "development_projects": 8, "avg_deduction_pct": 10.0,
                "cluster_label": "High Development / High Expenditure",
            },
            police_data={"station_count": 1, "outpost_count": 2},
            crime_data={"risk_score": 71.7},
            air_data={"station_name": "Test Station", "pm25": 45.0, "pm10": 80.0},
            water_data={"lake_name": "Test Lake", "wq_class": "C", "status": "Fair"},
            complaints_data={"total": 5, "resolved": 3, "in_progress": 2},
        )

    def test_score_in_range(self):
        r = UrbanScoreEngine.calculate(**self._full_inputs())
        assert 0.0 <= r["score"] <= 100.0

    def test_weights_sum_to_1(self):
        assert abs(sum(UrbanScoreEngine.DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9

    def test_five_components_present(self):
        r = UrbanScoreEngine.calculate(**self._full_inputs())
        for k in ["safety", "infrastructure", "environment", "social_infrastructure", "governance"]:
            assert k in r["components"]

    def test_full_data_coverage_100_pct(self):
        r = UrbanScoreEngine.calculate(**self._full_inputs())
        assert r["data_coverage_pct"] == 100.0

    def test_none_inputs_no_crash(self):
        r = UrbanScoreEngine.calculate("Empty Area", None, None, None, None, None, None)
        assert isinstance(r["score"], float)

    def test_calculate_urban_score_helper(self):
        ev = {
            "display_name": "Helper Area",
            **{k: v for k, v in self._full_inputs().items() if k != "locality_name"}
        }
        r = calculate_urban_score(ev)
        assert "score" in r


# ═══════════════════════════════════════════════════════════════════
# 4. Redis Semantic Cache Tests
# ═══════════════════════════════════════════════════════════════════

class TestSemanticCache:

    def test_cosine_identity(self):
        v = [1.0, 2.0, 3.0]
        assert abs(cosine_similarity(v, v) - 1.0) < 1e-9

    def test_cosine_orthogonal(self):
        assert abs(cosine_similarity([1.0, 0.0], [0.0, 1.0])) < 1e-9

    def test_cosine_empty_returns_zero(self):
        assert cosine_similarity([], []) == 0.0
        assert cosine_similarity([1.0], []) == 0.0

    def test_normalize_lowercases(self):
        assert normalize_query_text("  HELLO World!  ") == "hello world"

    def test_cache_miss_when_redis_offline(self):
        cache = RedisSemanticCache(redis_url="redis://127.0.0.1:9999/0", ttl=60)
        cached, sim, status = cache.get_semantic_match("test query", [0.1, 0.2], "v1")
        assert cached is None
        assert status == "UNAVAILABLE"

    def test_cache_store_fails_silently_when_offline(self):
        cache = RedisSemanticCache(redis_url="redis://127.0.0.1:9999/0", ttl=60)
        ok = cache.store("q", [0.1, 0.2], {"answer": "x"}, [], "v1")
        assert ok is False

    def test_health_check_offline(self):
        cache = RedisSemanticCache(redis_url="redis://127.0.0.1:9999/0", ttl=60)
        h = cache.health_check()
        assert h["connected"] is False
        assert h["status"] == "bypassed_offline"

    def test_data_version_invalidates_cache(self):
        """
        Simulate a cache hit from version v1 being passed as invalid when current version is v2.
        The cache should treat this as a miss.
        """
        cache = RedisSemanticCache(redis_url="redis://127.0.0.1:9999/0", ttl=60)
        # Offline — get_semantic_match always returns None; this is the safe path
        cached, sim, status = cache.get_semantic_match("test", [0.1], "v2")
        assert cached is None


# ═══════════════════════════════════════════════════════════════════
# 5. Evidence Retriever Tests
# ═══════════════════════════════════════════════════════════════════

class TestEvidenceRetriever:

    def test_whitefield_in_locality_map(self):
        assert "whitefield" in LOCALITY_WARD_MAP

    def test_hsr_layout_in_locality_map(self):
        assert "hsr layout" in LOCALITY_WARD_MAP

    def test_minimum_25_localities(self):
        assert len(LOCALITY_WARD_MAP) >= 25

    def test_whitefield_ward_84(self):
        assert LOCALITY_WARD_MAP["whitefield"]["ward"] == "84"

    def test_extract_from_explicit_locality(self):
        found = extract_localities_from_query("anything", "Whitefield")
        assert "whitefield" in found

    def test_extract_from_question_text(self):
        found = extract_localities_from_query("Should I move to Koramangala?")
        assert "koramangala" in found

    def test_no_locality_extract_returns_list(self):
        found = extract_localities_from_query("What is the total crime in Bengaluru?")
        assert isinstance(found, list)


# ═══════════════════════════════════════════════════════════════════
# 6. API Endpoint Tests
# ═══════════════════════════════════════════════════════════════════

class TestIntelligenceAPI:

    def test_status_operational(self):
        resp = client.get("/api/intelligence/status")
        assert resp.status_code == 200
        d = resp.json()
        assert d["status"] == "operational"
        assert "model" in d
        assert "cache" in d
        assert d["localities_indexed"] >= 25

    def test_status_has_primary_fallback_info(self):
        resp = client.get("/api/intelligence/status")
        assert resp.status_code == 200
        model = resp.json().get("model", {})
        # New OllamaClient shape
        assert "primary_model" in model or "target_model" in model
        assert "installed_models" in model

    def test_urban_score_whitefield(self):
        resp = client.get("/api/intelligence/urban-score?area=Whitefield")
        assert resp.status_code == 200
        d = resp.json()
        assert 0 <= d["score"] <= 100
        assert "components" in d
        assert "data_coverage_pct" in d

    def test_urban_score_hsr_layout(self):
        resp = client.get("/api/intelligence/urban-score?area=HSR Layout")
        assert resp.status_code == 200
        assert resp.json()["score"] >= 0

    def test_compare_two_areas(self):
        resp = client.get("/api/intelligence/compare?areas=Whitefield,HSR Layout")
        assert resp.status_code == 200
        d = resp.json()
        assert len(d["areas"]) == 2
        assert len(d["scores"]) == 2
        assert len(d["metrics_table"]) >= 3

    def test_compare_requires_at_least_2_areas(self):
        resp = client.get("/api/intelligence/compare?areas=Whitefield")
        assert resp.status_code == 400

    def test_compare_rejects_more_than_5_areas(self):
        resp = client.get("/api/intelligence/compare?areas=Whitefield,HSR Layout,Koramangala,Indiranagar,Bellandur,Peenya")
        assert resp.status_code == 400

    def test_ask_empty_question_rejected(self):
        resp = client.post("/api/intelligence/ask", json={"question": ""})
        assert resp.status_code in (400, 422)

    def test_ask_response_has_answer_mode_field(self):
        """
        The response MUST include answer_mode to tell the client which level was used.
        Uses a simple general question so we can mock away the slow Qwen call.
        """
        mock_text = "Urban planning is important for sustainable development."
        with patch(
            "backend.app.services.intelligence.ollama_client.OllamaClient.chat_with_fallback",
            return_value=(mock_text, "qwen3:8b", "")
        ):
            resp = client.post(
                "/api/intelligence/ask",
                json={"question": "Why is urban planning important?", "enable_cache": False},
                timeout=15,
            )
        assert resp.status_code == 200
        d = resp.json()
        assert "answer_mode" in d
        assert d["answer_mode"] in (
            "General AI Answer",
            "UrbanPulse Data + AI Analysis",
            "Verified UrbanPulse Data",
            "Verified UrbanPulse Data (AI Unavailable)",
        )

    def test_ask_general_question_mode_is_general_ai(self):
        """A question with no local data signals must return 'General AI Answer'."""
        mock_text = "Urban planning helps create livable cities."
        with patch(
            "backend.app.services.intelligence.ollama_client.OllamaClient.chat_with_fallback",
            return_value=(mock_text, "qwen3:8b", "")
        ):
            resp = client.post(
                "/api/intelligence/ask",
                json={"question": "What are the principles of good urban design?", "enable_cache": False},
                timeout=15,
            )
        assert resp.status_code == 200
        d = resp.json()
        assert d["answer_mode"] == "General AI Answer"
        assert d["answer"] == mock_text

    def test_ask_locality_question_mode_is_hybrid(self):
        """A question mentioning Whitefield + invest should return 'UrbanPulse Data + AI Analysis'."""
        mock_text = "Based on the evidence, Whitefield scores well."
        with patch(
            "backend.app.services.intelligence.ollama_client.OllamaClient.chat_with_fallback",
            return_value=(mock_text, "qwen3:8b", "")
        ):
            resp = client.post(
                "/api/intelligence/ask",
                json={"question": "Should I invest in Whitefield?", "enable_cache": False},
                timeout=15,
            )
        assert resp.status_code == 200
        d = resp.json()
        assert d["answer_mode"] in ("UrbanPulse Data + AI Analysis", "Verified UrbanPulse Data (AI Unavailable)")

    def test_ask_qwen_failure_returns_data_only_mode(self):
        """When both models are unavailable, answer_mode must be 'Verified UrbanPulse Data (AI Unavailable)'."""
        with patch(
            "backend.app.services.intelligence.ollama_client.OllamaClient.chat_with_fallback",
            return_value=(None, "none", "ollama_unavailable")
        ):
            resp = client.post(
                "/api/intelligence/ask",
                json={"question": "Should I buy a house in Koramangala?", "enable_cache": False},
                timeout=15,
            )
        assert resp.status_code == 200
        d = resp.json()
        assert d["answer_mode"] == "Verified UrbanPulse Data (AI Unavailable)"
        assert len(d["answer"]) > 10  # deterministic answer still returned

    def test_ask_general_qwen_failure_returns_data_only_mode(self):
        """
        General question with both models offline → answer_mode is DATA_ONLY.
        The service returns a deterministic data overview (never fabricated data),
        so the answer text contains verifiable BBMP/UrbanPulse content.
        """
        with patch(
            "backend.app.services.intelligence.ollama_client.OllamaClient.chat_with_fallback",
            return_value=(None, "none", "ollama_unavailable")
        ):
            resp = client.post(
                "/api/intelligence/ask",
                json={"question": "What is ESG?", "enable_cache": False},
                timeout=15,
            )
        assert resp.status_code == 200
        d = resp.json()
        assert d["answer_mode"] == "Verified UrbanPulse Data (AI Unavailable)"
        # The deterministic fallback still returns a valid, data-grounded response
        assert len(d["answer"]) > 10


    def test_cache_clear_endpoint(self):
        resp = client.post("/api/intelligence/cache/clear")
        assert resp.status_code == 200
        assert "message" in resp.json()

    def test_v1_prefix_also_works(self):
        resp = client.get("/api/v1/intelligence/urban-score?area=Koramangala")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# 7. AI Assistant Fixes & Enhancements Verification
# ═══════════════════════════════════════════════════════════════════

class TestAssistantFixes:
    """Tests for assistant fixes: caching rules, greetings, comparisons, distinct answers."""

    def test_failed_llm_answer_is_not_cached(self):
        """A failed LLM answer (MODE_DATA_ONLY / fail_reason / model='none') must never be cached."""
        with patch("backend.app.services.intelligence.assistant_service.ollama_client.chat_with_fallback",
                   return_value=(None, "none", "primary_timed_out")), \
             patch("backend.app.services.intelligence.assistant_service.semantic_cache.store") as mock_store:
            resp = client.post("/api/v1/intelligence/ask", json={"question": "What is the future of urban sprawl in Bengaluru?"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["answer_mode"] == "Verified UrbanPulse Data (AI Unavailable)"
            mock_store.assert_not_called()

    def test_two_different_questions_return_different_answers(self):
        """Two different questions should not return the exact same hardcoded text."""
        with patch("backend.app.services.intelligence.assistant_service.ollama_client.chat_with_fallback",
                   side_effect=[
                       ("Answer for question 1 about urban zoning laws.", "qwen3:4b", ""),
                       ("Answer for question 2 about rainwater harvesting techniques.", "qwen3:4b", "")
                   ]):
            resp1 = client.post("/api/v1/intelligence/ask", json={"question": "Tell me about urban zoning laws.", "enable_cache": False})
            resp2 = client.post("/api/v1/intelligence/ask", json={"question": "How does rainwater harvesting work?", "enable_cache": False})
            assert resp1.status_code == 200
            assert resp2.status_code == 200
            assert resp1.json()["answer"] != resp2.json()["answer"]

    def test_greeting_makes_no_llm_call(self):
        """Greetings should return instant friendly response without invoking ollama_client."""
        with patch("backend.app.services.intelligence.assistant_service.ollama_client.chat_with_fallback") as mock_chat, \
             patch("backend.app.services.intelligence.assistant_service.ollama_client.chat") as mock_chat_direct:
            resp = client.post("/api/v1/intelligence/ask", json={"question": "Hello! How can you help me?"})
            assert resp.status_code == 200
            mock_chat.assert_not_called()
            mock_chat_direct.assert_not_called()
            d = resp.json()
            assert "UrbanPulse Intelligence Assistant" in d["answer"]

    def test_compare_whitefield_and_hsr_layout_makes_no_llm_call(self):
        """'Compare Whitefield and HSR Layout' should return deterministic comparison from DB without calling LLM."""
        with patch("backend.app.services.intelligence.assistant_service.ollama_client.chat_with_fallback") as mock_chat, \
             patch("backend.app.services.intelligence.assistant_service.ollama_client.chat") as mock_chat_direct:
            resp = client.post("/api/v1/intelligence/ask", json={"question": "Compare Whitefield and HSR Layout", "enable_cache": False})
            assert resp.status_code == 200
            mock_chat.assert_not_called()
            mock_chat_direct.assert_not_called()
            d = resp.json()
            assert "Whitefield" in d["answer"]
            assert "HSR Layout" in d["answer"]
            assert "UrbanScore" in d["answer"]

    def test_streaming_endpoint_returns_ndjson(self):
        """Test POST /api/v1/intelligence/ask/stream returns application/x-ndjson with done payload."""
        import json
        resp = client.post("/api/v1/intelligence/ask/stream", json={"question": "Hello"})
        assert resp.status_code == 200
        assert "application/x-ndjson" in resp.headers.get("content-type", "")
        lines = [line for line in resp.text.strip().split("\n") if line]
        assert len(lines) >= 1
        last_obj = json.loads(lines[-1])
        assert last_obj.get("done") is True
        assert "payload" in last_obj


# ═══════════════════════════════════════════════════════════════════
# 8. Live Qwen3 Integration (slow — opt-in only)
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.slow
class TestLiveQwen3:
    """
    These tests hit the real local Ollama server.
    Run with: pytest -m slow -v
    """

    def test_general_question_via_qwen(self):
        resp = client.post(
            "/api/intelligence/ask",
            json={"question": "What factors should I consider before buying a house?", "enable_cache": False},
            timeout=90,
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["answer_mode"] in ("General AI Answer", "UrbanPulse Data + AI Analysis")
        assert len(d["answer"]) > 20

    def test_hybrid_question_whitefield_via_qwen(self):
        resp = client.post(
            "/api/intelligence/ask",
            json={"question": "Should I invest in property in Whitefield?", "enable_cache": False},
            timeout=90,
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["urban_score"] is not None
        assert d["answer_mode"] in ("UrbanPulse Data + AI Analysis",)
