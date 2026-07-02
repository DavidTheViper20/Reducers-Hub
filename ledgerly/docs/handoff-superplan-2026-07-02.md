# Ledgerly Bank Feeds — Handoff & Super Plan

Date: 2026-07-02
Author: Claude (session on `DavidTheViper20/Reducers-Hub`, which could not access the Ledgerly repo)
Audience: a **fresh Claude Code session** with access to `DavidTheViper20/Ledgerly`. This document is
self-contained — execute it without needing any prior conversation context.

---

## 0. Instructions for David (how to start the new chat)

1. Create a new Claude Code session scoped to **`DavidTheViper20/Ledgerly`**.
   If the UI lets you add a second repository, also add `DavidTheViper20/Reducers-Hub`
   (reference only — it holds an older copy and earlier review docs; not required).
2. Attach this document to the first message.
3. Suggested kickoff prompt:

   > Read the attached handoff document fully, then execute it top to bottom. Work on branch
   > `codex/ledgerly-cloud-bank-feeds-wip-20260702`. Review the diff, then make all the changes
   > the document lists plus anything else you judge necessary. Commit in logical chunks and push.
   > Don't ask me questions unless you're blocked on credentials or a destructive decision.

That's it. Everything else the new session needs is below.

---

## 1. Project context (read this first, new session)

**Ledgerly** is a desktop replacement for Xero: an Electron app with a local SQLite ledger
(Node's built-in `node:sqlite`), double-entry bookkeeping, invoices/bills/credit notes/quotes,
bank accounts + CSV import + Xero-style reconciliation, reports (P&L, Balance Sheet, Trial
Balance, BAS), purchase orders, expenses, fixed assets, projects, payroll, multi-currency with
FX gain/loss, budgets — all localised for Australia/Victoria (GST 10%, Simpler BAS, PAYG,
super guarantee, FY ending 30 June). It also has an **AI assistant** chat bubble (bottom-right)
with provider-configurable endpoints (Anthropic / OpenAI / DeepSeek / local) and 14 read-only
ledger tools. Money is integer cents everywhere; journals must balance; reports read posted
journals only.

**Repo history — there are two copies; the Ledgerly repo is now canonical:**

- `DavidTheViper20/Reducers-Hub`, branch `claude/xero-replacement-app-ixl3i6`, directory
  `ledgerly/` — the original build (48 tests). Frozen reference; do not develop there.
- `DavidTheViper20/Ledgerly` — standalone repo (app at repo root). Its branch
  **`codex/ledgerly-cloud-bank-feeds-wip-20260702`** is one WIP commit containing everything
  below and is **the branch you work on**. Its `main` is the pre-bank-feeds baseline —
  diff against the merge-base with `main` to see exactly what changed.
- David's Mac: `/Volumes/1tb/Ledgerly-bank-feeds` (his working copy, source of the WIP push)
  and `/Users/davidnaguib/Desktop/Ledgerly` (untouched backup — never modify).

**What's on the WIP branch (written by "Codex", another AI tool, in three passes):**
It adds "Ledgerly Cloud" — a hosted broker (Node server under `server/`) that will hold the
Basiq bank-data-provider API key, user/org records, bank-feed consent, provider tokens, sync
jobs and audit logs, so the desktop app never ships or stores provider credentials.

- **Pass 1 — cloud persistence:** `pg` dependency; `server/src/db/postgres-store.js` +
  `memory-store.js` (test/dev double) behind one store contract, selected by `DATABASE_URL`;
  migration runner `server/src/db/migrate.js`; `server/src/db/schema.sql` with idempotency
  fields and uniqueness constraints; `/readyz` endpoint; tests `store-contract.test.js`,
  `app.test.js`, `schema.test.js`.
- **Pass 2 — staging deploy scaffold:** root `render.yaml`, `npm start` in server,
  `docs/release/staging-cloud-deployment.md`, `server/tests/deployment.test.js`
  (guards blueprint, checks no committed secrets). **No live deploy exists.**
- **Pass 3 — desktop sign-in scaffold:** `src/services/cloud/auth.js` (Auth0-style
  Authorization Code + PKCE, token exchange, refresh rotation, refresh token encrypted via
  Electron `safeStorage`, access token only in main-process memory);
  `electron/cloud-auth-loopback.js` (loopback OAuth callback server); `electron/main.js`
  wires `cloud-auth` IPC + legacy `cloud-session`/env-token fallback; `electron/preload.js`
  exposes `window.ledgerly.cloudAuth(method, args)`; `electron/security.js` adds
  `validateCloudAuthRequest` and refresh-token secret detection; `src/services/cloud/client.js`
  gains `hasSessionToken`; settings + dashboard UI for sign-in; tests `cloud-auth.test.js`
  and extended `electron-security.test.js`; `docs/release/desktop-cloud-auth.md`.
- **Pre-existing bank-feed work** (earlier passes, also on this branch): desktop cloud client
  (`src/services/cloud/client.js`), bank-feed flow (`src/services/cloud/bank-feed-flow.js`),
  Basiq broker/service under `src/services/bank-feed/` + server routes, provider-account →
  Ledgerly-bank-account mapping, sync into `statement_lines` with dedupe by provider
  transaction ID, consent/revocation/data-deletion paths, IPC validation.
- In-repo docs to read: `docs/claude-code-handoff-2026-07-02.md` (Codex's own handoff),
  `docs/superpowers/plans/2026-06-30-commercial-launch-readiness.md` (master roadmap),
  `docs/release/*.md`.

**Last verified state (by Codex, before the WIP commit):** `npm test` 84 passed;
`npm --prefix server test` 35 passed + 1 skipped (needs local Postgres); `npm run smoke`
41 screens + 3 interactions; `git diff --check` clean.

## 2. David's goal and mandate (verbatim intent)

- North star: **"the main thing I really wanted was for this application to be able to
  actually be synced with a bank account."** Everything is sequenced to reach a real
  Basiq-sandbox bank sync as fast as possible.
- Mandate for this session: review the diff for correctness and direction — *not*
  exhaustive testing — and then **"make all the changes you think need to be made."**
  You have authority to fix, simplify and restructure without asking, as long as you keep
  the guardrails (§6) and don't rewrite the working accounting app.
- Deferred by David (do NOT build now): AI assistant write-actions / page control;
  billing, legal, code signing, website (commercial launch pile).

## 3. Architecture decisions already made — do not relitigate

An architecture review was already done against Codex's handoff (full text:
`ledgerly/docs/bank-feeds-review-2026-07-02.md` on Reducers-Hub; conclusions reproduced here):

1. **Overall direction: sound, keep it.** Desktop + local SQLite stays the product
   (local-first is the differentiator vs Xero). Ledgerly Cloud exists only because bank
   feeds physically require a server-side key holder. Cloud owns feed/consent/audit data
   only — never the ledger.
2. **Two tracks.** Codex scoped for a commercial SaaS launch (Auth0 tenants, device
   registration/revocation, billing, legal). That's Track B — keep the scaffolding, don't
   let it block. **Track A (now): single-user path** — David's own bank data flowing on his
   own machine, with the simplest safe auth. Device enforcement is a Track B prerequisite
   for *other people's* data, not for David's own.
3. **Basiq** stays the provider (AU, CDR-accredited, sandbox available).
4. **Auth0** stays the identity plan, but is NOT a Track A blocker. Don't formalise org-ID
   claim mapping until a second tenant exists.
5. **Render** is fine for staging only — it has **no Australian region**; for production
   move to Fly.io (`syd`) / Railway / AWS `ap-southeast-2`. Note this in docs; don't churn
   hosting now.
6. **Sync model v1: desktop-initiated pull** (app start + a "Sync now" button), with the
   cloud transactions endpoint shaped as a cursor API (`?since=` / opaque cursor) from day
   one so a webhook-fed hybrid later needs no API break.
7. Postgres/memory store pair behind one contract: correct pattern, keep. Don't split
   `postgres-store.js` into modules until it actually hurts.

## 4. Phase 1 — Review the diff (do this before changing anything)

```sh
git fetch origin codex/ledgerly-cloud-bank-feeds-wip-20260702 main
git checkout codex/ledgerly-cloud-bank-feeds-wip-20260702
npm install && npm --prefix server install
npm test && npm --prefix server test && npm run smoke   # expect 84 / 35(+1 skip) / 41+3
git diff $(git merge-base HEAD origin/main)..HEAD --stat # then read the full diff
```

Review checklist — verify each in the actual code; each failure becomes a fix in Phase 2:

- [ ] **Token exposure:** nothing crossing `electron/preload.js` / IPC ever contains access
      tokens, refresh tokens, or provider credentials. Enumerate every `cloud-auth` /
      `cloud-session` IPC response shape. Renderer gets booleans/status strings only.
- [ ] **Idempotent sync:** re-running a sync can never duplicate statement lines. There must
      be a DB-level uniqueness guarantee on the dedupe key — cloud side
      (`provider_account_id, provider_transaction_id` or equivalent) AND desktop side
      (unique index on statement lines' provider-txn key, not just app-logic checks).
- [ ] **Sign/units convention:** imported statement lines are integer cents with the same
      sign convention reconciliation expects (+ money in / − money out), and dates are
      normalised the way `bank.js` expects.
- [ ] **Revocation/deletion really delete:** consent revocation and data-deletion request
      paths remove cloud-side rows (tokens, consent, cached transactions), not just flags.
- [ ] **Legacy fallback gating:** the `cloud-session`/env-token fallback must be impossible
      in production (see fix #2).
- [ ] **Secrets hygiene:** no secrets committed (deployment test claims to guard this —
      verify); server logs scrub tokens; `electron/security.js` secret-field detection
      covers refresh tokens and Basiq tokens.
- [ ] **Async conversion quality:** `server/src/app.js` async store conversion — check for
      missed awaits, unhandled rejections, and request handlers that leak errors with
      secret material in messages.
- [ ] **Existing app intact:** the accounting suites still pass and the AI assistant
      (`src/services/assistant.js`, `tests/assistant.test.js`, `ui/assistant.js`) still
      exists and works on this branch. If the assistant is missing (lineage uncertainty),
      flag it to David — the reference copy lives in Reducers-Hub `ledgerly/`.
- [ ] **Smoke passes headless:** `npm run smoke` under `xvfb-run` if no display.

## 5. Phase 2 — Changes to make (David has pre-authorised these)

In rough commit order. Add anything else the diff review surfaces — the mandate is
"all the changes you think need to be made."

1. **Numbered migrations.** Replace/extend the migration runner so schema changes are
   versioned files (`server/src/db/migrations/001_init.sql`, `002_*.sql`, …) with an
   applied-migrations table. Do this *before* any hosted DB exists — retrofitting later
   is pain. Fold the current `schema.sql` into `001_init.sql`.
2. **Gate the dev-token fallback.** Legacy `cloud-session`/env-token path is honoured only
   when explicitly in dev (e.g. `LEDGERLY_DEV_TOKEN` set AND `!app.isPackaged` /
   `NODE_ENV !== 'production'`). Add a test asserting a production-like configuration
   rejects it. Plan its removal once Auth0 is live.
3. **Dynamic loopback port.** Replace fixed port 38987: bind port 0 (or iterate a small
   registered candidate set per RFC 8252), handle port-in-use, and document the callback
   URLs that must be registered in Auth0.
4. **Dedupe indexes** (wherever the checklist found gaps): DB-level unique constraints on
   the sync dedupe keys, cloud and desktop, with tests that a double-sync inserts zero
   duplicates.
5. **Track A auth mode for the cloud server.** A config-gated static-bearer mode (e.g.
   `CLOUD_STATIC_TOKEN` env var → single user/org) so staging can run single-user without
   Auth0 being set up. Auth0 path stays intact behind config. Reject all bank-feed routes
   without *some* valid auth in every mode. Add tests for both modes.
6. **Cursor-shaped transactions endpoint + "Sync now".** Ensure the cloud → desktop
   transaction pull uses an incremental cursor (`?since=`/cursor param) rather than
   full-dump-every-time, and the bank screen has a manual "Sync now" affordance.
   (If Codex already built this shape, just verify and test it.)
7. **IPC/security tightening** from checklist findings: any response field carrying token
   material gets stripped; extend `tests/electron-security.test.js` to enumerate and
   assert the full `cloudAuth` surface.
8. **Docs honesty pass.** Update `docs/release/*.md` and the master plan: mark what is
   scaffolded vs deployed; add the Render-has-no-AU-region note and the production-host
   recommendation; document Track A vs Track B sequencing (you can copy §3 of this doc).
9. **Settings UI (low priority, do last):** split "Cloud account" into its own card in
   `ui/views/settings.js` instead of crowding the Bank feeds card.
10. **Run everything; fix what breaks.** `npm test`, `npm --prefix server test`,
    `npm run smoke`, `git diff --check`. All green before finishing.

**Commit strategy:** logical chunks, not one blob — e.g.
`feat: add Ledgerly Cloud Postgres persistence`, `chore: add staging deployment scaffold`,
`feat: add secure desktop cloud sign-in`, then one commit per fix above. Push to
`codex/ledgerly-cloud-bank-feeds-wip-20260702` (or a successor branch — tell David which).
Do not merge to `main` without David's say-so.

## 6. Guardrails (carry these verbatim)

- Never modify `/Users/davidnaguib/Desktop/Ledgerly` (Mac backup) — irrelevant in a cloud
  session, but never instruct David to touch it either.
- Provider credentials (Basiq keys, server tokens) live **only** in Ledgerly Cloud.
  Never in the desktop app, renderer, local SQLite, or the repo.
- Access tokens never reach the renderer or disk; refresh tokens only via `safeStorage`.
- No secrets committed, ever. No hard-coded keys, even "temporarily".
- Small, testable passes; security-boundary tests before/with implementation.
- Preserve the existing accounting/reconciliation UX — bank feeds feed *into* it.
- Keep docs honest about scaffolded vs deployed.

## 7. Phase 3+ — after the code is fixed (needs David)

**Phase 3 — minimal staging (Track A):** David provides a hosting account (Render OK for
staging), hosted Postgres, and a **Basiq sandbox API key** (cloud env only). Deploy, run
migrations, verify `/healthz`, `/readyz`, 401s on unauthenticated routes, scrubbed logs.

**Phase 4 — the milestone: first real sandbox sync end-to-end.** Desktop → cloud → Basiq
consent in browser → list provider accounts → map to a Ledgerly bank account → pull
transactions → statement lines appear → reconcile. Also exercise reconnect, revoke, and
data-deletion. **This is "actually synced with a bank account" — the whole point.**

**Phase 5 (Track B, only when David wants other users):** Auth0 tenant live, device
registration/enforcement (Codex's Pass-4 test list in its handoff is good), AU-region host,
then billing/legal/signing/auto-update.

**What David provides, when:**
- Phase 3–4: hosting account, hosted Postgres, Basiq sandbox key.
- Phase 5: Auth0 tenant + native app client + API audience + refresh rotation; monitoring.
- Phase 6: Stripe, domain, signing certs. — Never: secrets in the repo.

## 8. Definition of done for the new session's first sitting

1. Full diff reviewed against the §4 checklist, findings noted.
2. All §5 changes (plus judgment calls) implemented, all suites green, pushed in logical
   commits.
3. A short summary to David: what was found, what was changed, what Phase 3 needs from him
   (the three credentials above) — so the very next step is the staging deploy and then the
   first real bank sync.
