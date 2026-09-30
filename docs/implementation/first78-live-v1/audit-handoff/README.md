# FIRST78 Live V1 — independent audit handoff

Versioned package: [`2026-09-30/`](2026-09-30/).

This folder prepares a **reproducible challenge**, not a passed audit.
Pushing a git commit does **not** deploy the binary. The host still runs
FIRST78_67 SHADOW (`nba001-20260927T042347Z`).

## Exact identities

| Role | Value |
|---|---|
| Branch | `main` |
| Implementation commit (source under review) | `2a22a2a2f7797f9d54b6372c6f4f8ccb5379bcc2` |
| Audit-documentation commit | `1daeeba2598facd65f21f240fb3832278956a1a6` (folder); tip stamp `c28b1317ef866525fdefd9fbe11e5689a1cce7fa` |
| Deployed code | GET-only FIRST78_67 worker started `2026-09-27T04:30:09Z` |
| Deployed binary SHA-256 | `9ef129e1d8b1ee111666e80265d70cd3dad1ddfa3dd5017d9865b848e57d6789` |
| Host contract SHA-256 | `ef1c488ab450aadd82e78c2bde2f40506d6baccee15e35f4e09fb3f9869d5ab9` (FIRST78_67, **not** V1) |

GitHub commit URL (after push):
`https://github.com/LBL-Official/momento/commit/2a22a2a2f7797f9d54b6372c6f4f8ccb5379bcc2`

## Reproduce locally (no credentials)

Pinned toolchain: `rust-toolchain.toml` channel `1.98.0`.

```sh
git checkout 2a22a2a2f7797f9d54b6372c6f4f8ccb5379bcc2
cargo test --locked -p momento-strategy-nba -p momento-nba-001
cargo test --locked -p momento-kalshi
python3 ROLLER/roller/systimo/nba001_v1.py
```

Expected when last recorded: 121 + 67 (+1 ignored) + 18 Kalshi; Systimo self-test prints `nba001_v1_self_test_ok`.
See [`2026-09-30/TEST_RESULTS.md`](2026-09-30/TEST_RESULTS.md) and [`2026-09-30/ADVERSARIAL.md`](2026-09-30/ADVERSARIAL.md).

## Artifact index

| File | Contents |
|---|---|
| [`2026-09-30/release-manifest.json`](2026-09-30/release-manifest.json) | SHAs, hashes, timestamps, mode |
| [`2026-09-30/TEST_RESULTS.md`](2026-09-30/TEST_RESULTS.md) | Commands, totals, ignored, untested |
| [`2026-09-30/DEPLOYMENT_EVIDENCE.md`](2026-09-30/DEPLOYMENT_EVIDENCE.md) | Fresh AWS/SSM observations |
| [`2026-09-30/ACCESS_REQUIREMENTS.md`](2026-09-30/ACCESS_REQUIREMENTS.md) | What Codex/another agent can and cannot inherit |
| [`2026-09-30/KNOWN_GAPS.md`](2026-09-30/KNOWN_GAPS.md) | Blockers, defects, unsupported behavior |
| [`2026-09-30/ADVERSARIAL.md`](2026-09-30/ADVERSARIAL.md) | Isolated commands/fixtures for challenge tests |
| [`2026-09-30/ACCOUNT_OBSERVE.md`](2026-09-30/ACCOUNT_OBSERVE.md) | Host GET-only cash/position integers |

Sensitive artifacts stay on the host (`/dev/shm/momento-kalshi-nba-001.json`, signed Kalshi bodies). This repo holds digests and redacted summaries only.

## Honesty terms

Use only: IMPLEMENTED, TESTED, CONNECTED, RECONCILED, DEPLOYED, HEALTHY, ARMED, EXECUTING.
Do not collapse them. This package does **not** declare the independent audit passed.
