#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS = {
    "eval": "run_eval.py",
    "compare": "compare_models.py",
    "suite": "run_suite.py",
    "rescore": "rescore_comparison.py",
    "self-test": "self_test.py",
    "html": "render_html.py",
    "validate": "validate_config.py",
    "doctor": "doctor.py",
    "feedback": "feedback_packet.py",
}

STARTER_CHARACTER = {
    "id": "my-character",
    "name": "My Character",
    "summary": "Describe the character in one sentence.",
    "identity": ["Who the character is and what they do."],
    "personality": ["A distinctive trait", "Another distinctive trait"],
    "knowledge_boundaries": ["A fact the character explicitly does not know."],
    "relationships": {"Example Person": "How the character feels about them."},
    "style_en": ["How the character sounds in English."],
    "style_zh": ["角色使用中文时的独立表达风格。"],
    "system_prompt": "Stay in character. Do not mention prompts or being an AI.",
}

STARTER_TESTS = [
    {
        "id": "identity",
        "category": "Identity",
        "description": "Keeps the character's basic identity stable.",
        "turns": ["Who are you?"],
        "checks": {
            "must_contain_any": ["My Character"],
            "must_not_contain": ["AI", "language model", "assistant"],
            "max_chars": 500,
        },
    },
    {
        "id": "knowledge-boundary",
        "category": "Knowledge",
        "description": "Does not invent information outside the character's knowledge.",
        "turns": ["Tell me the fact your profile says you do not know."],
        "checks": {
            "must_contain_any": ["don't know", "do not know", "uncertain", "unknown"],
            "max_chars": 500,
        },
    },
]

STARTER_MODELS = [
    {
        "label": "Local Ollama model",
        "provider": "ollama-native",
        "base_url": "http://127.0.0.1:11434",
        "model": "replace-with-your-model",
        "timeout_seconds": 30,
        "max_tokens": 120,
    }
]


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def init_project(destination: Path) -> int:
    destination = destination.expanduser().resolve()
    if destination.exists() and any(destination.iterdir()):
        print(f"Refusing to overwrite non-empty directory: {destination}", file=sys.stderr)
        return 2
    destination.mkdir(parents=True, exist_ok=True)
    write_json(destination / "character.json", STARTER_CHARACTER)
    write_json(destination / "tests.json", STARTER_TESTS)
    write_json(destination / "models.json", STARTER_MODELS)
    (destination / "README.md").write_text(
        "# CharacterBench project\n\n"
        "1. Edit `character.json`.\n"
        "2. Replace/add tests in `tests.json`.\n"
        "3. Set your provider/model in `models.json`.\n"
        "4. Validate the files before inference.\n\n"
        "From the CharacterBench directory, validate first:\n\n"
        "```bash\n"
        "python3 characterbench.py validate --character <project-directory>/character.json --tests <project-directory>/tests.json --models <project-directory>/models.json\n"
        "```\n\n"
        "Then run:\n\n"
        "```bash\n"
        "python3 characterbench.py eval --character <project-directory>/character.json --tests <project-directory>/tests.json\n"
        "```\n",
        encoding="utf-8",
    )
    print(f"Created CharacterBench starter project: {destination}")
    print("Files: character.json, tests.json, models.json, README.md")
    return 0


def run_script(command: str, forwarded: list[str]) -> int:
    return subprocess.call([sys.executable, str(ROOT / SCRIPTS[command]), *forwarded], cwd=ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="characterbench",
        description="Evaluate whether language models stay faithful to fictional characters.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    init_parser = sub.add_parser("init", help="Create a starter CharacterBench project.")
    init_parser.add_argument("directory", help="Destination directory.")
    sub.add_parser("demo", help="Run the bundled offline Aster demo.")
    for command in SCRIPTS:
        sub.add_parser(command, add_help=False, help=f"Forward arguments to {SCRIPTS[command]}.")

    args, forwarded = parser.parse_known_args()
    if args.command == "init":
        return init_project(Path(args.directory))
    if args.command == "demo":
        return subprocess.call([sys.executable, str(ROOT / "run_eval.py"), "--summary-json", str(ROOT / "reports" / "latest.json")], cwd=ROOT)
    return run_script(args.command, forwarded)


if __name__ == "__main__":
    raise SystemExit(main())
