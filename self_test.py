#!/usr/bin/env python3
from __future__ import annotations

import base64
import binascii
import json
import struct
import zlib

from feedback_packet import build_packet, error_class, render_markdown
from card_import import import_card_bytes, import_card_object
from run_eval import ROOT, build_summary, evaluate, load_json, score_criteria, term_present
from ui_server import run_payload
from validate_config import validate_character, validate_tests

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

    ui_demo = run_payload({"suite": "aster", "provider": "fixture"})
    if ui_demo.get("overall") != 4.3 or ui_demo.get("suite_id") != "aster":
        raise AssertionError("Local UI fixture path must reproduce the Aster generic regression fixture")
    try:
        run_payload({
            "suite": "aster",
            "provider": "fixture",
            "custom_character": {"name": "X"},
            "custom_tests": [],
        })
    except ValueError:
        pass
    else:
        raise AssertionError("Custom UI input must not run through fixture mode")
    print("PASS local UI regression path")

    sample_card = {
        "spec": "chara_card_v2",
        "data": {
            "name": "Mira Vale",
            "description": "A cautious archivist aboard Meridian Station.",
            "personality": "Careful, skeptical, dry-witted.",
            "scenario": "Meridian Station during a blackout.",
            "mes_example": "{{char}}: I prefer evidence to optimism.",
            "character_book": {"entries": [{"keys": ["Vault Nine"], "content": "Vault Nine is sealed and its contents are unknown."}]},
        },
    }
    imported = import_card_object(sample_card)
    if imported["preview"]["name"] != "Mira Vale" or imported["preview"]["test_count"] < 5:
        raise AssertionError("Character Card import must generate a usable starter suite")
    validate_character(imported["character"], "imported character")
    validate_tests(imported["tests"], "generated tests")
    raw_card = json.dumps(sample_card).encode("utf-8")
    if import_card_bytes("mira.json", raw_card)["source"] != "json":
        raise AssertionError("JSON character-card import failed")

    def png_chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", binascii.crc32(kind + body) & 0xffffffff)
    png = b"\x89PNG\r\n\x1a\n"
    png += png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    png += png_chunk(b"tEXt", b"chara\0" + base64.b64encode(raw_card))
    png += png_chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00")) + png_chunk(b"IEND", b"")
    if import_card_bytes("mira.png", png)["source"] != "png":
        raise AssertionError("PNG character-card import failed")
    print("PASS character-card JSON/PNG import")

    print("All CharacterBench self-tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
