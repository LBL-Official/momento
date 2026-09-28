# CTO-W1 documentation directory

**Path note (FLAG-016):** On this Darwin volume `W1/` and `w1/` are the **same directory**. W1 implementation docs and the control-plane six-file package share this folder. That is an ownership collision, not a merge of meaning.

**Control-plane status:** VALIDATING until CTO signs `W1_ACCEPTANCE_PACKAGE.md`  
**W1 agent:** **10/10 PASS** evidence pack — [ACCEPTANCE_CANDIDATE.md](ACCEPTANCE_CANDIDATE.md) (FLAG-001/002/003 addressed in code). CTO call is still required.

## Control-plane package (CTO)

| Doc | Role |
|-----|------|
| [SPEC.md](SPEC.md) | Objective, inputs, outputs |
| [DEPENDENCIES.md](DEPENDENCIES.md) | Upstream / downstream / blockers |
| [CONTRACTS.md](CONTRACTS.md) | Contracts owned or consumed |
| [ACCEPTANCE.md](ACCEPTANCE.md) | Done-when (control plane) |
| [PROGRESS.md](PROGRESS.md) | Control-plane ledger view |

## W1 implementation-agent package (do not delete)

| Doc | Role |
|-----|------|
| [ACCEPTANCE_CANDIDATE.md](ACCEPTANCE_CANDIDATE.md) | **10/10** evidence vs closeout bar |
| [ARCHITECTURE.md](ARCHITECTURE.md) | W1 raw-data control description |
| [LEDGER.md](LEDGER.md) | PLAN vs W1-LEDGER (IDs ≠ PLAN IDs) |
| [VALIDATION_REPORT.md](VALIDATION_REPORT.md) | Integrity + cargo commands |
| [COMPLETION_REPORT.md](COMPLETION_REPORT.md) | Agent candidate; not CTO signature |
| [REGISTRY_ID_MAPPING.md](REGISTRY_ID_MAPPING.md) | FLAG-001 alias table |
| [PBP_SOURCE_MATRIX.md](PBP_SOURCE_MATRIX.md) | PLAN-W1-A6 catalog only |
| [W2_HANDOFF.md](W2_HANDOFF.md) | Pointers W2 may read |
| [CROSS_WATERFALL_ISSUES.md](CROSS_WATERFALL_ISSUES.md) | XW-1…XW-6 |
| [DATA_DICTIONARY.md](DATA_DICTIONARY.md) | W1 field notes |
| [COVERAGE.md](COVERAGE.md) / [PROVENANCE.md](PROVENANCE.md) / [OBSERVABILITY.md](OBSERVABILITY.md) | W1 vocab write-ups |

Derived artifacts (outside Data-Real): `Backtesting Suite/Foundation/W1/`

Control plane: [../WATERFALL_MASTER_REGISTRY.md](../WATERFALL_MASTER_REGISTRY.md) · [../CTO_REVIEW_FLAGS.md](../CTO_REVIEW_FLAGS.md)
