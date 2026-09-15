#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
SAFE_CATEGORIES = {
    "Identity", "Personality", "Knowledge", "Relationships", "Style", "Language",
    "Robustness", "Memory", "Long conversation", "Values",
}


def safe_categories(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    kept: dict[str, float] = {}
    other: list[float] = []
    for key, score in value.items():
        if not isinstance(score, (int, float)):
            continue
        if key in SAFE_CATEGORIES:
            kept[str(key)] = float(score)
        else:
            other.append(float(score))
    if other:
        kept["Other"] = round(sum(other) / len(other), 1)
    return kept


def weak_tests(tests: Any) -> list[dict[str, Any]]:
    if not isinstance(tests, list):
        return []
    weak: list[dict[str, Any]] = []
    for item in tests:
        if not isinstance(item, dict):
            continue
        score = item.get("score")
        if not isinstance(score, (int, float)) or score >= 8:
            continue
        category = item.get("category") if item.get("category") in SAFE_CATEGORIES else "Other"
        weak.append({"test": f"weak_{len(weak) + 1}", "category": category, "score": score})
    return weak


def provider_family(value: Any) -> str:
    text = str(value or "").casefold()
    if "fixture" in text:
        return "fixture"
    if "ollama" in text:
        return "ollama-native"
    if "openai" in text or "compatible" in text:
        return "openai-compatible"
    return "unspecified"


def error_class(value: Any) -> str:
    text = str(value or "").casefold()
    if "timeout" in text or "timed out" in text:
        return "timeout"
    if "reach" in text or "connection" in text:
        return "provider-unreachable"
    if "http" in text:
        return "provider-http-error"
    if "config" in text or "missing" in text or "invalid" in text:
        return "configuration-error"
    return "runtime-error"


def compact_run(run: dict[str, Any], scenario_number: int | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "status": run.get("status", "ok") if run.get("status") in {"ok", "error", "partial"} else "unknown",
        "overall": run.get("overall") if isinstance(run.get("overall"), (int, float)) else None,
        "categories": safe_categories(run.get("categories")),
        "weak_tests": weak_tests(run.get("tests")),
    }
    if scenario_number is not None:
        out["scenario"] = f"scenario_{scenario_number}"
    if run.get("status") == "error":
        out["error_class"] = error_class(run.get("error"))
    config = run.get("config")
    if isinstance(config, dict):
        out["provider"] = provider_family(config.get("provider"))
    return out


def build_packet(data: dict[str, Any]) -> dict[str, Any]:
    packet: dict[str, Any] = {
        "characterbench_version": VERSION,
        "privacy": "No prompts, responses, transcripts, names, labels, endpoint URLs, or local paths included.",
    }
    models = data.get("models")
    if isinstance(models, list):
        if "suite" in data:
            packet["result_type"] = "suite"
            packet["scenario_count"] = len(data.get("suite") or [])
            safe_models = []
            for index, model in enumerate(models, start=1):
                scenarios = [
                    compact_run(run, scenario_index)
                    for scenario_index, run in enumerate(model.get("scenarios", []), start=1)
                    if isinstance(run, dict)
                ]
                safe_models.append({
                    "model": f"model_{index}",
                    "status": model.get("status") if model.get("status") in {"ok", "error", "partial"} else "unknown",
                    "overall": model.get("overall") if isinstance(model.get("overall"), (int, float)) else None,
                    "categories": safe_categories(model.get("categories")),
                    "scenarios": scenarios,
                })
            packet["models"] = safe_models
        else:
            packet["result_type"] = "comparison"
            packet["models"] = [
                {"model": f"model_{index}", **compact_run(model)}
                for index, model in enumerate(models, start=1)
                if isinstance(model, dict)
            ]
        return packet

    if "overall" in data and "tests" in data:
        packet["result_type"] = "single"
        packet.update(compact_run(data))
        packet["provider"] = provider_family(data.get("provider"))
        return packet

    raise ValueError("Unrecognised CharacterBench JSON shape")


def render_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# CharacterBench privacy-safe feedback packet",
        "",
        f"- Version: `{packet['characterbench_version']}`",
        f"- Result type: `{packet['result_type']}`",
        "- Private prompts, responses, names, labels, URLs and local paths are intentionally excluded.",
        "",
    ]
    if packet["result_type"] == "single":
        lines += [
            f"- Overall: **{packet.get('overall')}/10**",
            f"- Provider: `{packet.get('provider', 'unspecified')}`",
            "",
            "## Weak tests",
            "",
        ]
        weak = packet.get("weak_tests", [])
        lines += [f"- `{x['test']}` ({x['category']}): {x['score']}/10" for x in weak] or ["- None below 8/10."]
    else:
        lines += ["## Results", ""]
        for model in packet.get("models", []):
            lines += [
                f"### {model['model']}",
                "",
                f"- Status: `{model.get('status')}`",
            ]
            if model.get("status") == "error":
                lines.append(f"- Result: **ERROR** ({model.get('error_class', 'runtime-error')})")
            else:
                lines.append(f"- Overall: **{model.get('overall')}/10**")
            if packet["result_type"] == "comparison":
                weak = model.get("weak_tests", [])
                if model.get("status") == "error":
                    pass
                else:
                    lines += [f"- Weak: `{x['test']}` ({x['category']}) {x['score']}/10" for x in weak] or ["- No tests below 8/10."]
            else:
                for scenario in model.get("scenarios", []):
                    lines.append(f"- {scenario['scenario']}: {scenario.get('overall')}/10 ({scenario.get('status')})")
                    for x in scenario.get("weak_tests", []):
                        lines.append(f"  - `{x['test']}` ({x['category']}) {x['score']}/10")
            lines.append("")
    lines += [
        "## Tester notes",
        "",
        "- Setup difficulty (1-5): ",
        "- Most useful result: ",
        "- Biggest confusing point: ",
        "- Would you use this again? yes / maybe / no",
        "- One feature you would add: ",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a privacy-safe feedback packet from saved CharacterBench JSON.")
    parser.add_argument("--input", default=str(ROOT / "reports" / "latest.json"))
    parser.add_argument("--output", default=str(ROOT / "reports" / "feedback.md"))
    parser.add_argument("--json", default="", help="Optional JSON packet output path.")
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    packet = build_packet(data)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_markdown(packet), encoding="utf-8")
    if args.json:
        json_path = Path(args.json)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Feedback packet: {output}")
    if args.json:
        print(f"Feedback JSON: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
