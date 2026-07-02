# Bank Feeds: Architecture Review & Revised Plan

Date: 2026-07-02 (reviewed by Claude from the Codex handoff `claudecodehandoff20260702.md`)
Status of this review: based on the handoff document only — the actual Codex diff lives
uncommitted in `/Volumes/1tb/Ledgerly-bank-feeds` on branch `codex/xero-bank-feeds` and
has NOT been pushed anywhere Claude can read it.

> **ACTION REQUIRED (David):** commit the working tree in `/Volumes/1tb/Ledgerly-bank-feeds`
> (even as one WIP commit) and push branch `codex/xero-bank-feeds` to GitHub so the actual
> code can be reviewed line-by-line next session. Until then, everything below is an
> architecture-level review, not a code review.

---

## 1. Verdict on the overall direction

**Sound. Keep it.** For real bank feeds from a desktop app, a hosted broker is essentially
forced: the bank-data provider's API key must never ship inside a distributable desktop
binary, so *something* server-side has to hold it. The proposed split is the right shape:

- **Ledgerly Desktop** — accounting UI + local SQLite ledger (local-first stays the product promise).
- **Ledgerly Cloud** — holds Basiq keys, consent state, provider tokens, sync jobs, audit log.
- Imported transactions land as `statement_lines` and flow through the existing
  reconciliation UX — this is exactly right; it means bank feeds reuse everything already
  built and tested rather than adding a parallel pipeline.

Also correct: Auth Code + PKCE with a loopback redirect (the standard native-app OAuth
pattern), refresh token encrypted with Electron `safeStorage`, access token only in
main-process memory, never in the renderer or SQLite. The memory-store/Postgres-store
pair behind one contract with a `DATABASE_URL` switch is a standard, testable pattern.

## 2. The big strategic flag: personal goal vs commercial scope

David's stated goal: *"the main thing I really wanted was for this application to be able
to actually be synced with a bank account."*

Codex's plan targets a **commercial launch**: Auth0 tenants, device registration and
revocation, billing/entitlements, legal pack, code signing, support tooling, incident
response. All legitimate — *for selling the product*. None of it is required to get
David's own bank transactions flowing into his own ledger.

Two tracks, both compatible with the code already written:

| | Track A: Personal-first (recommended now) | Track B: Commercial |
|---|---|---|
| Cloud auth | Single static bearer token (one user: you) | Auth0 + PKCE (already scaffolded) |
| Device enforcement | Skip | Required before onboarding strangers |
| Billing/legal/signing | Skip | Required |
| Time to first real bank sync | Days | Weeks–months |

**Recommendation:** keep all the Auth0/device scaffolding in the tree (it's the right
end-state), but do not make it a prerequisite. Sequence the work so a real Basiq sandbox
sync happens first under a single-tenant guardrail, then harden. The handoff calls device
enforcement "the most important next pass before real bank data" — that's true before
*other people's* bank data; it is not a blocker for the owner's own sandbox/production
consent on his own machine.

## 3. Specific technical review (from the handoff descriptions)

### Pass 1 — Postgres persistence: agree, with two asks
- Memory store + Postgres store behind one contract: good. Keep the contract test.
- **Adopt numbered/versioned migrations now** (e.g. `001_init.sql`, `002_...`), before any
  hosted DB exists. Retrofitting versioning after a staging DB has state is pain for zero
  benefit. The handoff itself flags this — do it.
- Idempotency keys + uniqueness constraints on sync jobs/transactions: essential for
  money-adjacent data. Verify there is a unique index on
  `(provider_account_id, provider_transaction_id)` on the cloud side **and** the same
  dedupe key on desktop `statement_lines` import (local unique index, not just app logic).
- Splitting `postgres-store.js` into modules: defer until it actually hurts. Don't churn.

### Pass 2 — Render staging: fine for staging, wrong region for production
- Render is a fast path to web service + managed Postgres. OK for staging.
- **Flag: Render has no Australian region.** Bank feeds are AU (Basiq/CDR). For anything
  past experiments, AU data residency and latency matter — CDR-adjacent data hosted in
  Oregon/Frankfurt is a bad look and possibly a compliance problem for a commercial
  product. Prefer Fly.io (`syd`), Railway, or AWS `ap-southeast-2` when leaving staging.
  Decision can wait; the `render.yaml` doesn't lock anything in.

### Pass 3 — Desktop sign-in scaffold: right pattern, three fixes
- Auth Code + PKCE + loopback callback + `safeStorage` refresh token + main-memory access
  token: textbook correct for native apps.
- **Fixed loopback port 38987 is fragile** (port collisions, multiple instances). Use a
  dynamic port from a small registered set, or bind port 0 and register the handful of
  candidate callback URLs in Auth0. RFC 8252 anticipates exactly this.
- **Gate the legacy `cloud-session`/env-token fallback** behind an explicit dev flag
  (e.g. `LEDGERLY_DEV_TOKEN` only honoured when `NODE_ENV !== 'production'`), so it can
  never be a production bypass. Remove entirely once Auth0 is live.
- Org-ID claim mapping: don't formalise until a second tenant/user actually exists.
  Single-tenant assumption is fine for Track A.
- UI: agree with the handoff's instinct — cloud account status deserves its own
  "Cloud account" card in Settings rather than crowding the Bank feeds card. Low priority.

### Pre-existing bank-feed work (client, flow, Basiq service, consent/revocation/deletion)
- Direction is right. The critical properties to verify in code review (next session):
  1. Renderer never sees provider tokens or access tokens (IPC surface audit).
  2. Sync is idempotent — re-running a sync never duplicates statement lines.
  3. Consent revocation and data-deletion paths actually delete cloud-side rows.
  4. Statement-line import maps amounts to integer cents with the same sign convention
     the reconciliation screen expects (+in / −out).

### Sync model (the handoff asks: pull, push, webhook, hybrid?)
**v1: desktop-initiated pull** (on app start + a "Sync now" button on the bank screen).
It matches local-first (the cloud doesn't own the ledger), works when the desktop is
offline-most-of-the-time, and is the simplest to make idempotent. Design the cloud
transactions endpoint as a cursor API (`?since=`) from day one so a later hybrid
(webhook fills a cloud cache → desktop pulls the cache) needs no API break.

### Provider choice
Basiq is the right AU pick (CDR-accredited, AU coverage, sandbox available). No change.

### Architecture questions the handoff asks us to challenge — answers
- Electron + local SQLite + cloud broker: **yes, keep.** Local-first is the differentiator
  vs Xero; the broker exists only because bank feeds physically require it.
- Should cloud own more ledger data: **no.** Feed/consent/audit data only.
- Auth0 first: **fine.** Don't churn identity providers; revisit only if pricing bites.
- Render past staging: **no — AU region issue above.**
- Idempotency/audit coverage: verify in code review; the schema fields exist per Pass 1.

## 4. Revised sequencing (replaces the handoff's "Immediate Steps")

1. **Get the code visible & committed.** David pushes `codex/xero-bank-feeds` to GitHub.
   Claude reviews the actual diff, fixes what's broken, lands it in logical commits
   (the handoff's suggested commit split is fine).
2. **Migration versioning + dedupe indexes** (small, do before any hosted DB).
3. **Minimal staging deploy for one user** — needs from David: hosting account
   (Render OK for now), hosted Postgres, Basiq **sandbox** key. Auth can start as a
   single static bearer token (Track A) with the Auth0 path kept behind a flag.
4. **First real sandbox sync end-to-end:** desktop → cloud → Basiq consent in browser →
   list provider accounts → map to a Ledgerly bank account → pull transactions →
   statement lines appear → reconcile. This is the milestone that satisfies
   "actually synced with a bank account."
5. **Then** harden for other humans: Auth0 live, device registration/enforcement
   (the handoff's Pass 4 test list is good), scrubbed logs verified, AU-region host.
6. **Then** the commercial pile: billing, legal, signing, auto-update, website — only if
   David actually wants to sell it.

## 5. What David needs to provide (unchanged from handoff, ordered by when needed)

Now (for steps 3–4): hosting account, hosted Postgres, Basiq sandbox key.
Later (step 5): Auth0 tenant + native app + API audience + refresh rotation, monitoring.
Much later (step 6): Stripe, domain, signing certificates.

Never: no secrets in the repo, no provider keys in the desktop app or renderer.

## 6. Guardrails carried forward

- `/Users/davidnaguib/Desktop/Ledgerly` is the untouched backup — never modify.
- Work happens in `/Volumes/1tb/Ledgerly-bank-feeds` (or on the pushed branch).
- Provider credentials live only in Ledgerly Cloud; tokens never reach the renderer.
- Small testable passes; security-boundary tests before implementation where possible.
- Keep the existing accounting/reconciliation UX intact — bank feeds feed into it,
  they don't replace it.

## 7. Verification commands (in the bank-feeds working copy)

```sh
npm test                  # desktop suite (was 84 passing per handoff)
npm --prefix server test  # cloud suite (was 35 passing, 1 skipped without local PG)
npm run smoke             # 41 screens + 3 interactions
git diff --check
```
