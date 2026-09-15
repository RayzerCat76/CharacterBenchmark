#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def status(kind: str, message: str) -> None:
    print(f"{kind:<5} {message}")


def fetch_ollama(url: str, timeout: float) -> list[str] | None:
    endpoint = url.rstrip('/') + '/api/tags'
    try:
        with urllib.request.urlopen(endpoint, timeout=timeout) as response:
            data = json.loads(response.read().decode('utf-8'))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None
    models = []
    for item in data.get('models', []):
        name = item.get('name') or item.get('model')
        if isinstance(name, str):
            models.append(name)
    return models


def main() -> int:
    parser = argparse.ArgumentParser(description='Diagnose a CharacterBench environment without running a benchmark.')
    parser.add_argument('--ollama-url', default='http://127.0.0.1:11434')
    parser.add_argument('--model', default='')
    parser.add_argument('--timeout', type=float, default=3.0)
    args = parser.parse_args()

    failed = False
    version = sys.version_info
    if version >= (3, 10):
        status('PASS', f'Python {version.major}.{version.minor}.{version.micro}')
    else:
        status('FAIL', f'Python {version.major}.{version.minor}.{version.micro}; Python 3.10+ recommended')
        failed = True

    required = ['run_eval.py', 'compare_models.py', 'run_suite.py', 'render_html.py', 'validate_config.py']
    missing = [name for name in required if not (ROOT / name).is_file()]
    if missing:
        status('FAIL', f'missing CharacterBench files: {", ".join(missing)}')
        failed = True
    else:
        status('PASS', 'CharacterBench core files present')

    try:
        probe = ROOT / '.doctor-write-test'
        probe.write_text('ok', encoding='utf-8')
        probe.unlink()
        status('PASS', 'working directory writable')
    except OSError as exc:
        status('WARN', f'working directory is not writable: {exc}')

    models = fetch_ollama(args.ollama_url, args.timeout)
    if models is None:
        status('WARN', f'Ollama not reachable at {args.ollama_url}; fixture/OpenAI-compatible modes can still work')
        if args.model:
            status('FAIL', f'cannot verify requested Ollama model: {args.model}')
            failed = True
    else:
        status('PASS', f'Ollama reachable ({len(models)} model(s) installed)')
        if args.model:
            if args.model in models:
                status('PASS', f'Ollama model installed: {args.model}')
            else:
                status('FAIL', f'Ollama model not installed: {args.model}')
                if models:
                    status('INFO', 'installed: ' + ', '.join(models[:8]) + (' …' if len(models) > 8 else ''))
                failed = True

    status('INFO', 'CharacterBench sends no telemetry; provider requests occur only when you run live model tests')
    return 2 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
