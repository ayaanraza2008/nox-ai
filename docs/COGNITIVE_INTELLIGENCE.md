# NOX Cognitive Intelligence

The Cognitive Intelligence workspace uses the existing configured NOX chat providers; it does not add a paid model dependency or a separate provider key. Available modes are behavioral hypotheses, pattern review, cognitive-bias review, cross-disciplinary synthesis, structured thinking, optional personality reflection, and practical Stoic exercises.

## API

`POST /api/cognitive/analyze`

Request JSON: `{"mode":"behavior","content":"...","language":"auto"}`

Modes: `behavior`, `patterns`, `bias`, `omnivore`, `thinking`, `personality`, `stoicism`. Languages: `auto`, `en`, `hi`, `hinglish`, `ur`.

The endpoint processes only the text supplied in the request; it does not read conversation history, account records, or save a long-term behavioral profile. It uses the existing configured provider. If no provider is configured or all providers fail, it returns a clear service error rather than pretending to analyze the input.

The local pattern helper reports exact repeated tokens across explicitly supplied samples. It is descriptive, not causal or psychological proof. LLM-generated interpretation depends on the configured provider and should be treated as hypotheses, not diagnosis or certainty.

## Limits

- No clinical diagnosis or definitive mind-reading.
- No automatic long-term personality/behavior profile.
- Provider-backed research/citations are only as available as the existing provider and tools; the endpoint does not claim it independently searched the web.
- Personality prompts are informal reflection, not validated assessment scores.
