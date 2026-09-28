# Momento Systems — Bracket

The bracket is the conceptual architecture and, in Phase 3, the navigation UI.

Visual spec for Phase 3 (no screenshot is in-repo; this text is the authority
until a screenshot is supplied):

```text
background: #34777B
boxes:      #131313
text:       #FFFFFF
border:     1px near-white
radius:     0
shadow:     none
font:       compact sans-serif
```

Do not redesign this into a SaaS dashboard. Do not use ROLLER styling.
Do not add extra cards on the main bracket.

## Tournament

```text
DATABASE                    TRADE BREAKDOWN
DATA ANALYSIS               POSITION STRATIFICATION
        \                           \
         > DATA MODELING             > DYNAMIC RISK ENGINE
        /                           /
FAIR ODDS MODELING          HEDGING ANALYSIS
IN HOUSE ODDS MODELING      RELATIVE VALUE HEDGING
        \                           \
         > GAME MODELING             > POSITION MANAGEMENT
        /                           /

DATA MODELING               DYNAMIC RISK ENGINE
        \                           \
         > SIGNAL GENERATION         > ALGORITHMIC EXECUTION
        /                           /   (Momento Live Trading Bot)
GAME MODELING               POSITION MANAGEMENT
                \
                 > MOMENTO SYSTEMS
                /
        ALGORITHMIC EXECUTION
```

Outside the bracket:

```text
SYSTEM MAINTENANCE          DATA INGESTION
TRADE RECONCILIATION        SYSTEM ORCHESTRATION
```

## Machine edges

Defined in [`ROLLER/roller/momento/bracket.py`](../../ROLLER/roller/momento/bracket.py).

14 tournament edges plus `data_ingestion → database`.
System Maintenance, Trade Reconciliation, and System Orchestration have
no producer edges.

The graph is acyclic. Tests assert that.

## Box labels

Database, Data Analysis, Data Modeling, Fair Odds Modeling,
In House Odds Modeling, Game Modeling, Signal Generation, Momento Systems,
Algorithmic Execution, Dynamic Risk Engine, Position Stratification,
Trade Breakdown, Position Management, Hedging Analysis,
Relative Value Hedging, System Maintenance, Data Ingestion,
Trade Reconciliation, System Orchestration.

Algorithmic Execution carries subtitle `(Momento Live Trading Bot)`.

## Click behavior (Phase 3)

Each box opens Backend / Frontend. Routes come from the registry.
Do not hardcode routing in the visual component.
Phase 3 is not started.
