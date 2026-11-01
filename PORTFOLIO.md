# CharacterBench — portfolio guide

**What it is:** a local regression tester for AI characters. It reruns controlled conversations after a model, prompt, memory, or character-card change and highlights shifts in personality, knowledge boundaries, relationships, and memory. Scores are diagnostic signals, not a model leaderboard.

## Try it in five minutes

1. Download the [v0.2.2-alpha release](https://github.com/RayzerCat76/CharacterBenchmark/releases/tag/v0.2.2-alpha) and unzip it.
2. Run `python3 characterbench.py demo` for a model-free example. Inspect `reports/latest.md` and `reports/latest.json`.
3. Run `python3 characterbench.py ui` to open the local interface. To test your own character, import a standard Character Card JSON or PNG, review the starter checks, select an installed Ollama model, and run. Save that result as a baseline, change one input, rerun, and inspect the comparison.

The local UI and example screenshot are documented in the main [README](README.md). The [website](https://characterbench-alpha.netlify.app/) points to the public alpha package.

## Why I made it and how it changed

I was changing character cards and models but could not reliably tell whether a character's behavior had improved or quietly regressed. The initial prototype used fixed, repeatable conversations to expose failures such as accepting false memories or inventing lore. The current alpha adds card import, starter checks, a local UI, saved baselines, test fingerprints, reports, and comparison. Fingerprints prevent changed tests from being presented as directly comparable runs.

The [build-process map](docs/BUILD_PROCESS.md) links specific public revisions to those decisions and to the current code.

## Current stage

The v0.2.2-alpha package and its local demo, UI/API workflows, Ollama runs, reports, and comparisons have been exercised. This establishes a working prototype, not broad external validation. I am still seeking real character-card cases that reveal false positives, missed failures, or confusing onboarding.

## Contributions and sources

Ray Liu defined the problem, product workflow, test criteria, and release decisions, and reviewed the resulting behavior. OpenAI Codex assisted with code, tests, debugging, UI text, and documentation. There were no other human collaborators on CharacterBench.

Character Card files use a third-party community format; cards imported by users are not included in this repository. Ollama and third-party language models provide inference during live local tests and are not my models. The optional [SillyTavern extension](https://github.com/RayzerCat76/CharacterBench-SillyTavern) integrates with the third-party SillyTavern application. Bundled example characters and benchmark fixtures are original synthetic examples, not evidence of external model quality.
