#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def score_class(score: float | None) -> str:
    if score is None:
        return "muted"
    if score >= 8:
        return "good"
    if score >= 5:
        return "warn"
    return "bad"


def score_bar(label: str, score: float | None) -> str:
    if score is None:
        return f'<div class="metric"><div class="metric-head"><span>{esc(label)}</span><strong>—</strong></div><div class="track"></div></div>'
    width = max(0.0, min(100.0, score * 10.0))
    cls = score_class(score)
    return (
        '<div class="metric">'
        f'<div class="metric-head"><span>{esc(label)}</span><strong class="{cls}">{score:.1f}</strong></div>'
        f'<div class="track"><div class="fill {cls}" style="width:{width:.1f}%"></div></div>'
        '</div>'
    )


def details_for_tests(tests: list[dict[str, Any]]) -> str:
    weak = [item for item in tests if item.get("score", 10) < 8]
    if not weak:
        return '<p class="quiet">No tests below 8/10.</p>'
    parts: list[str] = []
    for item in weak:
        reasons = ''.join(f'<li>{esc(reason)}</li>' for reason in item.get('reasons', []))
        response = esc(item.get('response', ''))
        parts.append(
            '<details>'
            f'<summary><span>{esc(item.get("test_id", "test"))}</span>'
            f'<span class="pill {score_class(float(item.get("score", 0)))}">{float(item.get("score", 0)):.1f}/10</span></summary>'
            f'<p class="desc">{esc(item.get("description", ""))}</p>'
            f'<pre>{response}</pre>'
            f'<ul>{reasons}</ul>'
            '</details>'
        )
    return ''.join(parts)


def model_card(model: dict[str, Any], scenario_name: str | None = None) -> str:
    label = model.get('label') or model.get('provider') or scenario_name or 'Model'
    status = model.get('status', 'ok')
    if status == 'error':
        return f'<section class="card"><h2>{esc(label)}</h2><p class="bad">Runtime error: {esc(model.get("error", "unknown error"))}</p></section>'
    overall = float(model.get('overall', 0))
    categories = model.get('categories', {})
    metrics = score_bar('Overall', overall) + ''.join(score_bar(name, float(score)) for name, score in categories.items())
    tests = model.get('tests', [])
    return (
        '<section class="card">'
        f'<div class="card-title"><div><p class="eyebrow">{esc(scenario_name or "MODEL")}</p><h2>{esc(label)}</h2></div>'
        f'<div class="big-score {score_class(overall)}">{overall:.1f}</div></div>'
        f'<div class="metrics">{metrics}</div>'
        '<h3>Attention</h3>'
        f'{details_for_tests(tests)}'
        '</section>'
    )


def suite_card(model: dict[str, Any]) -> str:
    label = model.get('label', 'Model')
    overall = model.get('overall')
    runs = model.get('runs', [])
    if overall is None:
        return f'<section class="card"><h2>{esc(label)}</h2><p class="bad">No scenarios completed successfully.</p></section>'
    overall = float(overall)
    metrics = score_bar('Overall', overall)
    for run in runs:
        name = run.get('scenario_id', 'scenario')
        score = run.get('overall') if run.get('status') == 'ok' else None
        metrics += score_bar(name, float(score) if score is not None else None)
    weak_parts = []
    for run in runs:
        if run.get('status') == 'ok':
            weak_parts.append(f'<h4>{esc(run.get("scenario_id", "scenario"))}</h4>{details_for_tests(run.get("tests", []))}')
        else:
            weak_parts.append(f'<h4>{esc(run.get("scenario_id", "scenario"))}</h4><p class="bad">{esc(run.get("error", "runtime error"))}</p>')
    return (
        '<section class="card">'
        f'<div class="card-title"><div><p class="eyebrow">MULTI-PERSONA</p><h2>{esc(label)}</h2></div>'
        f'<div class="big-score {score_class(overall)}">{overall:.1f}</div></div>'
        f'<div class="metrics">{metrics}</div><h3>Attention</h3>{"".join(weak_parts)}'
        '</section>'
    )


def render(data: dict[str, Any], title: str) -> str:
    if 'suite' in data and 'models' in data:
        subtitle = 'Multi-character suite · diagnostic character-consistency scores'
        cards = ''.join(suite_card(model) for model in data.get('models', []))
    elif 'models' in data:
        subtitle = f'Character: {data.get("character", "unknown")} · model comparison'
        cards = ''.join(model_card(model) for model in data.get('models', []))
    else:
        subtitle = f'Character: {data.get("character", "unknown")} · single-model report'
        cards = model_card(data)

    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<style>
:root{{--bg:#07101d;--card:#0c1727;--line:#1d2d44;--text:#eef3f9;--muted:#8fa1ba;--blue:#75a6ef;--green:#71d6a2;--amber:#f0c36e;--red:#ef7f86}}
*{{box-sizing:border-box}}body{{margin:0;background:linear-gradient(180deg,#06101b,#091525);color:var(--text);font:15px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}}
main{{max-width:1080px;margin:auto;padding:56px 24px 80px}}header{{margin-bottom:36px}}.eyebrow{{color:var(--blue);font-size:12px;letter-spacing:.16em;text-transform:uppercase;margin:0 0 8px}}h1{{font:700 42px/1.05 system-ui,sans-serif;margin:0 0 12px}}h2{{font:700 26px/1.1 system-ui,sans-serif;margin:0}}h3{{font:700 17px system-ui,sans-serif;margin:28px 0 12px}}h4{{color:var(--muted);margin:22px 0 8px}}.sub,.quiet,.desc{{color:var(--muted)}}.grid{{display:grid;gap:20px}}.card{{background:rgba(12,23,39,.94);border:1px solid var(--line);border-radius:18px;padding:24px;box-shadow:0 18px 50px rgba(0,0,0,.18)}}.card-title{{display:flex;align-items:flex-start;justify-content:space-between;gap:20px}}.big-score{{font:800 54px/1 system-ui,sans-serif}}.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px;margin-top:24px}}.metric-head{{display:flex;justify-content:space-between;gap:16px;color:var(--muted);margin-bottom:6px}}.track{{height:8px;background:#23334b;border-radius:999px;overflow:hidden}}.fill{{height:100%;border-radius:999px}}.good,.fill.good{{color:var(--green)}}.fill.good{{background:var(--green)}}.warn,.fill.warn{{color:var(--amber)}}.fill.warn{{background:var(--amber)}}.bad,.fill.bad{{color:var(--red)}}.fill.bad{{background:var(--red)}}.muted{{color:var(--muted)}}details{{border-top:1px solid var(--line);padding:12px 0}}summary{{cursor:pointer;display:flex;justify-content:space-between;gap:16px;align-items:center}}.pill{{font-size:12px;border:1px solid currentColor;border-radius:999px;padding:2px 8px}}pre{{white-space:pre-wrap;background:#07111e;border:1px solid var(--line);padding:14px;border-radius:10px;color:#dbe6f3;overflow:auto}}ul{{color:var(--muted);padding-left:20px}}footer{{color:var(--muted);margin-top:28px;font-size:12px}}
</style></head><body><main><header><p class="eyebrow">CharacterBench</p><h1>{esc(title)}</h1><p class="sub">{esc(subtitle)}</p></header><div class="grid">{cards}</div><footer>Generated locally by CharacterBench. Scores are diagnostic signals, not scientific measurements or general model-quality rankings.</footer></main></body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser(description='Render CharacterBench JSON results as a standalone HTML report.')
    parser.add_argument('--input', required=True, help='CharacterBench JSON result file.')
    parser.add_argument('--output', required=True, help='Destination HTML file.')
    parser.add_argument('--title', default='CharacterBench report')
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text(encoding='utf-8'))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(data, args.title), encoding='utf-8')
    print(f'HTML: {output}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
