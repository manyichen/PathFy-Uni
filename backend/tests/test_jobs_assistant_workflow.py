from flask import Flask

from app.domains.jobs import assistant
from app.infrastructure import llm


def _setting(key, default=None):
    values = {"AI_MAX_RETURN_JOBS": 40, "AI_CONTEXT_WINDOW": 6}
    return values.get(key, default)


def test_assistant_uses_configured_result_window_instead_of_twenty(monkeypatch):
    monkeypatch.setattr(assistant, "setting", _setting)

    assert assistant._normalize_filters({})["limit"] == 40
    assert assistant._normalize_filters({"limit": 12})["limit"] == 12
    assert assistant._normalize_filters({"limit": 200})["limit"] == 40


def test_sparse_filter_patch_preserves_unmentioned_previous_conditions(monkeypatch):
    monkeypatch.setattr(assistant, "setting", _setting)
    previous = assistant._normalize_filters({"keywords": ["Java"], "locations": ["北京"]})
    current = assistant._normalize_filters({"keywords": ["后端"]}, sparse=True)

    merged = assistant._merge_filters(previous, current)

    assert merged["keywords"] == ["后端"]
    assert merged["locations"] == ["北京"]
    assert merged["limit"] == 40


def test_multiple_keywords_are_broadening_terms_not_an_impossible_and_chain(monkeypatch):
    monkeypatch.setattr(assistant, "setting", _setting)

    query, params = assistant._build_filter_cypher(
        assistant._normalize_filters({"keywords": ["计算机", "实践"]})
    )

    assert "any(kw IN $keywords WHERE" in query
    assert "kw_0" not in params
    assert params["keywords"] == ["计算机", "实践"]
    assert params["limit"] == 40


def test_intent_parser_disables_thinking_and_omits_unmentioned_filter_keys(monkeypatch):
    monkeypatch.setattr(assistant, "setting", _setting)
    captured = {}

    def fake_call(*_args, **kwargs):
        captured.update(kwargs)
        return {"intent": "filter", "operation": "merge", "filters": {"locations": ["上海"]}}

    monkeypatch.setattr(assistant, "call_ark_json", fake_call)
    result = assistant._parse_intent_filters(
        "改成上海",
        assistant._normalize_filters({"keywords": ["Java"], "locations": ["北京"]}),
        [],
        has_previous_results=True,
    )

    assert captured["thinking"] == "disabled"
    assert result["filters"]["keywords"] == ["Java"]
    assert result["filters"]["locations"] == ["上海"]


def test_ark_json_forwards_explicit_thinking_mode(monkeypatch):
    request = {}

    class FakeCompletions:
        def create(self, **kwargs):
            request.update(kwargs)
            message = type("Message", (), {"content": '{"ok":true}'})()
            choice = type("Choice", (), {"message": message})()
            return type("Response", (), {"choices": [choice]})()

    client = type("Client", (), {"chat": type("Chat", (), {"completions": FakeCompletions()})()})()
    monkeypatch.setattr(llm, "build_ark_openai_client", lambda required=False: client)
    app = Flask(__name__)
    app.config.update(ARK_MODEL="test-model", LLM_PRIVACY_MODE=False)

    with app.app_context():
        result = llm.call_ark_json("输出 JSON", {"value": 1}, thinking="disabled")

    assert result == {"ok": True}
    assert request["extra_body"] == {"thinking": {"type": "disabled"}}
