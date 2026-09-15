#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from run_eval import ROOT, build_summary, evaluate, load_json


def resolve(base: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


def average(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def aggregate_model(label: str, runs: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [run for run in runs if run["status"] == "ok"]
    categories: dict[str, list[float]] = {}
    for run in ok:
        for category, score in run["categories"].items():
            categories.setdefault(category, []).append(float(score))
    if not ok:
        status = "error"
    elif len(ok) != len(runs):
        status = "partial"
    else:
        status = "ok"
    return {
        "label": label,
        "status": status,
        "overall": average([float(run["overall"]) for run in ok]),
        "categories": {key: average(values) for key, values in categories.items()},
        "scenarios": runs,
    }


def render_report(models: list[dict[str, Any]], scenario_ids: list[str]) -> str:
    lines = [
        "# CharacterBench multi-character suite",
        "",
        "Scores aggregate across original CharacterBench test characters.",
        "",
        "| Model | Overall | " + " | ".join(scenario_ids) + " | Status |",
        "|---|---:|" + "|".join("---:" for _ in scenario_ids) + "|---|",
    ]
    for model in sorted(models, key=lambda x: x["overall"] if x["overall"] is not None else -1, reverse=True):
        by_id = {run["scenario_id"]: run for run in model["scenarios"]}
        cells = []
        for scenario_id in scenario_ids:
            run = by_id.get(scenario_id)
            if not run or run["status"] != "ok":
                cells.append("ERR")
            else:
                cells.append(f"{run['overall']:.1f}")
        overall = "—" if model["overall"] is None else f"**{model['overall']:.1f}**"
        lines.append(f"| {model['label']} | {overall} | " + " | ".join(cells) + f" | {model['status']} |")

    lines += ["", "## Failures and weak spots", ""]
    for model in models:
        lines += [f"### {model['label']}", ""]
        emitted = False
        for run in model["scenarios"]:
            if run["status"] != "ok":
                lines.append(f"- **{run['scenario_id']}** runtime error: {run['error']}")
                emitted = True
                continue
            weak = [test for test in run["tests"] if test["score"] < 8]
            for test in weak:
                lines.append(f"- **{run['scenario_id']} / {test['test_id']}** — {test['score']}/10")
                emitted = True
        if not emitted:
            lines.append("- No tests below 8/10.")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CharacterBench across multiple characters and models.")
    parser.add_argument("--suite", default=str(ROOT / "suites" / "core.json"))
    parser.add_argument("--config", default=str(ROOT / "suite_models.example.json"))
    parser.add_argument("--report", default=str(ROOT / "reports" / "suite.md"))
    parser.add_argument("--json", default=str(ROOT / "reports" / "suite.json"))
    args = parser.parse_args()

    suite_path = Path(args.suite).resolve()
    config_path = Path(args.config).resolve()
    suite = load_json(suite_path)
    configs = load_json(config_path)
    if not isinstance(suite, list) or not suite:
        print("Suite must be a non-empty JSON list.", file=sys.stderr)
        return 2
    if not isinstance(configs, list) or not configs:
        print("Config must be a non-empty JSON list.", file=sys.stderr)
        return 2

    suite_base = suite_path.parent
    config_base = config_path.parent
    model_outputs: list[dict[str, Any]] = []

    for config in configs:
        label = config.get("label") or config.get("model") or "unnamed"
        provider = config.get("provider", "openai-compatible")
        model = config.get("model", label)
        api_key = os.getenv(config.get("api_key_env", "CHARACTERBENCH_API_KEY"), "local")
        base_url = config.get("base_url", os.getenv("CHARACTERBENCH_BASE_URL", "http://localhost:11434/v1"))
        max_tokens = int(config.get("max_tokens", 120))
        request_timeout = float(config.get("request_timeout", 60.0))
        runs: list[dict[str, Any]] = []
        print(f"\n## {label}")

        for scenario in suite:
            scenario_id = scenario["id"]
            character_path = resolve(suite_base, scenario["character"])
            tests_path = resolve(suite_base, scenario["tests"])
            character = load_json(character_path)
            tests = load_json(tests_path)
            fixture_value = (config.get("fixtures") or {}).get(scenario_id)
            if not fixture_value and len(suite) == 1:
                fixture_value = config.get("fixture")
            fixture_path = resolve(config_base, fixture_value)
            print(f"  {scenario_id}...", end="", flush=True)
            try:
                results, provider_label = evaluate(
                    character,
                    tests,
                    provider=provider,
                    fixture_path=fixture_path,
                    base_url=base_url,
                    api_key=api_key,
                    model=model,
                    max_tokens=max_tokens,
                    request_timeout=request_timeout,
                )
                summary = build_summary(character, results, provider_label)
                summary.update({"scenario_id": scenario_id, "status": "ok"})
                runs.append(summary)
                print(f" {summary['overall']:.1f}/10")
            except (ValueError, RuntimeError) as exc:
                runs.append({
                    "scenario_id": scenario_id,
                    "status": "error",
                    "error": str(exc),
                    "overall": None,
                    "categories": {},
                    "tests": [],
                })
                print(f" ERROR: {exc}")

        model_outputs.append(aggregate_model(label, runs))

    report_path = Path(args.report)
    json_path = Path(args.json)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    scenario_ids = [scenario["id"] for scenario in suite]
    report_path.write_text(render_report(model_outputs, scenario_ids), encoding="utf-8")
    json_path.write_text(json.dumps({"suite": scenario_ids, "models": model_outputs}, ensure_ascii=False, indent=2), encoding="utf-8")

    ranked = [model for model in model_outputs if model["overall"] is not None]
    if ranked:
        best = max(ranked, key=lambda item: item["overall"])
        print(f"\nBest suite score: {best['label']} ({best['overall']:.1f}/10)")
    print(f"Report: {report_path}")
    print(f"JSON: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
