# NOX Cognitive Intelligence

The Cognitive Intelligence workspace uses the existing configured NOX chat providers; it does not add a paid model dependency or a separate provider key. Available modes are behavioral hypotheses, pattern review, cognitive-bias review, cross-disciplinary synthesis, structured thinking, optional personality reflection, and practical Stoic exercises.

## API

`POST /api/cognitive/analyze`

Request JSON: `{"mode":"behavior","content":"...","language":"auto","use_knowledge":false}`

Modes: `behavior`, `patterns`, `bias`, `omnivore`, `thinking`, `personality`, `stoicism`. Languages: `auto`, `en`, `hi`, `hinglish`, `ur`.

By default, the endpoint processes only the text supplied in the request; it does not read conversation history or save a long-term behavioral profile. If `use_knowledge` is explicitly `true`, it resolves the current browser/account session and searches only that owner’s Knowledge Index (up to four chunks). Those snippets may be sent to the existing configured AI provider. No indexed content is searched when the option is off. If no provider is configured or all providers fail, it returns a clear service error rather than pretending to analyze the input.

The local pattern helper reports exact repeated tokens across explicitly supplied samples. It is descriptive, not causal or psychological proof. LLM-generated interpretation depends on the configured provider and should be treated as hypotheses, not diagnosis or certainty.

## Limits

- No clinical diagnosis or definitive mind-reading.
- No automatic long-term personality/behavior profile.
- Knowledge Index evidence is returned with `K1`, `K2`, etc. source metadata and URLs where available. The model is instructed to cite only these IDs for retrieved claims; verify important claims against the linked original source. This feature does not independently search the public web or guarantee source correctness.
- Personality prompts are informal reflection, not validated assessment scores.
