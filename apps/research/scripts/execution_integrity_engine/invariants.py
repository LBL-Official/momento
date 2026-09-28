"""Research-integrity gates. Fail the run if any break."""

from __future__ import annotations

from .enums import E1, GAP_THROUGH, L4


def check(trades: list[dict], sport: str, expected_n: int) -> list[dict]:
    fails = []
    if len(trades) != expected_n:
        fails.append(
            {
                "id": "INV5_UNIVERSE",
                "ok": False,
                "detail": f"{sport} n={len(trades)} expected={expected_n}",
            }
        )
    else:
        fails.append({"id": "INV5_UNIVERSE", "ok": True, "detail": f"{sport} n={expected_n}"})

    for i, t in enumerate(trades):
        if t.get("evidence_level_l4_claimed") == L4:
            fails.append({"id": "INV1_NO_FAKE_L4", "ok": False, "detail": t["trade_id"]})
            break
        if t.get("pnl_e1") is not None and not t.get("execution_model_e1"):
            fails.append({"id": "INV3_MODEL_ID", "ok": False, "detail": t["trade_id"]})
            break
        if (
            t.get("opportunity_class") == GAP_THROUGH
            and t.get("e1_hedge_filled")
            and t.get("e1_hedge_price") == t.get("threshold")
            and t.get("e1_observed_in_band") is False
        ):
            fails.append({"id": "INV2_NO_GAP_FILL_E1", "ok": False, "detail": t["trade_id"]})
            break
    else:
        fails.append({"id": "INV1_NO_FAKE_L4", "ok": True})
        fails.append({"id": "INV3_MODEL_ID", "ok": True})
        fails.append({"id": "INV2_NO_GAP_FILL_E1", "ok": True})

    # lookahead: V3 adapter already excludes t<=entry; assert entry_ts <= first_touch when present
    leak = 0
    for t in trades:
        e = t.get("entry_ts")
        h = t.get("hedge_signal_ts")
        if e is not None and h is not None:
            try:
                if int(h) <= int(e):
                    leak += 1
            except (TypeError, ValueError):
                pass
    fails.append(
        {
            "id": "INV6_NO_LOOKAHEAD",
            "ok": leak == 0,
            "detail": f"same_or_prior_bar_touches={leak}",
        }
    )
    return fails


def require_e1_not_l4():
    assert E1 != L4
