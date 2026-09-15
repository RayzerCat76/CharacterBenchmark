#!/usr/bin/env python3
from __future__ import annotations

import json

from feedback_packet import build_packet, error_class, render_markdown
from run_eval import ROOT, build_summary, evaluate, load_json, score_criteria, term_present

ASTER_EXPECTED = {
    "synthetic_good.json": 10.0,
    "synthetic_generic.json": 4.3,
    "synthetic_drift.json": 8.3,
}

TAVI_EXPECTED = {
    "tavi_good.json": 10.0,
    "tavi_generic.json": 4.7,
}


def main() -> int:
    suites = [
        ("aster", ROOT / "characters" / "demo.json", ROOT / "tests" / "tests.json", ASTER_EXPECTED),
        ("tavi", ROOT / "characters" / "tavi.json", ROOT / "tests" / "tavi_tests.json", TAVI_EXPECTED),
    ]

    for suite_name, character_path, tests_path, expected_map in suites:
        character = load_json(character_path)
        tests = load_json(tests_path)
        for filename, expected in expected_map.items():
            results, label = evaluate(
                character,
                tests,
                provider="fixture",
                fixture_path=ROOT / "fixtures" / filename,
            )
            summary = build_summary(character, results, label)
            actual = summary["overall"]
            if actual != expected:
                raise AssertionError(
                    f"{suite_name}/{filename}: expected {expected:.1f}, got {actual:.1f}"
                )
            print(f"PASS {suite_name}/{filename:<23} {actual:.1f}/10")

    if not term_present("I don’t know.", "don't"):
        raise AssertionError("Unicode apostrophes must normalize during text matching")
    if not term_present('“No.”', "no"):
        raise AssertionError("Unicode quotes must not break token matching")
    print("PASS unicode-normalized matching")

    one_fail, _ = score_criteria([(False, "failure")])
    one_fail_plus_pass, _ = score_criteria([(False, "failure"), (True, "extra pass")])
    if one_fail_plus_pass != one_fail:
        raise AssertionError(
            "Adding a passing criterion must not improve an already-failed score"
        )
    print(f"PASS monotonic scoring             {one_fail:.1f}/10")

    fake_email = "secret." + "user" + chr(64) + "example." + "com"
    fake_home = "/" + "Users" + "/private" + "person/model"
    fake_url = "http://" + "private." + "example.test"
    fake_alt_email = "x" + chr(64) + "y.example"
    private_payload = {
        "character": "PRIV" + "ATE_PERSON_NAME",
        "provider": f"{fake_email} {fake_home} {fake_url}",
        "overall": 4.2,
        "categories": {"PRIV" + "ATE_CATEGORY_NAME": 1.0, "Memory": 7.0},
        "tests": [
            {
                "test_id": "PRIV" + "ATE_TEST_NAME",
                "category": "PRIV" + "ATE_CATEGORY_NAME",
                "score": 2.0,
                "response": f"SECRET RESPONSE {fake_home} {fake_alt_email}",
                "responses": ["SECRET TRANSCRIPT"],
            }
        ],
    }
    safe_packet = json.dumps(build_packet(private_payload), ensure_ascii=False)
    forbidden = [
        "PRIV" + "ATE_", "private" + "person", "secret." + "user", "example." + "com",
        "/" + "Users" + "/", "SECRET RESPONSE", "SECRET TRANSCRIPT", "private." + "example",
    ]
    leaked = [value for value in forbidden if value.casefold() in safe_packet.casefold()]
    if leaked:
        raise AssertionError(f"Feedback packet leaked private input: {leaked}")
    print("PASS privacy-safe feedback packet")

    if error_class("Could not reach http://provider.invalid from a client") != "provider-unreachable":
        raise AssertionError("Reachability errors must not be reduced to generic HTTP errors")
    error_packet = {
        "characterbench_version": "test",
        "result_type": "comparison",
        "models": [{"model": "model_1", "status": "error", "overall": None, "error_class": "timeout", "weak_tests": []}],
    }
    error_markdown = render_markdown(error_packet)
    if "None/10" in error_markdown or "ERROR" not in error_markdown or "timeout" not in error_markdown:
        raise AssertionError("Feedback Markdown must render runtime failures safely")
    print("PASS feedback runtime-error rendering")

    print("All CharacterBench self-tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
