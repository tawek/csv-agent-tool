# Request: GPT-5 max completion tokens compatibility

- Fix the OpenAI request path for newer GPT-5 models that reject `max_tokens`.
- Use the supported parameter expected by those models so generation succeeds.
- Preserve existing behavior for supported models as much as possible.
- Add regression coverage for the request payload behavior.
- Non-goal: unrelated provider refactors or broader OpenAI API redesign.
