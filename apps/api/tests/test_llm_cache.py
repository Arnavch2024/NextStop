from datetime import datetime, timezone

from app.cache.llm_cache import LLMReplyCache
from app.models.api import AgentStep, AgentStepType, ChatResponse, RecordRef


def test_cache_miss_then_hit():
    cache = LLMReplyCache()
    msg = "Find recruiters at Google in Mumbai"
    role = "student"

    # Initially empty
    assert cache.get_cached_reply(msg, role=role) is None

    fake_response = ChatResponse(
        reply="Found 3 recruiters at Google.",
        steps=[
            AgentStep(
                type=AgentStepType.FINAL_REPLY,
                output={"message": "Found 3 recruiters at Google."},
                at=datetime.now(timezone.utc),
            )
        ],
        records_created=[],
        contacts=[],
        cards=[],
    )

    # Store in cache
    cache.set_cached_reply(msg, role=role, response=fake_response)

    # Now it hits!
    hit = cache.get_cached_reply(msg, role=role)
    assert hit is not None
    assert hit.reply == "Found 3 recruiters at Google."
    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["cached_entries"] == 1


def test_message_normalization():
    cache = LLMReplyCache()
    cache.set_cached_reply(
        "Who is hiring interns at TCS?",
        role="campus_recruiter",
        response=ChatResponse(
            reply="TCS hiring details.",
            steps=[],
            records_created=[],
            contacts=[],
            cards=[],
        ),
    )

    # Variations with extra spaces, punctuation, lowercase
    assert cache.get_cached_reply("  who is hiring interns at TCS?  ", role="campus_recruiter") is not None
    assert cache.get_cached_reply("who is hiring interns at tcs", role="campus_recruiter") is not None
    assert cache.get_cached_reply("WHO IS HIRING INTERNS AT TCS...", role="campus_recruiter") is not None


def test_demo_and_real_isolation():
    cache = LLMReplyCache()
    msg = "Show me student candidates"

    demo_resp = ChatResponse(reply="Demo student list", steps=[], records_created=[], contacts=[], cards=[])
    real_resp = ChatResponse(reply="Real student list", steps=[], records_created=[], contacts=[], cards=[])

    cache.set_cached_reply(msg, role="recruiter", response=demo_resp, is_demo=True)
    cache.set_cached_reply(msg, role="recruiter", response=real_resp, is_demo=False)

    hit_demo = cache.get_cached_reply(msg, role="recruiter", is_demo=True)
    hit_real = cache.get_cached_reply(msg, role="recruiter", is_demo=False)

    assert hit_demo is not None and hit_demo.reply == "Demo student list"
    assert hit_real is not None and hit_real.reply == "Real student list"


def test_invalidation_clears_cache_and_bumps_version():
    cache = LLMReplyCache()
    cache.set_cached_reply(
        "List placement stats",
        role="placement_officer",
        response=ChatResponse(reply="Stats 2027", steps=[], records_created=[], contacts=[], cards=[]),
    )
    assert cache.get_cached_reply("List placement stats", role="placement_officer") is not None
    assert cache.get_stats()["lake_version"] == 1

    # Invalidate
    cache.invalidate(reason="student_import")
    assert cache.get_cached_reply("List placement stats", role="placement_officer") is None
    stats = cache.get_stats()
    assert stats["cached_entries"] == 0
    assert stats["lake_version"] == 2
    assert stats["last_invalidation_reason"] == "student_import"


def test_skip_caching_mutation_responses():
    cache = LLMReplyCache()
    mutation_resp = ChatResponse(
        reply="Updated your profile.",
        steps=[],
        records_created=[RecordRef(table="students", id="stu-1", op="updated")],
        contacts=[],
        cards=[],
    )

    cache.set_cached_reply("My name is John", role="student", response=mutation_resp)
    # Mutation response should NOT be cached
    assert cache.get_cached_reply("My name is John", role="student") is None
    assert cache.get_stats()["cached_entries"] == 0


def test_cache_router_endpoints():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)

    # Test GET /v1/cache/stats
    res = client.get("/v1/cache/stats")
    assert res.status_code == 200
    data = res.json()
    assert "cached_entries" in data
    assert "lake_version" in data
    assert "saved_gemini_api_calls" in data

    # Test POST /v1/cache/clear
    clear_res = client.post("/v1/cache/clear", json={"reason": "test_suite_clear"})
    assert clear_res.status_code == 200
    clear_data = clear_res.json()
    assert clear_data["success"] is True
    assert clear_data["stats"]["last_invalidation_reason"] == "test_suite_clear"
