#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent


@dataclass
class TestResult:
    test_id: str
    category: str
    description: str
    score: float
    response: str
    responses: list[str]
    reasons: list[str]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_system_prompt(character: dict[str, Any]) -> str:
    sections = [
        character.get("system_prompt", ""),
        "Identity:\n- " + "\n- ".join(character.get("identity", [])),
        "Personality:\n- " + "\n- ".join(character.get("personality", [])),
        "Knowledge boundaries:\n- " + "\n- ".join(character.get("knowledge_boundaries", [])),
        "English style:\n- " + "\n- ".join(character.get("style_en", [])),
        "Chinese style:\n- " + "\n- ".join(character.get("style_zh", [])),
    ]
    relationships = character.get("relationships", {})
    if relationships:
        sections.append(
            "Relationships:\n"
            + "\n".join(
                f"- {name}: {description}"
                for name, description in relationships.items()
            )
        )
    return "\n\n".join(section for section in sections if section.strip())


def chat_completion(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.4,
    max_tokens: int = 120,
    request_timeout: float = 60.0,
) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = json.dumps(
        {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "reasoning_effort": "none",
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=request_timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except TimeoutError as exc:
        raise RuntimeError(f"Provider request timed out for model {model}") from exc
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Provider returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach provider: {exc}") from exc

    return data["choices"][0]["message"]["content"].strip()



def ollama_native_chat(
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.4,
    max_tokens: int = 120,
    request_timeout: float = 60.0,
) -> str:
    url = base_url.rstrip("/") + "/api/chat"
    payload = json.dumps(
        {
            "model": model,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=request_timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except TimeoutError as exc:
        raise RuntimeError(f"Ollama request timed out for model {model}") from exc
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach Ollama: {exc}") from exc
    return data["message"]["content"].strip()

def run_live_test(
    character: dict[str, Any],
    test: dict[str, Any],
    base_url: str,
    api_key: str,
    model: str,
    max_tokens: int = 120,
    request_timeout: float = 60.0,
) -> list[str]:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": build_system_prompt(character)}
    ]
    responses: list[str] = []

    for turn in test["turns"]:
        messages.append({"role": "user", "content": turn})
        answer = chat_completion(base_url, api_key, model, messages, max_tokens=max_tokens, request_timeout=request_timeout)
        responses.append(answer)
        messages.append({"role": "assistant", "content": answer})

    return responses


def contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", text))


def normalize_for_match(text: str) -> str:
    return (
        text.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("—", "-")
        .replace("–", "-")
    )


def term_present(text: str, term: str) -> bool:
    text = normalize_for_match(text)
    term = normalize_for_match(term)
    if re.fullmatch(r"[A-Za-z0-9_-]+", term):
        return bool(
            re.search(
                r"(?<![A-Za-z0-9_-])"
                + re.escape(term)
                + r"(?![A-Za-z0-9_-])",
                text,
                re.IGNORECASE,
            )
        )
    return term.casefold() in text.casefold()


def response_criteria(
    response: str,
    checks: dict[str, Any],
) -> list[tuple[bool, str]]:
    criteria: list[tuple[bool, str]] = []

    required_any = checks.get("must_contain_any", [])
    if required_any:
        passed = any(term_present(response, term) for term in required_any)
        criteria.append(
            (
                passed,
                "contains at least one expected signal"
                if passed
                else f"missing expected signal: one of {required_any}",
            )
        )

    required_all = checks.get("must_contain_all", [])
    if required_all:
        missing = [term for term in required_all if not term_present(response, term)]
        criteria.append(
            (
                not missing,
                "contains all required signals"
                if not missing
                else f"missing required text: {missing}",
            )
        )

    required_groups = checks.get("must_contain_groups", [])
    if required_groups:
        missing_groups = [
            group for group in required_groups
            if not any(term_present(response, term) for term in group)
        ]
        criteria.append(
            (
                not missing_groups,
                "contains a signal from every required group"
                if not missing_groups
                else f"missing required signal groups: {missing_groups}",
            )
        )

    forbidden = checks.get("must_not_contain", [])
    if forbidden:
        hits = [term for term in forbidden if term_present(response, term)]
        criteria.append(
            (
                not hits,
                "avoids forbidden claims/style"
                if not hits
                else f"contains forbidden text: {hits}",
            )
        )

    max_chars = checks.get("max_chars")
    if max_chars:
        passed = len(response) <= max_chars
        criteria.append(
            (
                passed,
                f"length <= {max_chars}"
                if passed
                else f"too long: {len(response)} chars > {max_chars}",
            )
        )

    if checks.get("require_cjk"):
        passed = contains_cjk(response)
        criteria.append(
            (passed, "contains Chinese text" if passed else "expected Chinese text")
        )

    if checks.get("forbid_cjk"):
        passed = not contains_cjk(response)
        criteria.append(
            (passed, "stays in English" if passed else "unexpected Chinese text in English response")
        )

    return criteria


def conversation_criteria(
    responses: list[str],
    checks: dict[str, Any],
) -> list[tuple[bool, str]]:
    criteria: list[tuple[bool, str]] = []
    if not checks:
        return criteria

    joined = "\n".join(responses)

    required_any = checks.get("must_contain_any", [])
    if required_any:
        passed = any(term_present(joined, term) for term in required_any)
        criteria.append(
            (
                passed,
                "conversation contains an expected signal"
                if passed
                else f"conversation missing expected signal: one of {required_any}",
            )
        )

    required_groups = checks.get("must_contain_groups", [])
    if required_groups:
        missing_groups = [
            group for group in required_groups
            if not any(term_present(joined, term) for term in group)
        ]
        criteria.append(
            (
                not missing_groups,
                "conversation contains a signal from every required group"
                if not missing_groups
                else f"conversation missing required signal groups: {missing_groups}",
            )
        )

    forbidden = checks.get("must_not_contain", [])
    if forbidden:
        hits = [term for term in forbidden if term_present(joined, term)]
        criteria.append(
            (
                not hits,
                "conversation avoids forbidden claims/style"
                if not hits
                else f"conversation contains forbidden text: {hits}",
            )
        )

    max_identical = checks.get("max_identical_responses")
    if max_identical is not None and responses:
        normalized = [" ".join(response.casefold().split()) for response in responses]
        counts = {item: normalized.count(item) for item in set(normalized)}
        highest = max(counts.values())
        passed = highest <= int(max_identical)
        criteria.append(
            (
                passed,
                f"no response repeated more than {max_identical} times"
                if passed
                else f"same response repeated {highest} times",
            )
        )

    return criteria


def score_criteria(
    criteria: list[tuple[bool, str]],
) -> tuple[float, list[str]]:
    if not criteria:
        return 10.0, ["no checks configured"]

    # Penalty-based scoring prevents a subtle metric bug: adding a new check
    # that passes must never improve a response that already failed existing
    # checks. Three independent failures are enough to bottom out a test.
    failure_count = sum(1 for ok, _ in criteria if not ok)
    score = round(max(0.0, 10.0 - failure_count * (10.0 / 3.0)), 1)
    reasons = [("PASS: " if ok else "FAIL: ") + reason for ok, reason in criteria]
    return score, reasons


def score_response(
    response: str,
    checks: dict[str, Any],
) -> tuple[float, list[str]]:
    return score_criteria(response_criteria(response, checks))


def score_test(
    responses: list[str],
    final_checks: dict[str, Any],
    conversation_checks: dict[str, Any] | None = None,
) -> tuple[float, list[str]]:
    criteria = response_criteria(responses[-1], final_checks)
    criteria.extend(conversation_criteria(responses, conversation_checks or {}))
    return score_criteria(criteria)


def category_scores(results: list[TestResult]) -> dict[str, float]:
    grouped: dict[str, list[float]] = {}
    for result in results:
        grouped.setdefault(result.category, []).append(result.score)
    return {
        category: round(sum(scores) / len(scores), 1)
        for category, scores in grouped.items()
    }


def build_summary(
    character: dict[str, Any],
    results: list[TestResult],
    provider_label: str,
) -> dict[str, Any]:
    overall = round(
        sum(result.score for result in results) / max(len(results), 1), 1
    )
    return {
        "character": character["name"],
        "provider": provider_label,
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "overall": overall,
        "categories": category_scores(results),
        "tests": [asdict(result) for result in results],
    }


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        f"# CharacterBench report — {summary['character']}",
        "",
        f"- **Provider:** {summary['provider']}",
        f"- **Generated:** {summary['generated_utc']}",
        f"- **Overall:** **{summary['overall']}/10**",
        "",
        "## Category scores",
        "",
        "| Category | Score |",
        "|---|---:|",
    ]

    for category, score in summary["categories"].items():
        lines.append(f"| {category} | {score:.1f}/10 |")

    lines += ["", "## Test results", ""]
    for result in summary["tests"]:
        score = result["score"]
        icon = "✅" if score >= 8 else ("⚠️" if score >= 5 else "❌")
        quoted_response = result["response"].replace("\n", "\n> ")
        lines += [
            f"### {icon} {result['test_id']} — {score}/10",
            "",
            result["description"],
            "",
            "**Final response**",
            "",
            f"> {quoted_response}",
            "",
            "**Checks**",
            "",
        ]
        lines.extend(f"- {reason}" for reason in result["reasons"])
        lines.append("")

    failures = [result for result in summary["tests"] if result["score"] < 8]
    lines += ["## Attention needed", ""]
    if not failures:
        lines.append("No tests scored below 8/10.")
    else:
        for result in failures:
            lines.append(
                f"- **{result['test_id']} ({result['category']})** — "
                f"{result['score']}/10"
            )
    lines.append("")
    return "\n".join(lines)


def evaluate(
    character: dict[str, Any],
    tests: list[dict[str, Any]],
    *,
    provider: str,
    fixture_path: Path | None = None,
    base_url: str = "http://localhost:11434/v1",
    api_key: str = "local",
    model: str = "local-model",
    max_tokens: int = 120,
    request_timeout: float = 60.0,
) -> tuple[list[TestResult], str]:
    fixtures: dict[str, list[str]] = {}
    if provider == "fixture":
        if fixture_path is None:
            raise ValueError("fixture_path is required for fixture provider")
        fixtures = load_json(fixture_path)

    results: list[TestResult] = []
    for test in tests:
        if provider == "fixture":
            responses = fixtures.get(test["id"])
            if not responses:
                raise ValueError(f"Missing fixture for {test['id']}")
        elif provider == "openai-compatible":
            responses = run_live_test(
                character,
                test,
                base_url,
                api_key,
                model,
                max_tokens=max_tokens,
                request_timeout=request_timeout,
            )
        elif provider == "ollama-native":
            messages: list[dict[str, str]] = [
                {"role": "system", "content": build_system_prompt(character)}
            ]
            responses = []
            for turn in test["turns"]:
                messages.append({"role": "user", "content": turn})
                answer = ollama_native_chat(base_url, model, messages, max_tokens=max_tokens, request_timeout=request_timeout)
                responses.append(answer)
                messages.append({"role": "assistant", "content": answer})
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        final_response = responses[-1]
        score, reasons = score_test(
            responses,
            test.get("checks", {}),
            test.get("conversation_checks", {}),
        )
        results.append(
            TestResult(
                test_id=test["id"],
                category=test["category"],
                description=test["description"],
                score=score,
                response=final_response,
                responses=responses,
                reasons=reasons,
            )
        )

    provider_label = (
        f"fixture: {fixture_path.name if fixture_path else 'unknown'}"
        if provider == "fixture"
        else f"{model} @ {base_url} ({provider})"
    )
    return results, provider_label


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate whether an LLM stays in character."
    )
    parser.add_argument(
        "--character",
        default=str(ROOT / "characters" / "demo.json"),
    )
    parser.add_argument(
        "--tests",
        default=str(ROOT / "tests" / "tests.json"),
    )
    parser.add_argument(
        "--provider",
        choices=["fixture", "openai-compatible", "ollama-native"],
        default="fixture",
    )
    parser.add_argument(
        "--fixture",
        default=str(ROOT / "fixtures" / "demo_responses.json"),
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("CHARACTERBENCH_BASE_URL", "http://localhost:11434/v1"),
    )
    parser.add_argument(
        "--model",
        default=os.getenv("CHARACTERBENCH_MODEL", "local-model"),
    )
    parser.add_argument(
        "--api-key-env",
        default="CHARACTERBENCH_API_KEY",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=120,
        help="Maximum generated tokens per assistant turn.",
    )
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=60.0,
        help="Per-request timeout in seconds.",
    )
    parser.add_argument(
        "--report",
        default=str(ROOT / "reports" / "latest.md"),
    )
    parser.add_argument(
        "--summary-json",
        default="",
        help="Optional machine-readable JSON output path.",
    )
    args = parser.parse_args()

    character = load_json(Path(args.character))
    tests = load_json(Path(args.tests))
    api_key = os.getenv(args.api_key_env, "local")

    try:
        results, provider_label = evaluate(
            character,
            tests,
            provider=args.provider,
            fixture_path=Path(args.fixture) if args.provider == "fixture" else None,
            base_url=args.base_url,
            api_key=api_key,
            model=args.model,
            max_tokens=args.max_tokens,
            request_timeout=args.request_timeout,
        )
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    for result in results:
        print(f"{result.test_id:<16} {result.score:>4.1f}/10")

    summary = build_summary(character, results, provider_label)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(summary), encoding="utf-8")

    if args.summary_json:
        summary_path = Path(args.summary_json)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(f"\nOverall: {summary['overall']:.1f}/10")
    print(f"Report: {report_path}")
    if args.summary_json:
        print(f"JSON: {args.summary_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
