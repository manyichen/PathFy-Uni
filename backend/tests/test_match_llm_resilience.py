from app.domains.match import llm_refine, services


def test_network_failure_is_reported_and_sdk_retries_are_disabled(monkeypatch):
    calls = []
    client_options = {}

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            raise RuntimeError("network unavailable")

    class FakeClient:
        def __init__(self, **kwargs):
            client_options.update(kwargs)
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr(llm_refine, "OpenAI", FakeClient)
    payload, error = llm_refine.refine_top5_deepseek(
        {"scores": {}, "confidences": {}},
        [{"id": "job-1", "title": "测试岗位", "scores": {}, "confidences": {}, "match_preview": {"match_score": 80}}],
        api_key="test-key",
        model="test-model",
        timeout=35,
    )

    assert payload is None
    assert "network unavailable" in error
    assert len(calls) == 1
    assert client_options["max_retries"] == 0
    assert client_options["timeout"] == 35
    assert calls[0]["extra_body"] == {"thinking": {"type": "disabled"}}


def test_timeout_retries_once_with_a_smaller_candidate_pool(monkeypatch):
    calls = []

    def fake_refine(_profile, pool, **kwargs):
        calls.append((len(pool), kwargs["timeout"]))
        if len(calls) == 1:
            return None, "deepseek_http_error:APITimeoutError('Request timed out.')"
        return {"model": "test-model", "pool_size": len(pool), "top5": []}, ""

    monkeypatch.setattr(services, "refine_top5_deepseek", fake_refine)
    payload, meta = services._refine_with_timeout_fallback(
        {"scores": {}, "confidences": {}},
        [{"id": f"job-{index}"} for index in range(20)],
        api_key="test-key",
        model="test-model",
        configured_timeout=120,
        match_goal="fit",
    )

    assert payload == {"model": "test-model", "pool_size": 10, "top5": []}
    assert calls == [(20, 55.0), (10, 30.0)]
    assert meta["retry_attempted"] is True
    assert meta["degraded"] is True
    assert meta["fallback_reason"] == "timeout"
    assert meta["initial_pool_size"] == 20
    assert meta["fallback_pool_size"] == 10


def test_network_failure_retries_once_with_a_smaller_candidate_pool(monkeypatch):
    calls = []

    def fake_refine(_profile, pool, **kwargs):
        calls.append((len(pool), kwargs["timeout"]))
        if len(calls) == 1:
            return None, "deepseek_http_error:APIConnectionError('connection reset')"
        return {"model": "test-model", "pool_size": len(pool), "top5": []}, ""

    monkeypatch.setattr(services, "refine_top5_deepseek", fake_refine)
    payload, meta = services._refine_with_timeout_fallback(
        {"scores": {}, "confidences": {}},
        [{"id": f"job-{index}"} for index in range(20)],
        api_key="test-key",
        model="test-model",
        configured_timeout=120,
        match_goal="fit",
    )

    assert payload == {"model": "test-model", "pool_size": 10, "top5": []}
    assert calls == [(20, 55.0), (10, 30.0)]
    assert meta["fallback_reason"] == "network"


def test_invalid_response_retries_once_with_a_smaller_candidate_pool(monkeypatch):
    calls = []

    def fake_refine(_profile, pool, **kwargs):
        calls.append(len(pool))
        if len(calls) == 1:
            return None, "empty_response:finish_reason=length"
        return {"model": "test-model", "pool_size": len(pool), "top5": []}, ""

    monkeypatch.setattr(services, "refine_top5_deepseek", fake_refine)
    payload, meta = services._refine_with_timeout_fallback(
        {"scores": {}, "confidences": {}},
        [{"id": f"job-{index}"} for index in range(20)],
        api_key="test-key",
        model="test-model",
        configured_timeout=120,
        match_goal="fit",
    )

    assert payload is not None
    assert calls == [20, 10]
    assert meta["fallback_reason"] == "invalid_response"


def test_local_refinement_has_explainable_top5():
    profile = {
        "scores": {
            "cap_req_theory": 80,
            "cap_req_cross": 60,
            "cap_req_practice": 75,
            "cap_req_digital": 70,
            "cap_req_innovation": 65,
            "cap_req_teamwork": 75,
            "cap_req_social": 55,
            "cap_req_growth": 80,
        }
    }
    job_scores = dict(profile["scores"])
    job_scores["cap_req_cross"] = 75
    pool = [
        {
            "id": f"job-{index}",
            "title": f"岗位 {index}",
            "company": "测试公司",
            "location": "北京",
            "scores": job_scores,
            "conf_avg": 35,
            "match_preview": {"match_score": 88 - index},
        }
        for index in range(7)
    ]

    payload = services._local_refine_top5(profile, pool, match_goal="fit")

    assert payload["model"] == "local-capability-ranker-v1"
    assert len(payload["top5"]) == 5
    assert payload["top5"][0]["llm_fallback"] is True
    assert any("交叉学科" in line and "15 分" in line for line in payload["top5"][0]["gaps"])
    assert "置信度" in payload["top5"][0]["risks"][0]


def test_non_timeout_failure_is_not_retried_and_has_a_public_error(monkeypatch):
    calls = []

    def fake_refine(_profile, pool, **kwargs):
        calls.append((len(pool), kwargs["timeout"]))
        return None, "deepseek_http_error:AuthenticationError('invalid api key')"

    monkeypatch.setattr(services, "refine_top5_deepseek", fake_refine)
    payload, meta = services._refine_with_timeout_fallback(
        {"scores": {}, "confidences": {}},
        [{"id": f"job-{index}"} for index in range(20)],
        api_key="test-key",
        model="test-model",
        configured_timeout=120,
        match_goal="fit",
    )

    assert payload is None
    assert calls == [(20, 55.0)]
    assert meta["error_code"] == "authentication"
    assert "鉴权失败" in meta["error"]
    assert meta["retry_attempted"] is False
    assert meta["degraded"] is False
