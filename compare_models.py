#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from run_eval import ROOT, build_summary, evaluate, load_json, render_report


def resolve_path(base: Path, value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else (base / path)


def render_comparison(summaries: list[dict[str, Any]]) -> str:
    successful = [item for item in summaries if item.get("status") == "ok"]
    failed = [item for item in summaries if item.get("status") == "error"]
    categories: list[str] = []
    for summary in successful:
        for category in summary["categories"]:
            if category not in categories:
                categories.append(category)

    lines = ["# CharacterBench comparison", ""]
    fixture_labels = [
        item.get("label", "unnamed")
        for item in summaries
        if item.get("config", {}).get("provider") == "fixture"
    ]
    if fixture_labels:
        lines += [
            "> Fixture-backed profiles are validation harnesses, not real model benchmarks.",
            "",
        ]
    lines += [
        "| Model | Overall | " + " | ".join(categories) + " |",
        "|---|---:|" + "|".join("---:" for _ in categories) + "|",
    ]

    for summary in sorted(successful, key=lambda item: item["overall"], reverse=True):
        category_cells = [
            f"{summary['categories'].get(category, 0):.1f}"
            if category in summary["categories"]
            else "—"
            for category in categories
        ]
        lines.append(
            f"| {summary['label']} | **{summary['overall']:.1f}** | "
            + " | ".join(category_cells)
            + " |"
        )

    if failed:
        lines += ["", "## Runtime errors", ""]
        for summary in failed:
            lines.append(f"- **{summary['label']}** — {summary['error']}")

    lines += ["", "## Attention by model", ""]
    for summary in successful:
        failures = [item for item in summary["tests"] if item["score"] < 8]
        lines.append(f"### {summary['label']}")
        lines.append("")
        if not failures:
            lines.append("- No tests below 8/10.")
        else:
            for item in failures:
                lines.append(
                    f"- `{item['test_id']}` ({item['category']}): "
                    f"{item['score']}/10"
                )
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the same CharacterBench suite across multiple model profiles."
    )
    parser.add_argument(
        "--config",
        default=str(ROOT / "models.example.json"),
        help="JSON list of model/provider configurations.",
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
        "--report",
        default=str(ROOT / "reports" / "comparison.md"),
    )
    parser.add_argument(
        "--json",
        default=str(ROOT / "reports" / "comparison.json"),
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    config_base = config_path.parent
    configs = load_json(config_path)
    character = load_json(Path(args.character))
    tests = load_json(Path(args.tests))

    if not isinstance(configs, list) or not configs:
        print("Config must be a non-empty JSON list.", file=sys.stderr)
        return 2

    summaries: list[dict[str, Any]] = []
    reports_dir = Path(args.report).parent
    reports_dir.mkdir(parents=True, exist_ok=True)

    for config in configs:
        label = config.get("label") or config.get("model") or "unnamed"
        provider = config.get("provider", "openai-compatible")
        fixture_path = resolve_path(config_base, config.get("fixture"))
        base_url = config.get(
            "base_url",
            os.getenv("CHARACTERBENCH_BASE_URL", "http://localhost:11434/v1"),
        )
        model = config.get("model", label)
        api_key_env = config.get("api_key_env", "CHARACTERBENCH_API_KEY")
        api_key = os.getenv(api_key_env, "local")
        max_tokens = int(config.get("max_tokens", 120))
        request_timeout = float(config.get("request_timeout", 60.0))

        print(f"\n== {label} ==")
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
        except (ValueError, RuntimeError) as exc:
            error_message = str(exc)
            print(f"{label}: ERROR: {error_message}", file=sys.stderr)
            summaries.append({
                "label": label,
                "status": "error",
                "error": error_message,
                "overall": None,
                "categories": {},
                "tests": [],
                "config": {
                    "provider": provider,
                    "model": model,
                    "base_url": base_url if provider != "fixture" else None,
                    "fixture": str(fixture_path) if fixture_path else None,
                    "max_tokens": max_tokens,
                    "request_timeout": request_timeout,
                },
            })
            continue

        for result in results:
            print(f"{result.test_id:<16} {result.score:>4.1f}/10")

        summary = build_summary(character, results, provider_label)
        summary["label"] = label
        summary["status"] = "ok"
        summary["config"] = {
            "provider": provider,
            "model": model,
            "base_url": base_url if provider == "openai-compatible" else None,
            "fixture": str(fixture_path) if fixture_path else None,
            "max_tokens": max_tokens,
            "request_timeout": request_timeout,
        }
        summaries.append(summary)

        safe_name = "".join(
            ch.lower() if ch.isalnum() else "-"
            for ch in label
        ).strip("-")
        model_report = reports_dir / f"{safe_name or 'model'}.md"
        model_report.write_text(render_report(summary), encoding="utf-8")

    Path(args.report).write_text(render_comparison(summaries), encoding="utf-8")
    Path(args.json).write_text(
        json.dumps(
            {
                "character": character["name"],
                "models": summaries,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    successful = [item for item in summaries if item.get("status") == "ok"]
    if successful:
        best = max(successful, key=lambda item: item["overall"])
        print(f"\nBest overall: {best['label']} ({best['overall']:.1f}/10)")
    else:
        print("\nNo models completed successfully.")
    print(f"Comparison: {args.report}")
    print(f"JSON: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
