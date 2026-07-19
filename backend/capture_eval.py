from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path

from app.ai_provider import MockAIProvider, OpenAIInterpretationProvider
from app.capture_models import ActionSeed, ActionType, ConfidenceCategory, EntityCandidate, StructuredInterpretation
from app.config import get_settings
from app.deterministic_interpreter import DeterministicInterpreter
from app.secret_provider import get_secret_provider


CORPUS = Path(__file__).resolve().parent / "evals" / "capture-v1.json"
REQUIRED = {
    "input", "timezone", "current_date", "candidate_items", "expected_deterministic_handling",
    "expected_intent", "expected_action_types", "expected_entity_match", "expected_clarification",
    "expected_risk_classification", "expected_confirmation_behavior", "expected_prohibition",
}


class FixtureEntities:
    def __init__(self, candidates):
        self.candidates = candidates

    def retrieve(self, *_args, **_kwargs):
        return self.candidates


def load_cases():
    value = json.loads(CORPUS.read_text(encoding="utf-8"))
    if value.get("version") != "capture-v1" or len(value.get("cases", [])) < 50:
        raise AssertionError("Capture evaluation corpus must be versioned and contain at least 50 cases.")
    for case in value["cases"]:
        missing = REQUIRED - set(case)
        if missing:
            raise AssertionError(f"{case.get('id', 'unknown')} is missing: {sorted(missing)}")
    return value["cases"]


def candidate(value):
    return EntityCandidate.model_validate({
        "entity_type": value["entity_type"],
        "entity_id": value["entity_id"],
        "display_title": value["display_title"],
        "item_type": value.get("item_type"),
        "safe_aliases": value.get("safe_aliases", []),
        "relevant_responsibility_id": value.get("relevant_responsibility_id"),
        "relevant_responsibility_title": value.get("relevant_responsibility_title"),
        "relevant_dates": value.get("relevant_dates", {}),
        "match_reasons": ["evaluation fixture"],
        "score": value.get("score", 0),
    })


def deterministic(cases):
    checked = 0
    for case in cases:
        candidates = [candidate(item) for item in case["candidate_items"]]
        interpreter = DeterministicInterpreter(FixtureEntities(candidates))
        result, _ = interpreter.interpret(
            user_id="eval-user",
            text=case["input"],
            captured_at=datetime.fromisoformat(f"{case['current_date']}T12:00:00+00:00"),
            timezone_name=case["timezone"],
        )
        if case["expected_deterministic_handling"] == "handled":
            if result is None:
                raise AssertionError(f"{case['id']}: expected deterministic handling")
            actual = [item.action_type.value for item in result.actions]
            if actual != case["expected_action_types"]:
                raise AssertionError(f"{case['id']}: expected {case['expected_action_types']}, got {actual}")
            checked += 1
    return checked


def mock(cases):
    checked = 0
    for case in cases:
        output = StructuredInterpretation(
            supported=True,
            confidence=ConfidenceCategory.LOW,
            summary=f"Mock evaluation for {case['expected_intent']}.",
            actions=[ActionSeed(action_type=ActionType.NO_ACTION, fields={"reason": "Evaluation fixture."}, explanation="No changes in mock evaluation.")],
        )
        provider = MockAIProvider([output])
        result = provider.interpret_capture(
            original_text=case["input"],
            captured_at=datetime.fromisoformat(f"{case['current_date']}T12:00:00+00:00"),
            timezone_name=case["timezone"],
            locale="en-US",
            entity_candidates=[candidate(item) for item in case["candidate_items"]],
            safety_identifier="eval-user",
        )
        if result.interpretation.summary != output.summary or len(provider.calls) != 1:
            raise AssertionError(f"{case['id']}: mock provider result mismatch")
        checked += 1
    return checked


def live(cases, allow_paid):
    if not allow_paid:
        raise SystemExit("Live evaluation is paid and requires --allow-paid.")
    settings = get_settings()
    provider = OpenAIInterpretationProvider(settings, get_secret_provider(settings))
    checked = 0
    for case in cases:
        provider.interpret_capture(
            original_text=case["input"],
            captured_at=datetime.fromisoformat(f"{case['current_date']}T12:00:00+00:00"),
            timezone_name=case["timezone"],
            locale="en-US",
            entity_candidates=[candidate(item) for item in case["candidate_items"]],
            safety_identifier="explicit-paid-evaluation",
        )
        checked += 1
    return checked


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("deterministic", "mock", "live"), required=True)
    parser.add_argument("--allow-paid", action="store_true")
    args = parser.parse_args()
    cases = load_cases()
    checked = {"deterministic": deterministic, "mock": mock}.get(args.mode)
    count = checked(cases) if checked else live(cases, args.allow_paid)
    print(json.dumps({"version": "capture-v1", "mode": args.mode, "cases": len(cases), "checked": count}))


if __name__ == "__main__":
    main()
