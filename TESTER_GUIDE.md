# CharacterBench 0.2 alpha tester guide

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

## 2. Open the local UI

```bash
python3 characterbench.py ui
```

The page binds to `127.0.0.1` and CharacterBench adds no telemetry.
## 3. Test your own character

Choose **Test my character** and drop a standard Character Card JSON or PNG. Review the starter checks, turn off anything that does not fit, and add one custom check if something important is missing.

Choose an installed Ollama model and run the suite. The most useful outcome is not a high score; it is one failure you recognize as a real character regression.

## 4. Save a baseline and rerun

Save the first result as a local baseline. Change one thing -- model, prompt, memory system, or character card -- and run the same checks again.

CharacterBench highlights meaningful regressions and improvements. If the test set or a test definition changed, it avoids presenting the overall scores as directly comparable.

## 5. Optional zero-model demo

```bash
python3 characterbench.py demo
```

This uses offline fixtures and writes `reports/latest.md` and `reports/latest.json`.
## 6. Send useful feedback

The best feedback is one concrete example where CharacterBench either missed an obvious character failure or flagged a response that was actually in-character.

For a saved JSON result, you can generate a privacy-safe feedback packet:

```bash
python3 characterbench.py feedback \
  --input reports/latest.json \
  --output reports/feedback.md
```

The default packet excludes prompts, responses, transcripts, character names, model labels, endpoint URLs, and local paths. Review any notes you add manually before sharing them.
