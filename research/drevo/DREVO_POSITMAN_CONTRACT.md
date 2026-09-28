# Drevo ← Positman contract

Drevo reads public `positman.plan.v0` via `roller.dre.positman_adapter.read_plan`.
It does not import Ballhog or TK Ultra adapters.

If the plan is structurally valid, `decision_status=POLICY_UNRESOLVED`.
If identity/schema/qty/route fail, `REJECT`. `execution_authorized` is always false.
