//! Parameterized B1 HOLD_TO_SETTLEMENT search.
//!
//! Wraps existing flatten / enrich / eval_screen / BH FDR / classify.
//! Does not change exhaustive-search methodology. Research only.

use std::collections::BTreeMap;
use std::path::PathBuf;

use serde::{Deserialize, Serialize};

use crate::a1_targets::EXIT_HOLD_TO_SETTLEMENT;
use crate::error::B1Error;
use crate::search::{
    ChronoSplit, FILL_STATUS, SearchRow, SplitMetrics, attach_train_tertiles, flatten, metrics,
    p_mean_le0,
};
use crate::search_83::{
    Cond83, attach_83_tertiles, cond_ok, enrich, eval_screen, label, parse_cond,
};
use crate::search_83_exh::{
    ExhaustiveArgs, assert_no_leakage, bh_qvalues, classify, enrich_exh, game_pnls,
};
use crate::search_83_opt::enrich_opt;
use crate::splits::{TRAIN_BEFORE, VAL_BEFORE, apply_configured_chrono_split};
use crate::store::FeatureStore;
use crate::types::B1EntrySnapshot;

const PRIMARY: &str = EXIT_HOLD_TO_SETTLEMENT;

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ParameterSpec {
    pub name: String,
    #[serde(default)]
    pub values: Vec<String>,
    /// `list` (default) or `range` (min/max/step → integer strings).
    #[serde(default)]
    pub kind: String,
    #[serde(default)]
    pub min: Option<i32>,
    #[serde(default)]
    pub max: Option<i32>,
    #[serde(default)]
    pub step: Option<i32>,
}

impl ParameterSpec {
    pub fn list(name: impl Into<String>, values: Vec<String>) -> Self {
        Self {
            name: name.into(),
            values,
            kind: "list".into(),
            min: None,
            max: None,
            step: None,
        }
    }

    pub fn resolved_values(&self) -> Result<Vec<String>, B1Error> {
        if self.kind == "range" {
            let min = self.min.ok_or_else(|| {
                B1Error::validation("RANGE", format!("{} missing min", self.name))
            })?;
            let max = self.max.ok_or_else(|| {
                B1Error::validation("RANGE", format!("{} missing max", self.name))
            })?;
            let step = self.step.unwrap_or(1);
            if step <= 0 || max < min {
                return Err(B1Error::validation(
                    "RANGE",
                    format!("{} has invalid range {min}..={max} step {step}", self.name),
                ));
            }
            let mut out = Vec::new();
            let mut x = min;
            while x <= max {
                out.push(x.to_string());
                x = x.saturating_add(step);
                if out.len() > 10_000 {
                    return Err(B1Error::validation("RANGE", "range expanded past 10000"));
                }
            }
            return Ok(out);
        }
        if self.values.is_empty() {
            return Err(B1Error::validation(
                "EMPTY_PARAM",
                format!("parameter {} has no values", self.name),
            ));
        }
        Ok(self.values.clone())
    }
}

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct ConfiguredSearchSpec {
    pub features_sqlite: PathBuf,
    pub train_before: String,
    pub val_before: String,
    pub parameters: Vec<ParameterSpec>,
    pub include_unconditional: bool,
    pub min_train: usize,
    pub min_val: usize,
    pub min_test: usize,
    pub fdr_alpha: f64,
}

impl Default for ConfiguredSearchSpec {
    fn default() -> Self {
        Self {
            features_sqlite: PathBuf::from(
                "Backtesting Suite/Foundation/B1/first83/features.sqlite",
            ),
            train_before: TRAIN_BEFORE.into(),
            val_before: VAL_BEFORE.into(),
            parameters: Vec::new(),
            include_unconditional: true,
            min_train: 50,
            min_val: 10,
            min_test: 15,
            fdr_alpha: 0.10,
        }
    }
}

#[derive(Clone, Debug, Serialize)]
pub struct SplitBlock {
    pub n: usize,
    pub win_rate: Option<f64>,
    pub ev_cents: Option<f64>,
    pub sharpe: Option<f64>,
    pub pnl_usd: f64,
    pub max_dd_usd: f64,
}

impl SplitBlock {
    fn from_metrics(m: &SplitMetrics) -> Self {
        Self {
            n: m.n_unique_games,
            win_rate: m.win_rate,
            ev_cents: m.ev_cents,
            sharpe: m.sharpe_game_unann,
            pnl_usd: m.total_pnl_usd,
            max_dd_usd: m.max_dd_usd,
        }
    }
}

#[derive(Clone, Debug, Serialize)]
pub struct EquityPoint {
    pub date: String,
    pub split: &'static str,
    pub pnl_usd: f64,
    pub cumulative_usd: f64,
}

#[derive(Clone, Debug, Serialize)]
pub struct HypothesisRow {
    pub rank: u32,
    pub condition: String,
    pub depth: u8,
    pub train: SplitBlock,
    pub validation: SplitBlock,
    pub test: SplitBlock,
    pub all: SplitBlock,
    pub p_value: Option<f64>,
    pub q_value: Option<f64>,
    pub classification: String,
    pub ev_lift_test: Option<f64>,
    pub equity: Vec<EquityPoint>,
}

#[derive(Clone, Debug, Serialize)]
pub struct ConfiguredSearchReport {
    pub n_83: usize,
    pub unique_games: usize,
    pub fill_status: &'static str,
    pub train_before: String,
    pub val_before: String,
    pub test_end: String,
    pub hypotheses_requested: usize,
    pub hypotheses_executed: usize,
    pub hypotheses_excluded: usize,
    pub number_of_tests: usize,
    pub fdr_method: &'static str,
    pub fdr_alpha: f64,
    pub correction_method: &'static str,
    pub unconditional: HypothesisRow,
    pub hypotheses: Vec<HypothesisRow>,
    pub feature_values: BTreeMap<String, Vec<String>>,
}

pub fn cartesian_product(params: &[ParameterSpec]) -> Result<Vec<Vec<(String, String)>>, B1Error> {
    if params.is_empty() {
        return Ok(vec![Vec::new()]);
    }
    for p in params {
        assert_no_leakage(&[(p.name.clone(), String::new())])?;
        let _ = p.resolved_values()?;
    }
    let mut acc: Vec<Vec<(String, String)>> = vec![Vec::new()];
    for p in params {
        let values = p.resolved_values()?;
        let mut next = Vec::new();
        for stem in &acc {
            for v in &values {
                let mut row = stem.clone();
                row.push((p.name.clone(), v.clone()));
                next.push(row);
            }
        }
        acc = next;
        if acc.len() > 50_000 {
            return Err(B1Error::validation(
                "GRID_TOO_LARGE",
                format!("cartesian product exceeded 50000 (got {})", acc.len()),
            ));
        }
    }
    Ok(acc)
}

pub fn estimate_hypothesis_count(params: &[ParameterSpec]) -> usize {
    if params.is_empty() {
        return 1;
    }
    params
        .iter()
        .map(|p| p.resolved_values().map(|v| v.len().max(1)).unwrap_or(0))
        .product()
}

pub type PreparedRows = (
    Vec<SearchRow>,
    String,
    String,
    String,
    BTreeMap<String, Vec<String>>,
);

pub fn prepare_search_rows(
    features_sqlite: &std::path::Path,
    train_before: &str,
    val_before: &str,
) -> Result<PreparedRows, B1Error> {
    if !features_sqlite.exists() {
        return Err(B1Error::Uncommitted(format!(
            "features.sqlite missing at {}",
            features_sqlite.display()
        )));
    }
    let store = FeatureStore::open_existing(features_sqlite)?;
    let snaps = store.load_all()?;
    let mut dated: Vec<SearchRow> = snaps.iter().map(flatten).collect();
    let (train_cut, val_cut, test_end) =
        apply_configured_chrono_split(&mut dated, train_before, val_before);
    let snaps83: Vec<B1EntrySnapshot> = snaps
        .iter()
        .filter(|s| s.entry_trade_price_cents == 83)
        .cloned()
        .collect();
    let mut rows: Vec<SearchRow> = dated.into_iter().filter(|r| r.entry_cents == 83).collect();
    if snaps83.is_empty() {
        return Err(B1Error::validation("NO_83", "no ENTRY_83 snapshots"));
    }
    attach_train_tertiles(&mut rows, &snaps83);
    attach_83_tertiles(&mut rows, &snaps83);
    for (r, s) in rows.iter_mut().zip(snaps83.iter()) {
        enrich(r, s);
        enrich_opt(r, s);
        enrich_exh(r, s);
        assert_no_leakage(
            &r.feats
                .keys()
                .map(|k| (k.clone(), String::new()))
                .collect::<Vec<_>>(),
        )?;
    }
    let feature_values = observed_values(&rows);
    Ok((rows, train_cut, val_cut, test_end, feature_values))
}

fn observed_values(rows: &[SearchRow]) -> BTreeMap<String, Vec<String>> {
    let mut map: BTreeMap<String, std::collections::BTreeSet<String>> = BTreeMap::new();
    for r in rows.iter().filter(|r| r.chrono == ChronoSplit::Train) {
        for (k, v) in &r.feats {
            if v != "NA" && v != "UNAVAILABLE" {
                map.entry(k.clone()).or_default().insert(v.clone());
            }
        }
    }
    map.into_iter()
        .map(|(k, vs)| (k, vs.into_iter().collect()))
        .collect()
}

fn equity_curve(rows: &[SearchRow], cond: &[(String, String)]) -> Vec<EquityPoint> {
    let mut hits: Vec<&SearchRow> = rows.iter().filter(|r| cond_ok(r, cond)).collect();
    hits.sort_by(|a, b| a.date.cmp(&b.date).then_with(|| a.game_id.cmp(&b.game_id)));
    let mut cum = 0.0;
    let mut out = Vec::new();
    for r in hits {
        let ret = r.exit_ret.get(PRIMARY).copied().unwrap_or(0);
        let pnl = f64::from(ret * r.qty) / 100.0;
        cum += pnl;
        out.push(EquityPoint {
            date: r.date.clone(),
            split: r.chrono.as_str(),
            pnl_usd: pnl,
            cumulative_usd: cum,
        });
    }
    out
}

fn to_row(
    c: &Cond83,
    rank: u32,
    q: Option<f64>,
    p: Option<f64>,
    class: String,
    equity: Vec<EquityPoint>,
) -> HypothesisRow {
    HypothesisRow {
        rank,
        condition: c.condition.clone(),
        depth: c.stage,
        train: SplitBlock::from_metrics(&c.train),
        validation: SplitBlock::from_metrics(&c.validation),
        test: SplitBlock::from_metrics(&c.test),
        all: SplitBlock::from_metrics(&c.all),
        p_value: p,
        q_value: q,
        classification: class,
        ev_lift_test: c.ev_lift_test,
        equity,
    }
}

/// Run a configured grid (or single/unconditional) search on an existing B1 store.
pub fn run_configured_search(
    spec: &ConfiguredSearchSpec,
) -> Result<ConfiguredSearchReport, B1Error> {
    run_configured_search_with_progress(spec, |_, _, _| Ok(()))
}

/// Same as [`run_configured_search`], reporting (done, total, current_label).
/// Return `Err` from the callback to cancel.
pub fn run_configured_search_with_progress<F>(
    spec: &ConfiguredSearchSpec,
    mut progress: F,
) -> Result<ConfiguredSearchReport, B1Error>
where
    F: FnMut(usize, usize, &str) -> Result<(), B1Error>,
{
    let (rows, train_cut, val_cut, test_end, feature_values) =
        prepare_search_rows(&spec.features_sqlite, &spec.train_before, &spec.val_before)?;
    let grid = cartesian_product(&spec.parameters)?;
    let mut conds: Vec<Vec<(String, String)>> = Vec::new();
    if spec.include_unconditional {
        conds.push(Vec::new());
    }
    for g in grid {
        if g.is_empty() && spec.include_unconditional {
            continue;
        }
        conds.push(g);
    }

    let all_rows: Vec<&SearchRow> = rows.iter().collect();
    let base_all = metrics(&all_rows, PRIMARY);
    let base_test = metrics(
        &rows
            .iter()
            .filter(|r| r.chrono == ChronoSplit::Test)
            .collect::<Vec<_>>(),
        PRIMARY,
    );

    let args = ExhaustiveArgs {
        min_train: spec.min_train,
        min_val: spec.min_val,
        min_test: spec.min_test,
        ..ExhaustiveArgs::default()
    };

    let requested = conds.len();
    let mut hold: Vec<Cond83> = Vec::new();
    let mut excluded = 0usize;
    for (i, cond) in conds.iter().enumerate() {
        progress(i, requested, &label(cond))?;
        assert_no_leakage(cond)?;
        match eval_screen(
            &rows,
            cond,
            cond.len() as u8,
            PRIMARY,
            &base_all,
            &base_test,
        ) {
            Some(c) => hold.push(c),
            None => excluded += 1,
        }
    }

    let mut pvals: Vec<(String, f64)> = Vec::new();
    for c in &hold {
        let tr = rows
            .iter()
            .filter(|r| r.chrono == ChronoSplit::Train && cond_ok(r, &parse_cond(&c.condition)))
            .collect::<Vec<_>>();
        let pnls = game_pnls(&tr, PRIMARY);
        if let Some(p) = p_mean_le0(&pnls) {
            pvals.push((c.condition.clone(), p));
        }
    }
    let qmap = bh_qvalues(&pvals);
    let pmap: BTreeMap<String, f64> = pvals.iter().cloned().collect();

    let mut hypotheses: Vec<HypothesisRow> = Vec::new();
    let mut unconditional = None;
    for (i, c) in hold.iter().enumerate() {
        let class = classify(c, &args, &qmap);
        let row = to_row(
            c,
            (i + 1) as u32,
            qmap.get(&c.condition).copied(),
            pmap.get(&c.condition).copied(),
            class,
            equity_curve(&rows, &parse_cond(&c.condition)),
        );
        if c.condition == "ALL_83" {
            unconditional = Some(row);
        } else {
            hypotheses.push(row);
        }
    }
    hypotheses.sort_by(|a, b| {
        b.validation
            .ev_cents
            .partial_cmp(&a.validation.ev_cents)
            .unwrap_or(std::cmp::Ordering::Equal)
    });
    for (i, h) in hypotheses.iter_mut().enumerate() {
        h.rank = (i + 1) as u32;
    }

    let uncond = unconditional.unwrap_or_else(|| {
        let empty: Vec<(String, String)> = Vec::new();
        HypothesisRow {
            rank: 0,
            condition: label(&empty),
            depth: 0,
            train: SplitBlock::from_metrics(&metrics(
                &rows
                    .iter()
                    .filter(|r| r.chrono == ChronoSplit::Train)
                    .collect::<Vec<_>>(),
                PRIMARY,
            )),
            validation: SplitBlock::from_metrics(&metrics(
                &rows
                    .iter()
                    .filter(|r| r.chrono == ChronoSplit::Validation)
                    .collect::<Vec<_>>(),
                PRIMARY,
            )),
            test: SplitBlock::from_metrics(&metrics(
                &rows
                    .iter()
                    .filter(|r| r.chrono == ChronoSplit::Test)
                    .collect::<Vec<_>>(),
                PRIMARY,
            )),
            all: SplitBlock::from_metrics(&base_all),
            p_value: None,
            q_value: None,
            classification: "BENCHMARK".into(),
            ev_lift_test: None,
            equity: equity_curve(&rows, &empty),
        }
    });

    Ok(ConfiguredSearchReport {
        n_83: rows.len(),
        unique_games: base_all.n_unique_games,
        fill_status: FILL_STATUS,
        train_before: train_cut,
        val_before: val_cut,
        test_end,
        hypotheses_requested: requested,
        hypotheses_executed: hold.len(),
        hypotheses_excluded: excluded,
        number_of_tests: pvals.len(),
        fdr_method: "Benjamini-Hochberg",
        fdr_alpha: spec.fdr_alpha,
        correction_method: "BH q on TRAIN P(mean P&L <= 0)",
        unconditional: uncond,
        hypotheses,
        feature_values,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn cartesian_is_product() {
        let params = vec![
            ParameterSpec::list("start_price_band", vec!["40_49".into(), "50_59".into()]),
            ParameterSpec::list("inning_grp", vec!["7".into()]),
        ];
        let g = cartesian_product(&params).unwrap();
        assert_eq!(g.len(), 2);
        assert_eq!(estimate_hypothesis_count(&params), 2);
    }

    #[test]
    fn leakage_rejected_in_grid() {
        let params = vec![ParameterSpec::list("settlement_win", vec!["YES".into()])];
        assert!(cartesian_product(&params).is_err());
    }

    #[test]
    fn identical_spec_is_deterministic() {
        let a = cartesian_product(&[
            ParameterSpec::list("start_price_band", vec!["40_49".into()]),
            ParameterSpec::list("inning_grp", vec!["7".into(), "8".into()]),
        ])
        .unwrap();
        let b = cartesian_product(&[
            ParameterSpec::list("start_price_band", vec!["40_49".into()]),
            ParameterSpec::list("inning_grp", vec!["7".into(), "8".into()]),
        ])
        .unwrap();
        assert_eq!(a, b);
        assert_eq!(a.len(), 2);
    }

    #[test]
    fn range_expands_integers() {
        let p = ParameterSpec {
            name: "inning_exact".into(),
            values: vec![],
            kind: "range".into(),
            min: Some(6),
            max: Some(9),
            step: Some(1),
        };
        assert_eq!(p.resolved_values().unwrap(), vec!["6", "7", "8", "9"]);
        assert_eq!(estimate_hypothesis_count(std::slice::from_ref(&p)), 4);
    }
}
