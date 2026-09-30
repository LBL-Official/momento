# Concise handoff (section 7)

Do not treat this page as an audit pass.

1. **Branch / implementation SHA:** `main` @ `2a22a2a2f7797f9d54b6372c6f4f8ccb5379bcc2`  
   URL: `https://github.com/LBL-Official/momento/commit/2a22a2a2f7797f9d54b6372c6f4f8ccb5379bcc2`

2. **Deployed code SHA:** unavailable as a git commit (GET-only binary `nba001-20260927T042347Z`).  
   **Deployed binary SHA-256:** `9ef129e1d8b1ee111666e80265d70cd3dad1ddfa3dd5017d9865b848e57d6789`

3. **Audit folder:** `docs/implementation/first78-live-v1/audit-handoff/2026-09-30/`  
   After push: `https://github.com/LBL-Official/momento/tree/main/docs/implementation/first78-live-v1/audit-handoff/2026-09-30`

4. **AWS:** account `895492487332`, `us-east-1`, `i-0f0849d5829476c31`.  
   Units: `momento-nba-001.service` (SHADOW), `momento-live.service` (Live MLB+WNBA).

5. **Access for Codex:** GitHub if granted. AWS/SSM/Kalshi **not inherited**. This laptop had STS+SSM; Kalshi MCP had no credentials. See `ACCESS_REQUIREMENTS.md`.

6. **Account (host GET, 2026-09-30T13:55:53Z):** `balance_total_cents=5797`, `portfolio_value_cents=0`, shard0 `5741`, shard3 `56`, positions empty, resting orders 0. **Not V1 RECONCILED.** Not a `$20`/`$20,000` fallback.

7. **Tests:** 121 + 67 (1 ignored) + 18 Kalshi. Performance bounds **not measured**. Gaps in `KNOWN_GAPS.md`.

8. **Terms**

| Term | Evidence |
|---|---|
| IMPLEMENTED | V1 source at `2a22a2a` |
| TESTED | local cargo totals above |
| CONNECTED | STS/SSM + host heartbeat |
| RECONCILED | no |
| DEPLOYED | **no** for V1; FIRST78_67 SHADOW is on disk |
| HEALTHY | not claimed |
| ARMED | no |
| EXECUTING | no |

PR: none created unless `main` cannot be pushed.
