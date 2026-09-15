#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

FINAL_KEYS = {
    "must_contain_any", "must_contain_all", "must_contain_groups",
    "must_not_contain", "max_chars", "require_cjk", "forbid_cjk",
}
CONVERSATION_KEYS = {
    "must_contain_any", "must_contain_groups", "must_not_contain",
    "max_identical_responses",
}
PROVIDERS = {"fixture", "openai-compatible", "ollama-native"}


def load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"file not found: {path}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: line {exc.lineno}, column {exc.colno}: {exc.msg}")


def strings(value: Any, where: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(f"{where} must be {'a non-empty' if nonempty else 'a'} list of strings")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{where} must contain only non-empty strings")
    return value


def validate_character(data: Any, where: str) -> None:
    if not isinstance(data, dict):
        raise ValueError(f"{where} must be a JSON object")
    if not isinstance(data.get("name"), str) or not data["name"].strip():
        raise ValueError(f"{where}.name must be a non-empty string")
    for key in ("identity", "personality", "knowledge_boundaries", "style_en", "style_zh"):
        if key in data:
            strings(data[key], f"{where}.{key}")
    if "relationships" in data:
        rel = data["relationships"]
        if not isinstance(rel, dict) or not all(isinstance(k, str) and k and isinstance(v, str) and v for k, v in rel.items()):
            raise ValueError(f"{where}.relationships must map non-empty strings to non-empty strings")
    if "system_prompt" in data and not isinstance(data["system_prompt"], str):
        raise ValueError(f"{where}.system_prompt must be a string")


def validate_string_list(checks: dict[str, Any], key: str, where: str) -> None:
    if key in checks:
        strings(checks[key], f"{where}.{key}", nonempty=True)


def validate_groups(checks: dict[str, Any], key: str, where: str) -> None:
    if key not in checks:
        return
    groups = checks[key]
    if not isinstance(groups, list) or not groups:
        raise ValueError(f"{where}.{key} must be a non-empty list of string lists")
    for idx, group in enumerate(groups):
        strings(group, f"{where}.{key}[{idx}]", nonempty=True)


def validate_checks(checks: Any, where: str, *, conversation: bool = False) -> None:
    if not isinstance(checks, dict):
        raise ValueError(f"{where} must be an object")
    allowed = CONVERSATION_KEYS if conversation else FINAL_KEYS
    unknown = sorted(set(checks) - allowed)
    if unknown:
        raise ValueError(f"{where} contains unsupported check keys: {unknown}")
    for key in ("must_contain_any", "must_contain_all", "must_not_contain"):
        if key in allowed:
            validate_string_list(checks, key, where)
    validate_groups(checks, "must_contain_groups", where)
    if "max_chars" in checks and (not isinstance(checks["max_chars"], int) or isinstance(checks["max_chars"], bool) or checks["max_chars"] <= 0):
        raise ValueError(f"{where}.max_chars must be a positive integer")
    for key in ("require_cjk", "forbid_cjk"):
        if key in checks and not isinstance(checks[key], bool):
            raise ValueError(f"{where}.{key} must be true or false")
    if "max_identical_responses" in checks and (
        not isinstance(checks["max_identical_responses"], int)
        or isinstance(checks["max_identical_responses"], bool)
        or checks["max_identical_responses"] < 1
    ):
        raise ValueError(f"{where}.max_identical_responses must be a positive integer")


def validate_tests(data: Any, where: str) -> None:
    if not isinstance(data, list) or not data:
        raise ValueError(f"{where} must be a non-empty JSON list")
    ids: set[str] = set()
    for idx, test in enumerate(data):
        base = f"{where}[{idx}]"
        if not isinstance(test, dict):
            raise ValueError(f"{base} must be an object")
        test_id = test.get("id")
        if not isinstance(test_id, str) or not test_id.strip():
            raise ValueError(f"{base}.id must be a non-empty string")
        if test_id in ids:
            raise ValueError(f"duplicate test id: {test_id}")
        ids.add(test_id)
        for key in ("category", "description"):
            if not isinstance(test.get(key), str) or not test[key].strip():
                raise ValueError(f"{base}.{key} must be a non-empty string")
        strings(test.get("turns"), f"{base}.turns", nonempty=True)
        validate_checks(test.get("checks", {}), f"{base}.checks")
        validate_checks(test.get("conversation_checks", {}), f"{base}.conversation_checks", conversation=True)
        if test.get("checks", {}).get("require_cjk") and test.get("checks", {}).get("forbid_cjk"):
            raise ValueError(f"{base}.checks cannot require and forbid CJK at the same time")


def validate_models(data: Any, where: str) -> None:
    if not isinstance(data, list) or not data:
        raise ValueError(f"{where} must be a non-empty JSON list")
    for idx, model in enumerate(data):
        base = f"{where}[{idx}]"
        if not isinstance(model, dict):
            raise ValueError(f"{base} must be an object")
        provider = model.get("provider", "openai-compatible")
        if provider not in PROVIDERS:
            raise ValueError(f"{base}.provider must be one of {sorted(PROVIDERS)}")
        if provider != "fixture" and (not isinstance(model.get("model"), str) or not model["model"].strip()):
            raise ValueError(f"{base}.model is required for {provider}")
        if provider == "fixture" and not (model.get("fixture") or model.get("fixtures")):
            raise ValueError(f"{base} fixture provider requires fixture or fixtures")
        for key in ("timeout_seconds", "max_tokens"):
            if key in model and (not isinstance(model[key], int) or isinstance(model[key], bool) or model[key] <= 0):
                raise ValueError(f"{base}.{key} must be a positive integer")


def validate_suite(data: Any, where: str) -> None:
    if not isinstance(data, list) or not data:
        raise ValueError(f"{where} must be a non-empty JSON list")
    ids: set[str] = set()
    for idx, scenario in enumerate(data):
        base = f"{where}[{idx}]"
        if not isinstance(scenario, dict):
            raise ValueError(f"{base} must be an object")
        sid = scenario.get("id")
        if not isinstance(sid, str) or not sid.strip():
            raise ValueError(f"{base}.id must be a non-empty string")
        if sid in ids:
            raise ValueError(f"duplicate suite scenario id: {sid}")
        ids.add(sid)
        for key in ("character", "tests"):
            if not isinstance(scenario.get(key), str) or not scenario[key].strip():
                raise ValueError(f"{base}.{key} must be a non-empty path string")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate CharacterBench characters, tests, model configs, and suites.")
    parser.add_argument("--character")
    parser.add_argument("--tests")
    parser.add_argument("--models")
    parser.add_argument("--suite")
    args = parser.parse_args()
    if not any(vars(args).values()):
        parser.error("provide at least one of --character, --tests, --models, or --suite")
    jobs = [
        (args.character, validate_character, "character"),
        (args.tests, validate_tests, "tests"),
        (args.models, validate_models, "models"),
        (args.suite, validate_suite, "suite"),
    ]
    try:
        for raw, fn, label in jobs:
            if raw:
                path = Path(raw)
                fn(load(path), str(path))
                print(f"PASS {label}: {path}")
    except ValueError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
