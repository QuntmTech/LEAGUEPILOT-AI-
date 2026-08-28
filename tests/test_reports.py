from __future__ import annotations

from app.config import Settings
from app.demo import demo_snapshot
from app.services.ai import Narrator, RulesNarrator
from app.services.reports import build_configured_weekly_report, build_weekly_report_resilient


class FailingNarrator(Narrator):
    def create_weekly_narrative(self, facts: dict[str, object]) -> str:
        raise ValueError("provider returned malformed content")


class EmptyNarrator(Narrator):
    def create_weekly_narrative(self, facts: dict[str, object]) -> str:
        return "   "


def test_weekly_report_uses_deterministic_fallback_when_ai_fails() -> None:
    body, facts, mode = build_weekly_report_resilient(demo_snapshot(2026), FailingNarrator())

    assert mode == "rules-fallback"
    assert facts["narration_fallback"] is True
    assert "League Pulse" in body
    assert "no scores or injuries are invented" in body


def test_weekly_report_reports_rules_mode_without_false_fallback() -> None:
    body, facts, mode = build_weekly_report_resilient(demo_snapshot(2026), RulesNarrator())

    assert mode == "rules"
    assert "narration_fallback" not in facts
    assert "Week 6" in body


def test_weekly_report_falls_back_when_narrator_returns_empty_content() -> None:
    body, facts, mode = build_weekly_report_resilient(demo_snapshot(2026), EmptyNarrator())

    assert mode == "rules-fallback"
    assert facts["narration_fallback"] is True
    assert "Week 6" in body


def test_misconfigured_optional_ai_uses_rules_fallback() -> None:
    settings = Settings(_env_file=None, ai_provider="gemini", ai_model="")

    body, facts, mode = build_configured_weekly_report(demo_snapshot(2026), settings)

    assert mode == "rules-fallback"
    assert facts["narration_fallback"] is True
    assert "Week 6" in body
