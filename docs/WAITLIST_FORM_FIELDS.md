# Rico — Waitlist / Quick-Start Form (Jotform)

Reference for the public Jotform intake **"Rico AI Quick Start"**
(`form.jotform.com/261278237812056`), reviewed against what the backend
actually reads in `src/rico_jotform_webhook.py`.

The form is deliberately a **short, welcoming first hello** — only what makes
Rico useful from the first message: who you are, how to reach you, the role you
want, and (optionally) your CV. Everything else — salary, preferences, things
to avoid — Rico learns naturally in conversation
("Give just a few basics, then talk naturally with Rico").

---

## Visible fields (live)

| Order | Question a person sees | Purpose | Required |
|------|------------------------|---------|----------|
| 1 | First name | Greeting / personalisation | Yes |
| 2 | Email | Reliable contact + backend identity | Yes |
| 3 | **Mobile number (WhatsApp)** | Primary contact — how Rico reaches you | Yes |
| 4 | What dream job should Rico help you move toward? | Target role | Yes |
| 5 | Preferred UAE city | Location matching | Yes |
| 6 | Upload CV *(optional — Rico can start without it)* | Profile enrichment | No |
| 7 | Consent checkbox (store & process profile per Privacy Policy) | Legal basis | Yes |

## Hidden fields (kept for existing submission data, off the new form)

Hidden — not deleted — so the 5 early submissions keep their data, while new
sign-ups no longer see them. Rico gathers these in chat instead:

- **Telegram username** — replaced by Mobile number (WhatsApp) as first contact.
- **Anything Rico should avoid?** — a conversation, not a form field.
- **Lowest monthly salary (AED)** — Rico asks during the first chat.

Also never on the form (inferred in-app): `autonomy_level`, `match_strictness`,
`communication_style`, `skills`, `industries`, `visa_status`, `notice_period`,
`years_experience`.

---

## Backend field-name alignment (follow-up for the owner)

`src/rico_jotform_webhook.py` reads answers by **unique field name**, so each
Jotform field's internal name must match the key the webhook expects. Identity
resolves from `email` first, then `telegram_username` (`_resolve_user_id`).
With Telegram now hidden, **`email` is the primary identity** — good, it is
required.

Confirm/adjust these unique names in the Jotform builder (Field → Properties →
Advanced → "Unique Name"):

| Question | Webhook key expected | Notes |
|----------|----------------------|-------|
| Email | `email` | ✔ matches |
| Mobile number (WhatsApp) | `phone` | new field auto-named `mobileNumber` — **rename to `phone`** so it reaches the backend |
| First name | `full_name` (or `name`) | verify |
| Dream job | `target_roles` | verify |
| Preferred UAE city | `preferred_cities` | verify |

No backend code was changed in this pass — the alignment above is a small,
reviewed follow-up (rename one field, verify the rest).

## Note on delivery channel

The deck and current backend deliver matches over **Telegram**
(`notification_router.py`). Collecting a WhatsApp mobile number as first contact
does **not** change that — Rico can send a Telegram start-link via WhatsApp/email
during onboarding. If the product intends to move delivery itself to
WhatsApp/SMS, that is an architectural change (touches the whole notification
layer) and should be its own reviewed decision — flag it before updating the
deck's "on Telegram" language.
