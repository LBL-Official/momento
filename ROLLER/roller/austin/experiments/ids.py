"""Fail-closed experiment identities. H2_2 is forbidden."""

from __future__ import annotations

from roller.austin.errors import AustinError
from roller.choosin_texas.locks import PARTITIONS

SUITE_ID = "AUSTIN_NCAAB_TRANSFER_V1"
EXPERIMENT_A = "NCAAB_H1_2_AUSTIN_TRANSFER_V1"
EXPERIMENT_B = "NCAAB_H2_1_AUSTIN_TRANSFER_V1"
AUDIT_ID = "AUSTIN_PERSISTENCE_MECHANISM_AUDIT_V1"
PHASE2_ID = "AUSTIN_PERSISTENCE_MECHANISM_V1"
PHASE3_ID = "AUSTIN_DOWNFALL_STATE_MODEL_V1"
PHASE3_PHASE = "AUSTIN_DRE_PHASE_3"
PHASE4_ID = "AUSTIN_LOSS_HAZARD_RECOVERY_MODEL_V1"
PHASE4_PHASE = "AUSTIN_DRE_PHASE_4"
PHASE5_ID = "AUSTIN_DRE_POLICY_V2"
PHASE5_PHASE = "AUSTIN_DRE_PHASE_5A"
PHASE6_ID = "AUSTIN_CONFIRMATION_GATE_V1"
PHASE6_PHASE = "AUSTIN_DRE_PHASE_6"
PHASE7_ID = "AUSTIN_NBA_2026_27_PROSPECTIVE_V1"
PHASE7_PHASE = "AUSTIN_DRE_PHASE_7"
MEMBERS = (EXPERIMENT_A, EXPERIMENT_B)

SLICE_A = "H1_2"
SLICE_B = "H2_1"
ALLOWED_SLICES = frozenset({SLICE_A, SLICE_B})
FORBIDDEN_SLICES = frozenset({"H2_2", "H1_1", "H2_2ND10", "2ND10"})
FORBIDDEN_IDS = frozenset(
    {
        "NCAAB_2H_2ND10_AUSTIN_TRANSFER_V1",
        "NCAAB_H2_2_AUSTIN_TRANSFER_V1",
    }
)

N_A = 193
N_B = 139
N_UNION = 332

LOCK_A = next(p for p in PARTITIONS if p.partition_id == "ncaab_h1_2")
LOCK_B = next(p for p in PARTITIONS if p.partition_id == "ncaab_h2_1")

PAGE3_N = 280
PAGE3_S = "218/280"
PAGE3_EV_CENTS = 6.7143
PAGE3_BOOK_CENTS = 1880
PAGE3_ROLE = "DISPLAY_ONLY_NOT_AUSTIN_COHORT"

CSV_SPORT = "NCAAB"
OBSERVATION_SCHEDULE = "EVERY_2_GAME_CLOCK_MINUTES"
EV_DEFINITION = "hold_80_to_settlement"
CI_METHOD = "weighted_bootstrap"
BOOTSTRAP_SEED = 80
BOOTSTRAP_B = 1000
LOW_SUPPORT_MEDIAN_DISTANCE = 2.5
DETERIORATION_X_CENTS = 8.0
FEE_MODEL = "UNAVAILABLE"
FILL_STATUS = "FILL_UNAVAILABLE"
EXECUTION = "DISABLED"
LIVE_FEED = "UNAVAILABLE"
ENTRY_SOURCE = "ASKED_SIX_FIRST80"
CLOCK_SPORT = "NCAAB"

EXPERIMENT_BY_SLICE = {SLICE_A: EXPERIMENT_A, SLICE_B: EXPERIMENT_B}
SLICE_BY_EXPERIMENT = {EXPERIMENT_A: SLICE_A, EXPERIMENT_B: SLICE_B}
N_BY_EXPERIMENT = {EXPERIMENT_A: N_A, EXPERIMENT_B: N_B}
LOCK_BY_EXPERIMENT = {EXPERIMENT_A: LOCK_A, EXPERIMENT_B: LOCK_B}


def assert_experiment_id(experiment_id: str) -> str:
    text = str(experiment_id or "").strip()
    if text in FORBIDDEN_IDS or "2ND10" in text or "H2_2" in text:
        raise AustinError("QUERY_REJECTED", f"forbidden experiment id {text}")
    if text not in MEMBERS:
        raise AustinError("QUERY_REJECTED", f"unknown experiment {text}")
    return text


def assert_suite_id(suite_id: str) -> str:
    text = str(suite_id or "").strip()
    if text != SUITE_ID:
        raise AustinError("QUERY_REJECTED", f"unknown suite {text}")
    return text


def assert_slice(slice_name: str) -> str:
    text = str(slice_name or "").strip()
    if text in FORBIDDEN_SLICES or text == "H2_2":
        raise AustinError("LOCK_MISMATCH", f"forbidden slice {text}")
    if text not in ALLOWED_SLICES:
        raise AustinError("LOCK_MISMATCH", f"slice {text} is not a locked transfer population")
    return text
