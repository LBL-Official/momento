//! B1 CLI. Feature extraction and A1 bucket search. No network. Not live trading.

use momento_research_engine::jobs::JobService;
use momento_research_engine::types::ExperimentDefinition;
use momento_research_engine::{WorkspacePaths, open_engine};
use momento_research_features::{
    B1RunConfig, ExhaustiveArgs, ProspectiveArgs, SearchConfig, run_83_condition_search,
    run_83_exhaustive_search, run_83_optimal_search, run_b1_batch, run_bucket_search,
    run_capital_sim_only, run_first83_extract, run_prospective_validation,
    run_prospective83_engine, run_sixth_lead2_first80,
};
use tracing::info;
use tracing_subscriber::EnvFilter;

fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env().add_directive("info".parse().unwrap()))
        .init();
    let args: Vec<String> = std::env::args().collect();
    let mut cfg = B1RunConfig::defaults();
    let mut extract = false;
    let mut search = false;
    let mut search_83 = false;
    let mut search_83_opt = false;
    let mut search_83_exh = false;
    let mut extract_first83 = false;
    let mut first_exact_83 = false;
    let mut run_experiment: Option<String> = None;
    let mut validate_83_prospective = false;
    let mut capital_sim_only = false;
    let mut sixth_lead2_first80 = false;
    let mut prospective_start: Option<String> = None;
    let mut prospective_end: Option<String> = None;
    let mut exh = ExhaustiveArgs::default();
    let mut bootstrap = 10_000usize;
    let mut permutations = 2_000usize;
    let mut seed = 42u64;
    let mut candidate_set: Option<String> = None;
    let mut cost_grid: Option<String> = None;
    let mut i = 1usize;
    while i < args.len() {
        match args[i].as_str() {
            "--extract" | "--features" => {
                extract = true;
                i += 1;
            }
            "--search" => {
                search = true;
                i += 1;
            }
            "--search-83" => {
                search_83 = true;
                i += 1;
            }
            "--search-83-opt" => {
                search_83_opt = true;
                i += 1;
            }
            "--search-83-exhaustive" => {
                search_83_exh = true;
                i += 1;
            }
            "--extract-first83" => {
                extract_first83 = true;
                i += 1;
            }
            "--first-exact-83" => {
                first_exact_83 = true;
                i += 1;
            }
            "--run-experiment" => {
                run_experiment = Some(args.get(i + 1).expect("--run-experiment PATH").clone());
                i += 2;
            }
            "--validate-83-prospective" | "--prospective-83" => {
                validate_83_prospective = true;
                i += 1;
            }
            "--sixth-lead2-first80" | "--late-lead2-40" => {
                sixth_lead2_first80 = true;
                i += 1;
            }
            "--83-capital-sim" => {
                capital_sim_only = true;
                validate_83_prospective = true;
                i += 1;
            }
            "--prospective-start" => {
                prospective_start = Some(args.get(i + 1).expect("date").clone());
                i += 2;
            }
            "--prospective-end" => {
                prospective_end = Some(args.get(i + 1).expect("date").clone());
                i += 2;
            }
            "--seed" => {
                seed = args.get(i + 1).expect("seed").parse().expect("u64");
                i += 2;
            }
            "--candidate-set" => {
                candidate_set = Some(args.get(i + 1).expect("ids").clone());
                i += 2;
            }
            "--cost-grid" => {
                cost_grid = Some(args.get(i + 1).expect("cents").clone());
                i += 2;
            }
            "--max-interaction-depth" => {
                exh.max_depth = args.get(i + 1).expect("depth").parse().expect("u8");
                i += 2;
            }
            "--min-train" => {
                exh.min_train = args.get(i + 1).expect("n").parse().expect("n");
                i += 2;
            }
            "--min-val" => {
                exh.min_val = args.get(i + 1).expect("n").parse().expect("n");
                i += 2;
            }
            "--min-test" => {
                exh.min_test = args.get(i + 1).expect("n").parse().expect("n");
                i += 2;
            }
            "--bootstrap-reps" | "--bootstrap" => {
                let n = args.get(i + 1).expect("n").parse().expect("n");
                exh.bootstrap_reps = n;
                bootstrap = n;
                i += 2;
            }
            "--permutation-reps" | "--permutations" => {
                let n = args.get(i + 1).expect("n").parse().expect("n");
                exh.permutation_reps = n;
                permutations = n;
                i += 2;
            }
            "--recon" => {
                search = true;
                i += 1;
            }
            "--out" => {
                cfg.out_dir = args.get(i + 1).expect("--out PATH").into();
                i += 2;
            }
            "--lake" => {
                cfg.lake_root = args.get(i + 1).expect("--lake PATH").into();
                i += 2;
            }
            "--w8" => {
                cfg.w8_sqlite = args.get(i + 1).expect("--w8 PATH").into();
                i += 2;
            }
            "--w7" => {
                cfg.w7_sqlite = args.get(i + 1).expect("--w7 PATH").into();
                i += 2;
            }
            "--w6" => {
                cfg.w6_sqlite = args.get(i + 1).expect("--w6 PATH").into();
                i += 2;
            }
            "--identity" => {
                cfg.identity_landing = args.get(i + 1).expect("--identity PATH").into();
                i += 2;
            }
            "--max-entries" => {
                cfg.max_entries = Some(
                    args.get(i + 1)
                        .expect("--max-entries N")
                        .parse()
                        .expect("n"),
                );
                i += 2;
            }
            other => {
                eprintln!("unknown arg {other}");
                std::process::exit(2);
            }
        }
    }
    if let Some(path) = run_experiment {
        let def: ExperimentDefinition =
            serde_json::from_str(&std::fs::read_to_string(&path).expect("experiment json"))
                .expect("ExperimentDefinition");
        let paths = WorkspacePaths::detect();
        let store = std::sync::Arc::new(open_engine(&paths.root).expect("engine"));
        let jobs = JobService::new(store, paths);
        let exp = jobs.create_experiment(def).expect("create experiment");
        let job = jobs.queue_run(&exp.id).expect("queue");
        let done = jobs.execute_job(&job.id).expect("run experiment");
        info!(experiment = %exp.id, job = %done.id, status = %done.status, "research engine run");
        return;
    }
    if validate_83_prospective {
        let paths = WorkspacePaths::detect();
        let mut pargs = ProspectiveArgs::defaults(&paths.root);
        if let Some(s) = prospective_start {
            pargs.prospective_start = s;
        }
        pargs.prospective_end = prospective_end;
        pargs.bootstrap_reps = bootstrap;
        pargs.permutation_reps = permutations;
        pargs.seed = seed;
        if let Some(set) = candidate_set {
            pargs.candidate_set = Some(
                set.split(',')
                    .map(|s| s.trim().to_string())
                    .filter(|s| !s.is_empty())
                    .collect(),
            );
        }
        if let Some(grid) = cost_grid {
            pargs.cost_grid_cents = grid
                .split(',')
                .map(|s| s.trim().parse::<f64>().expect("cost cents"))
                .collect();
        }
        let d = B1RunConfig::defaults();
        if cfg.w6_sqlite != d.w6_sqlite {
            pargs.w6_sqlite = cfg.w6_sqlite.clone();
        }
        if cfg.w7_sqlite != d.w7_sqlite {
            pargs.w7_sqlite = cfg.w7_sqlite.clone();
        }
        if cfg.w8_sqlite != d.w8_sqlite {
            pargs.w8_sqlite = cfg.w8_sqlite.clone();
        }
        if cfg.out_dir != d.out_dir {
            pargs.out_dir = cfg.out_dir.clone();
        }
        let report = run_prospective_validation(&pargs).expect("prospective validation");
        if capital_sim_only {
            let path = run_capital_sim_only(&pargs).expect("capital sim");
            info!(path = %path.display(), "83¢ capital simulation");
        } else {
            let engine = run_prospective83_engine(&pargs).expect("prospective 83 engine");
            info!(
                headline = %engine["headline_status"],
                n = engine["integrity"]["n_total"].as_u64().unwrap_or(0),
                "B1 first-83 prospective research engine"
            );
        }
        info!(
            answer = %report.answer,
            status = %report.coverage.status,
            w6 = report.coverage.w6_eligible_games,
            w7_holdout = report.coverage.w7_post_cutoff_games,
            first83 = report.coverage.first83_eligible,
            out = %pargs.out_dir.display(),
            "B1 first-83 prospective validation"
        );
        println!("{}", report.answer);
        return;
    }
    if sixth_lead2_first80 {
        let first83 = cfg.out_dir.join("first83").join("features.sqlite");
        let out = cfg.out_dir.join("sixth_lead2_first80");
        let report = run_sixth_lead2_first80(
            &cfg.w6_sqlite,
            &cfg.w7_sqlite,
            &cfg.w8_sqlite,
            &cfg.identity_landing,
            Some(&first83),
            &out,
        )
        .expect("sixth-lead2 first80 analysis");
        info!(
            scanned = report.w7_games_scanned,
            inning6 = report.after6th_lead2_inning6.n,
            late = report.after6th_lead2_all.n,
            win_without_40 = report.after6th_lead2_inning6.win_without_40,
            out = %out.display(),
            "6th-inning lead≥2 first-80 never-touch-40"
        );
        println!(
            "inning6 n={} win_without_40={} ({}) late n={} win_without_40={} ({})",
            report.after6th_lead2_inning6.n,
            report.after6th_lead2_inning6.win_without_40,
            report
                .after6th_lead2_inning6
                .pct_win_without_40
                .map(|x| format!("{:.1}%", x * 100.0))
                .unwrap_or_else(|| "—".into()),
            report.after6th_lead2_all.n,
            report.after6th_lead2_all.win_without_40,
            report
                .after6th_lead2_all
                .pct_win_without_40
                .map(|x| format!("{:.1}%", x * 100.0))
                .unwrap_or_else(|| "—".into()),
        );
        return;
    }
    if !extract && !search && !search_83 && !search_83_opt && !search_83_exh && !extract_first83 {
        extract = true;
    }
    if extract {
        let report = run_b1_batch(&cfg).expect("b1 extract");
        info!(
            snapshots = report.snapshots_written,
            games = report.unique_games,
            w8 = report.w8_entries,
            gate = %report.b1_gate,
            "B1 feature extraction"
        );
    }
    if search {
        let mut sc = SearchConfig::defaults();
        sc.features_sqlite = cfg.out_dir.join("features.sqlite");
        sc.w8_sqlite = cfg.w8_sqlite.clone();
        sc.w6_sqlite = cfg.w6_sqlite.clone();
        sc.identity_landing = cfg.identity_landing.clone();
        sc.out_dir = cfg.out_dir.clone();
        let report = run_bucket_search(&sc).expect("b1 search");
        info!(candidates = ?report.get("candidates"), best = ?report.get("best"), "B1 bucket search");
    }
    if search_83 {
        let mut sc = SearchConfig::defaults();
        sc.features_sqlite = cfg.out_dir.join("features.sqlite");
        sc.out_dir = cfg.out_dir.clone();
        let report = run_83_condition_search(&sc).expect("b1 83 condition search");
        info!(
            n_83 = ?report.get("n_83"),
            best = ?report.get("best"),
            status = ?report.get("best_status"),
            "B1 83¢ condition search"
        );
    }
    if search_83_opt {
        let mut sc = SearchConfig::defaults();
        sc.features_sqlite = cfg.out_dir.join("features.sqlite");
        sc.out_dir = cfg.out_dir.clone();
        let report = run_83_optimal_search(&sc).expect("b1 83 optimal search");
        info!(
            n_83 = ?report.get("n_83"),
            best = ?report.get("best"),
            class = ?report.get("best_class"),
            consistent = ?report.get("n_consistent"),
            "B1 83¢ optimal intersection search"
        );
    }
    if extract_first83 || (search_83_exh && first_exact_83) {
        let db = cfg.out_dir.join("first83").join("features.sqlite");
        if extract_first83 || !db.exists() {
            let report = run_first83_extract(&cfg).expect("b1 first-exact-83 extract");
            info!(
                n = report.snapshots_written,
                games = report.unique_games,
                skipped_no_83 = report.skipped_no_83,
                skipped_bound = report.skipped_bound_contract_no_83,
                "B1 first exact 83¢ extract"
            );
        }
    }
    if search_83_exh {
        let mut sc = SearchConfig::defaults();
        if first_exact_83 {
            sc.features_sqlite = cfg.out_dir.join("first83").join("features.sqlite");
            sc.out_dir = cfg.out_dir.join("first83");
        } else {
            sc.features_sqlite = cfg.out_dir.join("features.sqlite");
            sc.out_dir = cfg.out_dir.clone();
        }
        let report = run_83_exhaustive_search(&sc, &exh).expect("b1 83 exhaustive search");
        info!(
            n_83 = ?report.get("n_83"),
            candidates = ?report.get("candidates"),
            primary = ?report.get("primary"),
            class = ?report.get("primary_class"),
            "B1 83¢ exhaustive search"
        );
    }
}
