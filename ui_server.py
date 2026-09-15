#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import threading
import urllib.error
import urllib.request
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from run_eval import build_summary, evaluate, load_json
from validate_config import validate_character, validate_tests

ROOT = Path(__file__).resolve().parent
UI_ROOT = ROOT / "ui"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

SUITES = {
    "aster": {
        "name": "Aster Vale",
        "description": "Calm, evidence-driven archivist. Good for identity, knowledge-boundary and memory checks.",
        "character": ROOT / "characters" / "demo.json",
        "tests": ROOT / "tests" / "tests.json",
        "fixture": ROOT / "fixtures" / "synthetic_generic.json",
    },
    "tavi": {
        "name": "Tavi Rook",
        "description": "Impulsive, sarcastic salvage pilot. Harder personality and style stress test.",
        "character": ROOT / "characters" / "tavi.json",
        "tests": ROOT / "tests" / "tavi_tests.json",
        "fixture": ROOT / "fixtures" / "tavi_generic.json",
    },
}

def ollama_models(base_url: str = "http://127.0.0.1:11434", timeout: float = 2.0) -> list[str]:
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/api/tags", timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return []
    models: list[str] = []
    for item in data.get("models", []):
        name = item.get("name") or item.get("model")
        if isinstance(name, str):
            models.append(name)
    return models


def state_payload() -> dict[str, Any]:
    models = ollama_models()
    return {
        "version": VERSION,
        "ollama_reachable": bool(models),
        "models": models,
        "suites": [
            {"id": suite_id, "name": cfg["name"], "description": cfg["description"]}
            for suite_id, cfg in SUITES.items()
        ],
    }


def run_payload(payload: dict[str, Any]) -> dict[str, Any]:
    suite_id = str(payload.get("suite", "aster"))
    if suite_id not in SUITES:
        raise ValueError("Unknown suite")
    cfg = SUITES[suite_id]
    provider = str(payload.get("provider", "fixture"))
    if provider not in {"fixture", "ollama-native"}:
        raise ValueError("UI currently supports offline demo and native Ollama runs")

    custom_character = payload.get("custom_character")
    custom_tests = payload.get("custom_tests")
    if custom_character is not None or custom_tests is not None:
        if custom_character is None or custom_tests is None:
            raise ValueError("Custom mode requires both character and tests JSON")
        if provider != "ollama-native":
            raise ValueError("Custom JSON runs currently require a local Ollama model")
        validate_character(custom_character, "character")
        validate_tests(custom_tests, "tests")
        character, tests = custom_character, custom_tests
        suite_id = "custom"
    else:
        character = load_json(cfg["character"])
        tests = load_json(cfg["tests"])
    model = str(payload.get("model", "")).strip()
    if provider == "ollama-native" and not model:
        raise ValueError("Choose an installed Ollama model")

    results, provider_label = evaluate(
        character,
        tests,
        provider=provider,
        fixture_path=cfg["fixture"] if provider == "fixture" and suite_id != "custom" else None,
        base_url="http://127.0.0.1:11434",
        model=model or "offline-fixture",
        max_tokens=120,
        request_timeout=30.0,
    )
    summary = build_summary(character, results, provider_label)
    summary["suite_id"] = suite_id
    return summary

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(UI_ROOT), **kwargs)

    def send_json(self, status: int, value: Any) -> None:
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/api/state":
            self.send_json(200, state_payload())
            return
        if self.path == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:
        if self.path != "/api/run":
            self.send_json(404, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 100_000:
                raise ValueError("Invalid request size")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Request must be a JSON object")
            result = run_payload(payload)
        except (ValueError, RuntimeError, json.JSONDecodeError) as exc:
            self.send_json(400, {"error": str(exc)})
            return
        self.send_json(200, result)

    def log_message(self, format: str, *args: Any) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local CharacterBench browser UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if args.host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("CharacterBench UI binds to localhost only in this alpha.")

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"CharacterBench UI: {url}")
    print("Localhost only. No telemetry. Press Ctrl+C to stop.")
    if not args.no_browser:
        threading.Timer(0.25, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
