//! DATA-INGEST CLI. Network requires --authorize-network ENABLE_RESEARCH_INGEST_NETWORK.

use momento_research_ingest::cloud::{CloudWorkerSpec, cloud_deployment_status};
use momento_research_ingest::fence::default_forbidden_roots;
use momento_research_ingest::kalshi::BlockedNetworkKalshiSource;
use momento_research_ingest::kalshi_live::LiveKalshiSource;
use momento_research_ingest::orchestrator::{replay_run, run_ingest_with_sources};
use momento_research_ingest::planner::{partition_window, required_mlb_partitions};
use momento_research_ingest::schedule::{ingest_schedule, next_weekly_ingest};
use momento_research_ingest::source::{EmptyPbpSource, LiveStatsApiSource};
use momento_research_ingest::types::{
    DateWindow, ExecutionMode, IngestPlan, NETWORK_AUTHORIZATION_PHRASE,
};
use momento_research_ingest::weekly_window;
use tracing::info;
use tracing_subscriber::EnvFilter;

fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env().add_directive("info".parse().unwrap()))
        .init();

    let args: Vec<String> = std::env::args().collect();
    let cmd = args.get(1).map(String::as_str).unwrap_or("schedule-info");
    match cmd {
        "schedule-info" => {
            let s = ingest_schedule();
            let next = next_weekly_ingest(chrono::Utc::now());
            let weekly = weekly_window(chrono::Utc::now(), 7);
            info!(
                timezone = s.timezone,
                weekday = ?s.weekday,
                hour_local = s.hour_local,
                next_run_utc = %next,
                weekly_start = %weekly.start,
                weekly_end = %weekly.end,
                cloud = cloud_deployment_status(),
                "DATA-INGEST weekly Sunday 00:00 Pacific"
            );
        }
        "plan-windows" => plan_windows_cmd(),
        "cloud-spec" => {
            let spec = CloudWorkerSpec::specified_not_deployed(ExecutionMode::Weekly);
            println!("{}", serde_json::to_string_pretty(&spec).expect("json"));
        }
        "run" => run_cmd(&args, ExecutionMode::Manual, false),
        "backfill" => run_cmd(&args, ExecutionMode::HistoricalBackfill, true),
        "weekly" => run_cmd(&args, ExecutionMode::Weekly, false),
        "replay" => {
            let dir = args.get(2).expect("usage: replay RUN_DIR");
            let report = replay_run(std::path::Path::new(dir)).expect("replay");
            info!(run_id = %report.run_id, status = ?report.status, "replayed ingest manifest");
        }
        "matched-trades-backfill" => matched_trades_cmd(&args),
        "rejoin-landing" => rejoin_landing_cmd(&args),
        other => {
            eprintln!(
                "unknown command {other}. commands: schedule-info, plan-windows, cloud-spec, run, backfill, weekly, replay, matched-trades-backfill, rejoin-landing"
            );
            std::process::exit(2);
        }
    }
}

fn plan_windows_cmd() {
    let as_of = chrono::Utc::now().date_naive();
    let required = DateWindow::required_mlb_windows(as_of);
    println!(
        "as_of={as_of} cloud={} targets: PBP>={} mapped_pairs>={} (not a completeness claim)",
        cloud_deployment_status(),
        momento_research_ingest::types::TARGET_MIN_PBP_GAMES,
        momento_research_ingest::types::TARGET_MIN_MAPPED_PAIRS
    );
    for w in &required {
        let parts = partition_window(w, 7);
        println!(
            "window {} {}..{} chunks={}",
            w.label,
            w.start,
            w.end,
            parts.len()
        );
    }
    println!("total_chunks={}", required_mlb_partitions(as_of, 7).len());
}

fn run_cmd(args: &[String], mode: ExecutionMode, backfill: bool) {
    let cwd = std::env::current_dir().unwrap_or_else(|_| ".".into());
    let mut plan = IngestPlan::test_defaults(
        "Backtesting Suite/Data-Real".into(),
        "Backtesting Suite/Foundation/Ingest".into(),
    );
    plan.kalshi_catalog = true;
    plan.kalshi_discover = false;
    plan.include_weekly = mode == ExecutionMode::Weekly;
    plan.network_enabled = false;
    plan.execution_mode = mode;
    plan.fill_unlisted_dates = !backfill;
    plan.invoke_w2 = !backfill;
    plan.persist_watermarks = true;
    plan.overlap_days = if matches!(mode, ExecutionMode::Weekly) {
        3
    } else {
        0
    };
    plan.skip_existing = true;
    plan.max_retries = 2;
    plan.retry_sleep_ms = 400;
    plan.rate_limit_ms = 400;
    plan.forbidden_write_roots = default_forbidden_roots(&cwd);
    if backfill {
        plan.pbp_windows = DateWindow::required_mlb_windows(plan.as_of_date());
        plan.invoke_w2 = false;
        plan.fill_unlisted_dates = false;
    }
    let mut i = 2usize;
    let mut network_phrase: Option<String> = None;
    while i < args.len() {
        match args[i].as_str() {
            "--lake" => {
                plan.lake_root = args.get(i + 1).expect("--lake PATH").into();
                i += 2;
            }
            "--out" => {
                plan.ingest_root = args.get(i + 1).expect("--out PATH").into();
                i += 2;
            }
            "--weekly" => {
                plan.include_weekly = true;
                i += 1;
            }
            "--window" => {
                let spec = args.get(i + 1).expect("--window START:END");
                let (start, end) = spec.split_once(':').expect("--window START:END");
                plan.pbp_windows = vec![DateWindow {
                    label: "cli-window".into(),
                    start: chrono::NaiveDate::parse_from_str(start, "%Y-%m-%d").expect("start"),
                    end: chrono::NaiveDate::parse_from_str(end, "%Y-%m-%d").expect("end"),
                }];
                plan.overlap_days = 0;
                i += 2;
            }
            "--max-days" => {
                plan.max_days = Some(args.get(i + 1).expect("--max-days N").parse().expect("n"));
                i += 2;
            }
            "--kalshi-metadata-only" => {
                plan.fetch_kalshi_artifacts = false;
                i += 1;
            }
            "--network" => {
                eprintln!(
                    "refusing bare --network. Use --authorize-network {NETWORK_AUTHORIZATION_PHRASE}"
                );
                std::process::exit(2);
            }
            "--authorize-network" => {
                network_phrase = Some(args.get(i + 1).expect("--authorize-network PHRASE").clone());
                i += 2;
            }
            "--invoke-w2" => {
                plan.invoke_w2 = true;
                i += 1;
            }
            other => {
                eprintln!("unknown flag {other}");
                std::process::exit(2);
            }
        }
    }
    if let Some(phrase) = network_phrase {
        if phrase != NETWORK_AUTHORIZATION_PHRASE {
            eprintln!("invalid network authorization phrase");
            std::process::exit(2);
        }
        plan.network_enabled = true;
        plan.kalshi_discover = true;
        plan.kalshi_catalog = true;
        plan.fetch_kalshi_artifacts = !args.iter().any(|a| a == "--kalshi-metadata-only");
        if !args.iter().any(|a| a == "--invoke-w2") {
            plan.invoke_w2 = false;
        }
        let pbp = LiveStatsApiSource;
        let mut kalshi = LiveKalshiSource::production(plan.rate_limit_ms);
        kalshi.fetch_trades = plan.fetch_kalshi_artifacts;
        kalshi.fetch_candles = plan.fetch_kalshi_artifacts;
        let report = match run_ingest_with_sources(&plan, &pbp, &kalshi) {
            Ok(r) => r,
            Err(e) => {
                eprintln!("ingest failed (watchdog will restart): {e}");
                std::process::exit(1);
            }
        };
        info!(
            run_id = %report.run_id,
            status = ?report.status,
            pbp_committed = report.corpus.pbp_games_committed,
            mapped_pairs = report.corpus.pairs_mapped,
            unmatched = report.corpus.pairs_unmatched,
            ambiguous = report.corpus.pairs_ambiguous,
            network_ready = report.network_ready,
            pbp_target_met = report.corpus.pbp_target_met,
            pair_target_met = report.corpus.pair_target_met,
            "authorized network ingest complete"
        );
        println!(
            "{}",
            serde_json::to_string_pretty(&report.corpus).expect("corpus json")
        );
        return;
    }
    let report = run_ingest_with_sources(&plan, &EmptyPbpSource, &BlockedNetworkKalshiSource)
        .expect("ingest");
    info!(
        run_id = %report.run_id,
        status = ?report.status,
        coverage = report.coverage.len(),
        cloud = %report.cloud_status,
        "ingest run complete (network not authorized)"
    );
}

fn matched_trades_cmd(args: &[String]) {
    let cwd = std::env::current_dir().unwrap_or_else(|_| ".".into());
    let mut lake = std::path::PathBuf::from("Backtesting Suite/Data-Real");
    let mut ingest_root = std::path::PathBuf::from("Backtesting Suite/Foundation/Ingest");
    let mut pairs_path: Option<std::path::PathBuf> = None;
    let mut network_phrase: Option<String> = None;
    let mut discover_only = false;
    let mut skip_existing = true;
    let mut max_markets: Option<usize> = None;
    let mut i = 2usize;
    while i < args.len() {
        match args[i].as_str() {
            "--lake" => {
                lake = args.get(i + 1).expect("--lake PATH").into();
                i += 2;
            }
            "--out" => {
                ingest_root = args.get(i + 1).expect("--out PATH").into();
                i += 2;
            }
            "--pairs" => {
                pairs_path = Some(args.get(i + 1).expect("--pairs PATH").into());
                i += 2;
            }
            "--max-markets" => {
                max_markets = Some(
                    args.get(i + 1)
                        .expect("--max-markets N")
                        .parse()
                        .expect("n"),
                );
                i += 2;
            }
            "--discover-only" => {
                discover_only = true;
                i += 1;
            }
            "--no-skip-existing" => {
                skip_existing = false;
                i += 1;
            }
            "--network" => {
                eprintln!(
                    "refusing bare --network. Use --authorize-network {NETWORK_AUTHORIZATION_PHRASE}"
                );
                std::process::exit(2);
            }
            "--authorize-network" => {
                network_phrase = Some(args.get(i + 1).expect("--authorize-network PHRASE").clone());
                i += 2;
            }
            other => {
                eprintln!("unknown flag {other}");
                std::process::exit(2);
            }
        }
    }
    let pairs_path = pairs_path.unwrap_or_else(|| {
        ingest_root
            .join("runs")
            .join("ingest-20260826T095038Z-2bc3d10b5833")
            .join("game_market_pairs.json")
    });
    let pairs = momento_research_ingest::matched_trades::load_game_market_pairs(&pairs_path)
        .expect("pairs");
    let forbidden = default_forbidden_roots(&cwd);
    if discover_only {
        let discovery =
            momento_research_ingest::matched_trades::discover_matched_trade_sources(&lake, &pairs)
                .expect("discovery");
        println!(
            "{}",
            serde_json::to_string_pretty(&discovery).expect("json")
        );
        return;
    }
    let Some(phrase) = network_phrase else {
        eprintln!(
            "matched-trades-backfill requires --authorize-network {NETWORK_AUTHORIZATION_PHRASE} or --discover-only"
        );
        std::process::exit(2);
    };
    if phrase != NETWORK_AUTHORIZATION_PHRASE {
        eprintln!("invalid network authorization phrase");
        std::process::exit(2);
    }
    let source = LiveKalshiSource::production(150);
    let report = momento_research_ingest::matched_trades::run_matched_trade_backfill(
        &ingest_root,
        &lake,
        &forbidden,
        &pairs,
        &source,
        chrono::Utc::now(),
        skip_existing,
        max_markets,
    )
    .expect("matched trade backfill");
    info!(
        attempted = report.matched_attempted,
        with_trades = report.landed_with_trades,
        empty = report.landed_empty,
        observations = report.canonical_trade_observations,
        "W4-D MATCHED trade backfill"
    );
    println!("{}", serde_json::to_string_pretty(&report).expect("json"));
}

fn rejoin_landing_cmd(args: &[String]) {
    let mut ingest_root = std::path::PathBuf::from("Backtesting Suite/Foundation/Ingest");
    let mut i = 2usize;
    while i < args.len() {
        match args[i].as_str() {
            "--out" => {
                ingest_root = args.get(i + 1).expect("--out PATH").into();
                i += 2;
            }
            other => {
                eprintln!("unknown flag {other}");
                std::process::exit(2);
            }
        }
    }
    let report = momento_research_ingest::rejoin::rejoin_landing(&ingest_root).expect("rejoin");
    info!(
        run_id = %report.run_id,
        pbp_ok = report.pbp_identity_ok,
        mapped_games = report.corpus.games_mapped,
        mapped_pairs = report.corpus.pairs_mapped,
        unmatched = report.corpus.games_unmatched,
        ambiguous = report.corpus.games_ambiguous,
        "offline landing identity rejoin"
    );
    println!(
        "{}",
        serde_json::to_string_pretty(&report.corpus).expect("json")
    );
}
