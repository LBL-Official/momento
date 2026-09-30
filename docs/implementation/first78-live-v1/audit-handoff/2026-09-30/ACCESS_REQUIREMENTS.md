# Access requirements for an independent reviewer (Codex)

Local AWS profiles, SSM sessions, and Kalshi secret files **do not transfer** to another agent. This authoring environment had an AWS CLI session that could call STS and SSM; Codex Cloud / another machine starts with none of that unless separately provisioned.

Do not weaken IAM, open new public ports, or enable unrestricted remote shells to make the audit convenient.

## GitHub

| Need | Detail |
|---|---|
| Repo | `https://github.com/LBL-Official/momento` |
| Branch | `main` |
| Read | clone / `git show 2a22a2a2f7797f9d54b6372c6f4f8ccb5379bcc2` |
| Blocker if missing | cannot reproduce source tests or read this handoff |

## AWS (read-only identity + optional host inspect)

| Need | Detail |
|---|---|
| Account | `895492487332` |
| Region | `us-east-1` |
| Instance | `i-0f0849d5829476c31` |
| Services | `momento-nba-001.service`, `momento-live.service` |
| Approved identity check | `python3 deploy/nba001-v1-preflight.py --expected-account 895492487332` (never claims trading-ready; exits 78) |
| Minimum IAM for preflight | `sts:GetCallerIdentity`, `ssm:DescribeInstanceInformation` |
| Host file/journal inspect | operator SSM `AWS-RunShellScript` **read-only** commands, or Momento LS observe (`docs/operations/MOMENTO_LS.md`, `:5181` / `:8792`) |
| Extra IAM if SSM inspect is authorized | `ssm:SendCommand`, `ssm:GetCommandInvocation` on that instance only |
| Forbidden | `VITAL_AWS_CONTROL`, systemd stop/disable, secret file reads, production Create/Cancel |

`VITAL_AWS_CONTROL` unset is fail-closed. Do not export it to complete the audit.

## Kalshi

| Path | Status |
|---|---|
| Host GET-only via deployed NBA worker | **Approved observe**. Summaries in `status.json` (`account.*`). Secret stays `/dev/shm/momento-kalshi-nba-001.json` |
| `probe` / `evidence` on an authorized host with `MOMENTO_KALSHI_SECRET_FILE` | GET-only; do not copy the file into git or chat |
| Kalshi MCP in this authoring session | `has_credentials=false` — **not** a second account view |
| Operator laptop Kalshi keys | must not be assumed to be the NBA shard |

If the reviewer has no SSM and no LS: account integers are **UNAVAILABLE** to them; they must not invent `$20` / `$57.41` from this document as live truth without re-reading the host.

## What this authoring session could do vs Codex

| Check | Here | Typical Codex without extra creds |
|---|---|---|
| GitHub source + cargo test | yes | if repo access |
| STS + SSM describe | yes (this laptop's AWS CLI) | **blocker: no inherited AWS** |
| SSM command output | yes (recorded in this folder) | **blocker** unless IAM + SSM |
| Host secret / signed raw Kalshi JSON | not read | must stay unread |
| Kalshi MCP portfolio | unauthenticated | same unless reviewer configures keys (may be the **wrong** account) |

## Blockers to name, not work around

1. No AWS credentials in the reviewer environment → cannot refresh host evidence.
2. No `VITAL_AWS_CONTROL` + confirmation → cannot drain MLB/WNBA (correct).
3. No current-season P5 evidence URLs → NCAAB stays blocked.
4. Owner has not named `emergency_floor_cents` → ARMED stays blocked.
