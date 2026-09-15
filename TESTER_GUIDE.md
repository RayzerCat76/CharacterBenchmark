# CharacterBench alpha tester guide

Target time: about 10 minutes.

## 1. Verify the environment

```bash
python3 characterbench.py doctor
python3 characterbench.py self-test
```

If you use Ollama, verify your model explicitly:

```bash
python3 characterbench.py doctor --model your-model-name
```

## 2. Run the bundled demo

```bash
python3 characterbench.py demo
```

This uses offline fixtures, should not contact a model provider, and writes both `reports/latest.md` and `reports/latest.json`.

## 3. Create a starter character test

```bash
python3 characterbench.py init my-test
```

Edit:

- `my-test/character.json`
- `my-test/tests.json`
- `my-test/models.json`

Then validate them:

```bash
python3 characterbench.py validate \
  --character my-test/character.json \
  --tests my-test/tests.json \
  --models my-test/models.json
```

## 4. Run one real model

For Ollama, either use `run_eval.py` directly or set the model/provider in your config. Keep the first run small; the goal is to see whether the report catches a real character failure.

## 5. Export an HTML report

If you saved JSON results:

```bash
python3 characterbench.py html \
  --input path/to/results.json \
  --output report.html \
  --title "My CharacterBench test"
```

Open `report.html` in a browser.

## 6. Generate a privacy-safe feedback packet

```bash
python3 characterbench.py feedback \
  --input reports/latest.json \
  --output reports/feedback.md
```

For your own real-model result, replace `reports/latest.json` with the JSON file you generated. The packet intentionally excludes prompts, model responses, transcripts, names, model labels, endpoint URLs and local paths. Review any notes you add manually before sharing them.

The most valuable product feedback is one concrete example where CharacterBench either:

1. missed an obvious character failure, or
2. flagged a response that was actually in-character.

Those false negatives/positives are more useful than a general opinion like “the score seems good.”
