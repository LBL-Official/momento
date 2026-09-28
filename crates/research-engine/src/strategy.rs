//! Strategy catalog for the console. B1 implements the hold-to-settlement family.
//! Parameters live on experiments, not in this file as trading rules.

use serde::Serialize;

#[derive(Clone, Debug, Serialize)]
pub struct ParameterDoc {
    pub name: &'static str,
    pub group: &'static str,
    pub kind: &'static str,
    pub notes: &'static str,
}

pub fn b1_parameter_catalog() -> Vec<ParameterDoc> {
    vec![
        ParameterDoc {
            name: "start_price_band",
            group: "START_BELIEF",
            kind: "categorical",
            notes: "Opening TRADE band. 40_49 is the published candidate benchmark.",
        },
        ParameterDoc {
            name: "p_start_lt50",
            group: "START_BELIEF",
            kind: "binary",
            notes: "YES if p_start < 50.",
        },
        ParameterDoc {
            name: "inning_grp",
            group: "BASEBALL_STATE",
            kind: "categorical",
            notes: "1_3, 4_5, 6, 7, 8, 9, EXTRA.",
        },
        ParameterDoc {
            name: "inning_exact",
            group: "BASEBALL_STATE",
            kind: "range",
            notes: "Integer inning. Use kind=range with min/max/step.",
        },
        ParameterDoc {
            name: "p_max_vs_83",
            group: "PATH",
            kind: "categorical",
            notes: "PEAK_AT / PEAK_ABOVE / PEAK_BELOW versus 83¢.",
        },
        ParameterDoc {
            name: "vol_1m_tertile",
            group: "VOLATILITY",
            kind: "ordinal",
            notes: "TRAIN tertile LOW/MID/HIGH.",
        },
        ParameterDoc {
            name: "vol_15m_tertile",
            group: "VOLATILITY",
            kind: "ordinal",
            notes: "TRAIN tertile LOW/MID/HIGH.",
        },
        ParameterDoc {
            name: "lead_ge2",
            group: "BASEBALL_STATE",
            kind: "binary",
            notes: "YES if bound-team lead ≥ 2.",
        },
        ParameterDoc {
            name: "personality",
            group: "PATH",
            kind: "categorical",
            notes: "TRENDING / CHOPPY / REVERSING / …",
        },
        ParameterDoc {
            name: "move_fine",
            group: "PATH",
            kind: "categorical",
            notes: "Start-to-entry move buckets.",
        },
    ]
}
