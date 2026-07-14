"""Keep backend/.env.example synchronized with deployment-only Config reads."""

import re
from pathlib import Path

from app.domains.settings.registry import FIELD_MAP


BACKEND_ROOT = Path(__file__).parents[1]


def test_backend_env_example_covers_every_config_variable():
    config_source = (BACKEND_ROOT / "app/core/config.py").read_text(encoding="utf-8")
    example_source = (BACKEND_ROOT / ".env.example").read_text(encoding="utf-8")

    used = set(
        re.findall(r'(?:os\.getenv|_env_bool)\("([A-Z][A-Z0-9_]*)"', config_source)
    )
    used -= set(FIELD_MAP)  # Business compatibility fallbacks live in MySQL settings.
    documented = set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]*)=", example_source, re.MULTILINE))

    assert used <= documented, f"Missing from backend/.env.example: {sorted(used - documented)}"


def test_examples_do_not_contain_obvious_real_secrets():
    for path in (
        BACKEND_ROOT / ".env.example",
        BACKEND_ROOT.parent / "frontend/.env.example",
        BACKEND_ROOT.parent / "generate_graph/.env.example",
    ):
        content = path.read_text(encoding="utf-8")
        assert not re.search(r"\b(sk-|AIza)[A-Za-z0-9_-]{12,}", content), path
