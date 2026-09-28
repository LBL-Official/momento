"""What each system actually does today. Do not invent features."""

from __future__ import annotations

LOGIC_NOTES: dict[str, str] = {
    "database": (
        "ROLLER warehouse + research_query. Canonical PIT memory. "
        "Confirm and Run is /warehouse-research. Does not decide trades. "
        "first80.py is a frozen loader, not a live signal."
    ),
    "data_analysis": (
        "SuperASI A Base → B Debase → Final → ITI. Decomposes measured "
        "populations. Path and terminal numbers it publishes are analysis "
        "outputs, not second-round model ownership. Research only."
    ),
    "fair_odds_modeling": (
        "Ontologic X on #/ontologic-x. The active book is BetOnline, labeled on every quote. "
        "William Hill remains a separate provider. A scheduled game stays when BetOnline has not posted a price. "
        "The offline lifecycle object stays model none."
    ),
    "in_house_odds_modeling": (
        "Ontologic Y on #/ontologic-y. XIB-NBA-V1 was found and is MODEL_INCOMPATIBLE. "
        "Probabilities stay unavailable. The lifecycle object stays NOT_IMPLEMENTED. "
        "Phase 7 F_t vs K_t is NOT AUTHORIZED."
    ),
    "trade_breakdown": (
        "Choosin Texas locked 80/40 economics. N=936 derived four. "
        "Ledger EV = 20S − L(1−S). 40-stop is a legacy benchmark. "
        "Candle path is not a fill."
    ),
    "position_stratification": (
        "Austin PCA+KNN on N=604 at #/austin. Classifies neighborhood / stratum. "
        "Never BUY/SKIP. Live feed UNAVAILABLE."
    ),
    "hedging_analysis": (
        "PARTIAL. Ballhog :5192 is the product Frontend (WHEN / q* / rho* / Δ*). "
        "BDR #/bdr remains the write-up library, not a 20th system. "
        "Austin 41/42 opponent-YES@40 maker and Family E features exist. "
        "LONG YES then BUY NO as taker is not implemented. Does not submit."
    ),
    "relative_value_hedging": (
        "PARTIAL. TK Ultra #/tk-ultra is the Frontend. "
        "tk_relative_value_v1 compiles a relationship into one signed tick number. "
        "Not a live hedge. Missing wing or beta is SOURCE_UNAVAILABLE. "
        "Futures formula is not assumed true for binaries."
    ),
    "data_modeling": (
        "Jump Drive organizes ROLLER + SuperASI pointers into path-efficiency "
        "research objects. Frontend is ?app=jump. Not a bot manager. "
        "Choosin Dallas is path evidence, not a Jump box."
    ),
    "game_modeling": (
        "Empirical SuperASI terminal decomp. XIB residual vs market is blocked. "
        "base_terminal_efficiency is Database measurement, not this system."
    ),
    "dynamic_risk_engine": (
        "Drevo :5191. Canonical Dynamic Risk Engine. Legacy alias DRE / /dre. "
        "V1 portfolio objective: preserve αP > 0, then ΔP → ΔP*(Xt). "
        "Forward feed: Choosin Texas + Austin, plus Positman plan gate. "
        "Phase 3 downfall is not an execution policy. Not crates/risk. "
        "Do not fake a hazard model. Do not invent Λα or ACCEPT thresholds."
    ),
    "position_management": (
        "Positman :5194 /positman. Deterministic compositor of Ballhog q* "
        "and TK Ultra route. Does not recompute siblings. Does not submit. "
        "target_from_research remains the old momento lifecycle fixture."
    ),
    "signal_generation": (
        "Stryke :5195 /stryke. FIRST78 78/67 signal sheet from the Jump folder. "
        "The bot contract reads it and stays NOT_DEPLOYED. first80.py stays frozen."
    ),
    "algorithmic_execution": (
        "NO NBA SUBMISSION IMPLEMENTATION. NBA Bot 001 (nba-001, alias "
        "nba-first80-001, FIRST78_67) runs as momento-nba-001.service: production "
        "data, GET-only account observe, local intents, SHADOW hedge path. No "
        "submission adapter is linked. The desk at /momento/execution/nba reads "
        "its status over read-only SSM. submits=false. "
        "MLB 001 is reference_only. Do not modify it. Do not submit orders."
    ),
    "momento_systems": (
        "Champion architecture box: registry + /momento façade + bracket UI. "
        "Not a prediction model. Not System Orchestration (bottom-layer runtime). "
        "Jump is a submodule, not a 20th system."
    ),
    "system_maintenance": (
        "Systimo Frontend :5193 /systimo on :8791. Registers tunnels and the "
        "transition audit loop (traces, hash chain, ORCHESTRA_CONTEXT). "
        "Does not own Austin/Choosin/Vital data. Momento LS :5181/:8792 remains the "
        "live-host observe adapter. UNKNOWN if unread. No fake green. "
        "ROLLER/roller/maintenance is ingest, not this system."
    ),
    "data_ingestion": (
        "Ingest scripts, auto_roller, research-ingest, maintenance/update.py. "
        "Autojest is NOT IMPLEMENTED. Polymarket is LAST_TRADE_PRINT."
    ),
    "trade_reconciliation": (
        "NOT IMPLEMENTED. Observe-only PositionReconciliation contract. "
        "UNKNOWN until exchange state is read. Not Vital. Not an OMS. "
        "Does not invent fills. Does not submit."
    ),
    "system_orchestration": (
        "DECLARED as Orchestra. No Orchestra application in V0. "
        "Systimo ORCHESTRA_CONTEXT is the query contract. "
        "Bottom-layer runtime job and pipeline orchestration remains NOT_IMPLEMENTED. "
        "Distinct from champion Momento Systems. Does not submit. "
        "Do not start momento-live.service."
    ),
}
