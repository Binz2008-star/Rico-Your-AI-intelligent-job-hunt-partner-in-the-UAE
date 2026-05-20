## Rico change summary

Describe the change clearly.

---

## Linked work

GitHub issue:
- Closes #147

Asana task:
- Paste Asana task URL here
- Or add: asana_task: 1234567890

---

## Engineering guardrails

- [ ] I reviewed Issue #147 before changing architecture or paths.
- [ ] Production entrypoint remains `src.api.app:app`.
- [ ] I did not create duplicate Rico routers/services unnecessarily.
- [ ] I did not bypass approval-required safety flows.
- [ ] I did not expose secrets/prompts/internal traces.
- [ ] Public endpoint behavior changes were reviewed.

---

## Smoke testing

List the smoke tests or commands you ran.

```bash
python scripts/test_rico_startup.py
```

Additional checks:

- [ ] /health
- [ ] /api/docs
- [ ] Rico chat
- [ ] CV upload
- [ ] Telegram webhook
- [ ] Jotform webhook
