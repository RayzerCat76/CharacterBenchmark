#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from compare_models import render_comparison
from run_eval import TestResult, build_summary, load_json, score_test


def main() -> int:
    parser = argparse.ArgumentParser(description="Rescore saved CharacterBench transcripts with current checks.")
    parser.add_argument("--input", required=True, help="Existing comparison JSON with saved transcripts.")
    parser.add_argument("--character", required=True)
    parser.add_argument("--tests", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report")
    args = parser.parse_args()

    source = load_json(Path(args.input))
    character = load_json(Path(args.character))
    definitions = {item["id"]: item for item in load_json(Path(args.tests))}
    rescored = []

    for model in source.get("models", []):
        if model.get("status") != "ok":
            rescored.append(model)
            continue
        results = []
        for old in model.get("tests", []):
            definition = definitions.get(old["test_id"])
            if not definition:
                raise ValueError(f"Missing current test definition for {old['test_id']}")
            responses = old.get("responses") or [old.get("response", "")]
            score, reasons = score_test(
                responses,
                definition.get("checks", {}),
                definition.get("conversation_checks", {}),
            )
            results.append(TestResult(
                test_id=old["test_id"],
                category=definition["category"],
                description=definition["description"],
                score=score,
                response=responses[-1],
                responses=responses,
                reasons=reasons,
            ))
        summary = build_summary(character, results, model.get("provider", "saved transcript"))
        summary["label"] = model.get("label", "unnamed")
        summary["status"] = "ok"
        summary["config"] = model.get("config", {})
        summary["rescored_from"] = str(Path(args.input))
        rescored.append(summary)

    payload = {"character": character["name"], "models": rescored}
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.report:
        Path(args.report).write_text(render_comparison(rescored), encoding="utf-8")
    for model in rescored:
        if model.get("status") == "ok":
            print(f"{model['label']}: {model['overall']:.1f}/10")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
