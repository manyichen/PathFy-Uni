"""privacy 脱敏模块单元测试。"""

from __future__ import annotations

import pytest

from app import create_app
from app.infrastructure.privacy import (
    llm_privacy_notice,
    privacy_student_profile,
    redact_payload,
    redact_text,
    storage_safe_text,
)


@pytest.fixture
def app():
    flask_app = create_app()
    flask_app.config.update(
        {
            "LLM_PRIVACY_MODE": True,
            "LLM_MAX_FIELD_CHARS": 1200,
            "LLM_MAX_RESUME_CHARS": 6000,
            "LOCAL_STORE_RAW_RESUME_TEXT": False,
        }
    )
    return flask_app


def test_redact_email_phone_id(app):
    with app.app_context():
        text = "联系 zhang@test.com 手机 13812345678 身份证 110101199001011234"
        out = redact_text(text)
        assert "[REDACTED_EMAIL]" in out
        assert "[REDACTED_PHONE]" in out
        assert "[REDACTED_ID_CARD]" in out
        assert "zhang@test.com" not in out


def test_redact_url_token_query(app):
    with app.app_context():
        text = "see https://example.com/path?token=abc123&foo=1"
        out = redact_text(text)
        assert "[REDACTED_URL]" in out or "[REDACTED_TOKEN]" in out


def test_redact_payload_strips_pii_keys(app):
    with app.app_context():
        payload = {
            "user_id": 9,
            "display_name": "张三",
            "resume_text": "手机号 13900001111",
            "job_id": "job-1",
        }
        safe = redact_payload(payload)
        assert "user_id" not in safe
        assert safe.get("job_id") == "job-1"
        assert safe.get("display_name") == "[REDACTED_NAME]"
        assert "resume_text" not in safe


def test_privacy_student_profile_anonymized(app):
    with app.app_context():
        slim = privacy_student_profile(
            {
                "id": "1",
                "display_name": "李四",
                "scores": {"cap_req_theory": 70},
                "confidences": {"cap_conf_theory": 0.8},
                "resume_excerpt": "邮箱 a@b.com",
            },
            include_excerpt=False,
        )
        assert "display_name" not in slim
        assert "id" not in slim
        assert "resume_excerpt" not in slim
        assert slim["scores"]["cap_req_theory"] == 70


def test_storage_safe_text_redacts_by_default(app):
    with app.app_context():
        stored = storage_safe_text("call me 13812345678", kind="resume")
        assert "[REDACTED_PHONE]" in stored


def test_privacy_mode_off_passthrough(app):
    with app.app_context():
        app.config["LLM_PRIVACY_MODE"] = False
        raw = "email: keep@me.com"
        assert redact_text(raw) == raw
        assert llm_privacy_notice() == ""
