"""Pinned Phase 5A artifact hashes. Phase 5B must not rewrite these files."""

from __future__ import annotations

PHASE5A_REQUIRED = (
    "MANIFEST.json",
    "POLICY_CANDIDATES.json",
    "candidate_discovery_events.csv",
    "candidate_economics_A.csv",
    "candidate_economics_B.csv",
    "candidate_comparison.csv",
    "first_intervention_events.csv",
    "timing_analysis.csv",
    "winner_sacrifice_analysis.csv",
    "loss_avoidance_analysis.csv",
    "dre_value_added.csv",
    "statistics.json",
    "model_lock_audit.json",
    "phase2_finalization_audit.json",
    "phase3_finalization_audit.json",
    "phase4_finalization_audit.json",
    "hazard_schema_audit.json",
    "cohort_hash_audit.json",
    "leakage_audit.json",
    "confirmation_protection_audit.json",
    "candidate_registry_audit.json",
    "REPORT.md",
)

PHASE5A_FILE_HASHES = {
    "MANIFEST.json": "e4411921abd92c077f0643def1fc8bd92c8e0a758ac753a5df98d96ebd483749",
    "POLICY_CANDIDATES.json": "e9816a29be6b24550e2712e7b81d9003be3ff518f60e237ad422ecfd9903f276",
    "candidate_discovery_events.csv": "313402d26ef31efaffafef65c2256af343157412bfefe1ab7080fe9ae629fdfa",
    "candidate_economics_A.csv": "2aa468799ce7ea616ab1203e990d2c5453e0e12f4da1b74b34c604a3dca2becb",
    "candidate_economics_B.csv": "9a3f62029a69c10b4c6bb5f177cdd2bba8a0c528685587951f98e503ea9d48b0",
    "candidate_comparison.csv": "57530ff2bc7e79d56f9a4689889de09f404944c6fdeb8c65ccbe56d10ac5532e",
    "first_intervention_events.csv": "e6ee03bff17f2a7170e76cecb4e9ee98ea2cb571b3596a3822d173f6872cacb7",
    "timing_analysis.csv": "bdf951f95d74f82e178d6c38c811366f705e7d5b13fec1e2a4fadb0f6301f08e",
    "winner_sacrifice_analysis.csv": "9291109fa5d1ff968072c059d043565c9a5e750da9381c71e10e6bbc2c92bb75",
    "loss_avoidance_analysis.csv": "fb314f5c693a481a51d20dca09f308a48d7b7fe9678c8c7ae786814faf8e7306",
    "dre_value_added.csv": "8d876dbf298c74d41a352413b91b19c897122ec1b9321b6ca6da185a87f41b58",
    "statistics.json": "0add293e0c97c773b0c7893ee3f679802ab27d19185e9ac91771261ed502f88c",
    "model_lock_audit.json": "46d7155811dadbdc7bfb76fb86f4475f64fa49375e5a29ed79a7a816c45a2a1f",
    "phase2_finalization_audit.json": "7fb21f5ed803f03bb1afcc10eac06b51f9d83b400856b9e59c68911cde006532",
    "phase3_finalization_audit.json": "b321004fc28251faebd4760ec0b7f244b625ee40f53ddc6274073f0ff6fb28c7",
    "phase4_finalization_audit.json": "e90eaf136d0b9767b4eb4d0d7e461650af2bebb51bd4d9281fc9cdaab7b4f9f9",
    "hazard_schema_audit.json": "393e4453b2a789322e86ee64c30d88196e8ed3db5e2cee8ce4781deef4aa76e5",
    "cohort_hash_audit.json": "8c2bc793986e8a60877fdccb7e993bfaab137764e8d7e6fa13e6caddfb6af2ec",
    "leakage_audit.json": "d8145e1755fc69e395892ac10a2a1be634a0b30417aadff5e62f1c6e5e7eb763",
    "confirmation_protection_audit.json": "227a64dacfbcfc65e47164f24f8d752dde9ca42bc50f18aa3cca134d40f167bf",
    "candidate_registry_audit.json": "3a9d7606c1bbe1197ab3a2bd50d5d40243c55b51aa00b26c5e8b6b457359bfa9",
    "REPORT.md": "be9a44c410d843f6761ee38f0abe665c3d42c90473f90e0cf2fbddaf5d32524b",
}

CANDIDATE_REGISTRY_HASH = PHASE5A_FILE_HASHES["POLICY_CANDIDATES.json"]
PHASE5A_MANIFEST_HASH = PHASE5A_FILE_HASHES["MANIFEST.json"]
