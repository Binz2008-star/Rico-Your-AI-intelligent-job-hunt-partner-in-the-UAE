# Localization: the "Detect-but-ignore" Bug Pattern

This document covers a recurring localization bug pattern found and fixed in
`src/rico_chat_api.py` (PR #606), and the regression rule and testing
guideline adopted to prevent it from reoccurring.

## The pattern

"Detect-but-ignore" describes a handler that correctly detects the user is
writing in Arabic somewhere in the request pipeline, but never receives that
detection result where it actually builds the reply text — so it returns
hardcoded English copy regardless of what language the user wrote in.

Before the fix, affected handlers looked like this:

```python
def _handle_lifecycle_query(self, user_id: str, query_type: str) -> dict:
    ...
    if not rows:
        empty_msg = "You haven't saved any jobs yet."
        return {"message": empty_msg, ...}
```

Earlier in the same request, Rico had already called something like
`self._is_arabic_text(message)` to decide how to classify intent or prompt
the AI provider — but the original `message` was never passed into this
handler, so it had no way to choose Arabic output even though the language
had already been correctly identified upstream.

22 methods in `src/rico_chat_api.py` had this issue, covering application
tracking, saved/applied job lists, profile completeness, role suggestions,
no-results recovery, CV generation, subscription information, and related
chat flows. One related resolver, `_resolve_verify_followup`, had the same
issue.

## The fix

Thread the original user message (or an explicit language flag derived from
it) into every handler that produces user-facing text, and branch on it:

```python
def _handle_lifecycle_query(
    self,
    user_id: str,
    query_type: str,
    message: str = "",
) -> dict:
    arabic = self._is_arabic_text(message)
    ...
    if not rows:
        empty_msg = (
            "لم تحفظ أي وظائف بعد."
            if arabic
            else "You haven't saved any jobs yet."
        )
        return {"message": empty_msg, ...}
```

The `message` parameter defaults to `""` (which `_is_arabic_text` safely
treats as non-Arabic), so existing call sites and tests that don't pass it
remain valid.

## What intentionally stays in English

Itemized data — job titles, company names, application records, and CV
section headers — intentionally remains in English even when the
surrounding conversational text is Arabic. This matches the convention
already shipped for the applications list (PR #605): UAE job postings and
CVs are conventionally handled in English regardless of the chat language.

## Regression rule

> Any chat-reachable handler that returns user-facing text must receive
> language context or the original user message.

When adding a new `_handle_*` method (or similar) to `src/rico_chat_api.py`
that returns a `message` field to the user, give it a `message: str = ""`
parameter (or accept an explicit `arabic: bool` flag) and branch any
hardcoded copy on `self._is_arabic_text(message)`. Itemized job/CV data is
exempt per the convention above.

## Testing guideline

When testing a handler that returns user-facing text:

- Arabic input should produce Arabic empty-state, success, and failure
  messages.
- English input should produce the same English copy as before — confirm
  no regression there too.

See `tests/test_lifecycle_followup.py` and `tests/test_cv_generation_continuity.py`
for examples of tests covering this for already-fixed handlers.
