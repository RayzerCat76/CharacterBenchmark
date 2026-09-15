# CharacterBench configuration reference

CharacterBench uses plain JSON. The validator catches malformed structures before any model requests are sent.

## Character file

Required:

```json
{
  "name": "My Character"
}
```

Common optional fields:

- `id`: stable identifier
- `summary`: short description
- `identity`: list of identity facts
- `personality`: list of behavioural traits
- `knowledge_boundaries`: facts the character does not know or should not invent
- `relationships`: object mapping names to relationship descriptions
- `style_en`: English-language style notes
- `style_zh`: Chinese-language style notes
- `system_prompt`: additional character instruction

## Test file

A test file is a non-empty JSON list. Test IDs must be unique.

```json
[
  {
    "id": "identity",
    "category": "Identity",
    "description": "Keeps identity stable.",
    "turns": ["Who are you?"],
    "checks": {
      "must_contain_any": ["archivist", "Aster"],
      "must_not_contain": ["language model"],
      "max_chars": 500,
      "forbid_cjk": true
    }
  }
]
```

## Final-response checks

- `must_contain_any`: at least one listed phrase must appear.
- `must_contain_all`: every listed phrase must appear.
- `must_contain_groups`: for every group, at least one phrase in that group must appear.
- `must_not_contain`: none of the listed phrases may appear.
- `max_chars`: maximum response length in characters.
- `require_cjk`: response must contain CJK text.
- `forbid_cjk`: response must not contain CJK text.

`require_cjk` and `forbid_cjk` cannot both be true.

## Conversation-wide checks

Long/multi-turn tests may also include `conversation_checks`:

- `must_contain_any`
- `must_contain_groups`
- `must_not_contain`
- `max_identical_responses`: maximum number of identical assistant turns allowed.

These checks inspect the full assistant transcript, not only the final turn.

## Model configuration

Supported providers:

- `fixture`
- `ollama-native`
- `openai-compatible`

Example:

```json
[
  {
    "label": "Local model",
    "provider": "ollama-native",
    "base_url": "http://127.0.0.1:11434",
    "model": "qwen3:1.7b",
    "timeout_seconds": 30,
    "max_tokens": 120
  }
]
```

API keys for OpenAI-compatible providers are read from environment variables; do not put keys in committed JSON.

## Validation

```bash
python3 characterbench.py validate \
  --character path/to/character.json \
  --tests path/to/tests.json \
  --models path/to/models.json
```
