# Rico — Waitlist / Quick-Start Form (Jotform)

Reference for the public Jotform intake **"Rico AI Quick Start"**
(`form.jotform.com/261278237812056`), reviewed against what the backend
actually reads in `src/rico_jotform_webhook.py`.

The form is deliberately a **short, welcoming first hello** — not a full
profile. Rico completes the picture later, in conversation
("Give just a few basics, then talk naturally with Rico").

---

## Current fields (live)

| Order | Question a person sees | Purpose | Required |
|------|------------------------|---------|----------|
| 1 | First name | Greeting / personalisation | Yes |
| 2 | **Email** *(added 2026-07)* | Reliable contact + backend identity | Yes |
| 3 | Telegram username | Where Rico actually reaches the person | Yes |
| 4 | What dream job should Rico help you move toward? | Target role | Yes |
| 5 | Preferred UAE city | Location matching | Yes |
| 6 | **Lowest monthly salary you'd accept (AED)** *(added 2026-07)* | Sharpens matching | No |
| 7 | Anything Rico should avoid? | Negative preferences | No |
| 8 | Upload CV *(optional — Rico can start without it)* | Profile enrichment | No |
| 9 | Consent checkbox (store & process profile per Privacy Policy) | Legal basis | Yes |

Intro copy was softened from *"your AI-native UAE career companion"* to
*"your AI career companion for the UAE"* to match the product's plain, human
voice.

## Deliberately kept OFF the form

These add friction and confuse a first-time visitor. Rico infers them in chat
instead: `autonomy_level`, `match_strictness`, `communication_style`,
`skills`, `industries`, `visa_status`, `notice_period`, `years_experience`.

---

## Backend field-name alignment (follow-up for the owner)

`src/rico_jotform_webhook.py` reads answers by **unique field name**, so each
Jotform field's internal name must match the key the webhook expects. Identity
resolves from `email` first, then `telegram_username` (`_resolve_user_id`).

Confirm these unique names in the Jotform builder (Field → Properties →
Advanced → "Unique Name"):

| Question | Webhook key expected | Notes |
|----------|----------------------|-------|
| Email | `email` | ✔ new field created with name `email` |
| Telegram username | `telegram_username` | verify |
| First name | `full_name` (or `name`) | verify |
| Dream job | `target_roles` | verify |
| Preferred UAE city | `preferred_cities` | verify |
| Lowest monthly salary | `minimum_salary_aed` | new field was auto-named `lowestMonthly` — **rename to `minimum_salary_aed`** so the answer reaches the backend |

"Anything Rico should avoid?" has no dedicated webhook key today; if it should
persist to the profile, add a mapping in `rico_jotform_webhook.py` (e.g.
`avoid` / `exclusions`). No backend change was made as part of this pass —
flagged here for a reviewed follow-up.
