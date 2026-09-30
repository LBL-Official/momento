# FIRST78 Live V1 — release report (2026-09-30)

October 3 is an America/Los_Angeles target, not a gate. This increment is **IMPLEMENTED** and locally **TESTED**. It is not **DEPLOYED**, **HEALTHY**, **ARMED**, or **EXECUTING**.

## Git

| Item | SHA |
|---|---|
| Incoming | `0ffd6ca79b29cbee09771fb02cbf1f343f3395af` |
| Prior main | `39be634355a2fc2f098b9f6ea7802e5631acb8db` |
| Backup branch | `backup/pre-first78-2026-10-03` @ `39be634` |
| Merge | `8bf61ba807477fccae13d12af767785b6f91c6a7` |
| Working tree | uncommitted V1 wiring/docs on top of that merge |

Unrelated dirty files left unstaged: `research/systimo/state/sessions.json`, `Untitled.rtf`.
Not pushed.

## Hashes

| Artifact | SHA-256 |
|---|---|
| `execution_contract_v1.json` | `bf9607805ea84bfb80e7427ea3fa53882675773b002519311d6042a1aadd825e` |
| `p5_membership_2026_27.json` | `7d21c88f2c547886c0941374de599eb348e72579048b75271d747e9ee4f2df1d` |

Deployed host binary hash: **UNAVAILABLE** (this increment was not installed).

## AWS (read-only)

- Account `895492487332`, region `us-east-1`, instance `i-0f0849d5829476c31`.
- Preflight: account verified, SSM online, blocker `HOST_RUNTIME_AND_LIVE_READINESS_NOT_VERIFIED`, exit 78.
- `VITAL_AWS_CONTROL` unset.

## MLB / WNBA

See `research/vital/bots/nba-001/retirement/STOP_BLOCKED.json`.
Fresh SSM at **2026-09-30T13:53:56Z**: `momento-live.service` active/enabled, mode Live, `order_submission=enabled`, MLB+WNBA strategies active. Heartbeat `open_*_positions=0` is **not** a signed GET inventory. Stop/disable **not** performed. Secrets **not** revoked. NBA unit left running.

## Account / capital

No signed V1 recon in this increment (`RECONCILED` = no).
Host NBA heartbeat (FIRST78_67 SHADOW, not V1): shard0 `5741` cents, shard3 `56` cents. Display those integers as observed host text. They are not a V1 opening snapshot and not a `$20` fallback.
Live unit heartbeat `bankroll_cents=5000` is that service's figure, not V1 equity.

## Mode

| Term | State |
|---|---|
| IMPLEMENTED | yes — V1 contract, reducer, recon, supervisor, ledgers, outbox, Systimo projection |
| TESTED | yes locally — 188 NBA tests + 18 Kalshi + Systimo self-test |
| CONNECTED | preflight + read-only SSM only |
| RECONCILED | no |
| DEPLOYED | no |
| HEALTHY | not claimed |
| ARMED | no |
| EXECUTING | no |

Production orders compiled out. `emergency_floor_cents` remains owner-unset. `FRACTIONAL_FILLS_UNSUPPORTED` blocks ARMED (host live journal still records fractional fills).

## What remains

Owner price protection and the other `UNRESOLVED_CHECKLIST.md` fields.
2026–27 NCAAB P5 evidence.
Vital-gated MLB/WNBA drain after a signed inventory.
Atomic shadow deploy of this V1 binary.
Genuine-signal canary.

A date does not pass those gates.
