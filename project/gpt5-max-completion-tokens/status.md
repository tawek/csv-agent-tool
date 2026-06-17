# Status

- Current state: implementation complete.
- Active step: n/a (done).
- Blockers: none.
- Next actions:
   1. ~~inspect source and tests~~ ✓
   2. ~~update specification for correct GPT-5 behavior~~ ↻ no spec change required (implementation-detail only)
   3. ~~implement and validate fix~~ ✓
   4. ~~review findings and close action register~~ ✓

## Implementation Notes

- Changed `max_tokens` → `max_completion_tokens` on the single `OpenAIProvider.generate()` SDK call (providers.py:232).
- Updated the corresponding test assertion in `test_openai_provider_uses_sdk` to check `max_completion_tokens`.
- Ollama provider is unaffected (uses `num_predict` in its own API payload).
- Internal `max_output_tokens` config/method-argument name preserved unchanged.
- No spec update needed — this is an implementation-detail fix, not a user-facing behavior change.
