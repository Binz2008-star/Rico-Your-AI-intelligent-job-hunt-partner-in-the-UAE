# Rico Product Communications Standard

## Purpose

This is Rico's canonical standard for communicating meaningful product changes to users. It governs in-app announcements, `/whats-new`, bilingual email, audience targeting, consent, delivery controls, reporting, and feedback.

This document defines policy and architecture boundaries. Runtime implementation must be delivered through separate, small PRs.

## Source of truth and ownership

- Live `main`, deployed evidence, and AI_WORKSPACE remain the source of truth for product reality.
- This document is the source of truth for communication policy and release-announcement governance.
- `/whats-new` is the user-facing release history, not a duplicate of internal engineering documentation.
- The product owner approves audience, message, channels, and send timing.
- Engineering verifies delivery safety, observability, rollback, and production readiness.
- No agent may contact real users without explicit owner approval.

## What qualifies for communication

Communicate:

- meaningful new capabilities;
- major UX or navigation changes;
- important workflow improvements;
- security or account-impacting changes;
- pricing or plan changes;
- service-impacting maintenance or incident resolution;
- substantial improvements to chat, applications, job discovery, career memory, or productivity.

Do not communicate:

- internal refactors;
- routine dependency updates;
- small styling fixes;
- invisible infrastructure changes;
- preview-only or unverified work;
- features not yet live;
- PR numbers, commit hashes, provider names, or internal implementation details.

## Announcement lifecycle

`draft → review → approved → scheduled → publishing → published → paused/archived/canceled`

Rules:

1. Draft content cannot send.
2. Approval must identify audience, channels, timing, and approver.
3. Large audiences require an explicit final confirmation.
4. Publishing must be idempotent, resumable, observable, and pausable.
5. The exact approved content version and resolved audience must remain auditable.

## Canonical announcement data

The eventual implementation should support:

- internal name, type, priority, and lifecycle status;
- bilingual title, summary, body, CTA label, and CTA URL;
- audience definition and resolved audience snapshot;
- enabled channels;
- publish and expiry times;
- creator and approver;
- content version and related release;
- pause/rollback note;
- created, updated, approved, and published timestamps.

The final schema must be designed only after verifying the existing repository and Neon schema.

## Audience standard

Supported audiences may include:

- all active registered users;
- paid, Pro, or Premium users;
- users active within a defined period;
- Arabic or English users;
- onboarding-complete or onboarding-incomplete users;
- users with or without tracked applications;
- explicit internal test recipients.

Audience protections:

- exclude deactivated and deleted accounts;
- honor consent and communication preferences;
- preview estimated recipient count before approval;
- save a resolved audience snapshot;
- never expose raw SQL in admin tools;
- do not support arbitrary list uploads in the first release;
- never expose recipient email lists in screenshots or broad reports.

## Channel standard

Initial channels:

- in-app announcements;
- `/whats-new`;
- email.

Future-compatible, but not approved for immediate implementation:

- Telegram;
- WhatsApp;
- push notifications;
- digest inclusion.

Every channel requires a preview, delivery state, failure reason, dedupe key, bounded retries, rate/volume guard, consent behavior, kill switch, and per-announcement pause.

## In-app announcements

Approved surfaces:

- lightweight banner;
- What’s New card;
- announcement center/history;
- modal only for critical account, security, or service-impacting notices.

Required states and behavior:

- unread, read, dismissed, and CTA-clicked;
- no repeated modal on every visit;
- expiry and deep-link support;
- bilingual EN/AR and correct RTL;
- mobile-safe, accessible, and reduced-motion safe;
- ordinary updates must not block product use.

## `/whats-new`

The route must:

- show newest updates first;
- support English and Arabic;
- include category, release date, user benefit, and optional CTA;
- provide stable links to individual updates;
- preserve archived updates;
- avoid engineering jargon and private implementation details.

Suggested categories: New, Improved, Fixed, Security, Career Intelligence, Applications, Chat, Mobile.

## Email standard

Reusable templates should cover product updates, redesigns, feature launches, important fixes, security notices, maintenance, paid-member early access, and feedback requests.

Requirements:

- approved Rico sender configuration only;
- responsive HTML plus plain-text fallback;
- English and Arabic with correct RTL;
- subject and content preview;
- test-send and dry-run modes;
- safe personalization such as first name only;
- support contact and unsubscribe for optional updates;
- stored approved content version;
- no CV content, application details, secrets, or sensitive profile data.

## Consent classes

Transactional: verification, password reset, billing receipts, security alerts, and user-requested workflow notifications.

Product updates: release announcements, redesign notices, feature summaries, surveys, and tips.

Marketing: promotions, offers, campaigns, and referrals.

Rules:

- required transactional messages remain available;
- product-update and marketing preferences must be independently controllable where appropriate;
- unsubscribe must not deactivate the Rico account;
- no dark patterns;
- consent and preference changes must be auditable.

## Admin workflow

`Create → write EN/AR → choose channels → define audience → preview count → preview surfaces → test send → approve → schedule/publish → monitor → pause/archive`

Admin protections:

- role-protected and audit-logged;
- no secrets displayed;
- test and production modes clearly separated;
- no hidden auto-send;
- explicit large-send confirmation;
- no direct database editing;
- no broad send until test-recipient and dry-run gates pass.

## Delivery architecture

Use Rico's approved FastAPI, Neon, frontend, and verified existing delivery infrastructure. Do not introduce architecture drift.

Target flow:

`announcement → audience snapshot → delivery batches → per-recipient delivery record → provider result → engagement events`

Required properties:

- idempotency and deduplication;
- bounded retries and batch isolation;
- fail-soft processing and interruption recovery;
- per-recipient status;
- test-recipient and dry-run modes;
- global kill switch and per-announcement pause;
- clear rollback path.

No new queue, worker platform, or provider may be introduced without evidence that existing infrastructure is insufficient and an approved Decision Record.

## Analytics and feedback

Track only privacy-respecting, useful metrics:

- resolved audience size;
- attempted, delivered, failed, and bounced when available;
- CTA clicked;
- in-app viewed and dismissed;
- relevant downstream product action;
- unsubscribe count.

Do not present open-rate tracking as exact without evidence of reliability and legal acceptability.

Feedback may use direct email reply, a simple link, thumbs up/down, a short comment, or report-a-problem. Do not build a separate survey platform without evidence.

## First standard campaign

The first campaign is **Rico has a new look**.

It may publish only after:

- the redesign is merged;
- production deployment is verified;
- desktop and mobile smoke pass;
- Arabic and English QA pass;
- no known user-breaking regression remains;
- audience, consent, sender, test-send, dry-run, dedupe, pause, and observability gates pass;
- the owner explicitly approves the send.

Channels:

- in-app announcement;
- email;
- `/whats-new` entry.

The message must explain what changed, why it helps, confirm account/data continuity, link to the updated experience, and request feedback. Paid members may receive a more personal variant, but factual claims must remain identical.

## Implementation roadmap

### Phase 0 — Evidence-first audit

Verify existing user, subscription, preference, email, analytics, admin, notification, and unsubscribe infrastructure. Produce a reuse/conflict matrix before code or schema design.

### Phase 1 — Data and repository layer

Additive announcement, audience snapshot, delivery, and audit models. No sending.

### Phase 2 — Admin draft and preview

Create/edit/preview bilingual content and test audiences. No production publishing.

### Phase 3 — In-app and `/whats-new`

Read/dismiss/click states and bilingual release history. No email sending yet.

### Phase 4 — Email test mode

Templates, test recipient, dry run, and delivery logs.

### Phase 5 — Controlled production sending

Audience snapshots, batches, dedupe, retry, pause, and explicit owner gate.

### Phase 6 — Reporting and feedback

Delivery reporting, engagement, and lightweight feedback.

Each phase must be one small reviewable PR with scope, risk, acceptance criteria, rollback, and AI_WORKSPACE synchronization.

## Production gates

Before any real contact, verify:

- exact deployed commit and production readiness;
- CI and required reviews;
- sender configuration and provider limits;
- audience estimate, exclusions, and consent;
- test-send and dry-run results;
- idempotency and duplicate prevention;
- pause and kill-switch behavior;
- delivery observability and rollback;
- explicit owner approval.

## Prohibited shortcuts

- Gmail BCC as the production system;
- personal sender mailbox;
- hardcoded sender addresses;
- direct database edits to simulate delivery;
- real user contact during development;
- exposing user emails in logs, screenshots, or PRs;
- sending before production verification;
- silently changing approved content;
- creating parallel documentation outside AI_WORKSPACE.

## Update rule

Update this standard when a communication channel becomes production-supported, consent/legal handling changes, approval or publishing lifecycle changes, delivery infrastructure changes, or a post-incident review identifies a missing guard.