//! Historical Kalshi research collector. Isolated from `momento-trading-engine`.

use chrono::Utc;
use momento_research_data::{
    Collector, CollectorConfig, ReplayDataset, ResearchCatalog, ResearchPaths, ResearchSeason,
    W1RunConfig, backfill_dates, collection_schedule, export_csv, next_collection_run,
    run_w1_foundation,
};
use tracing::{info, warn};
use tracing_subscriber::EnvFilter;

fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env().add_directive("info".parse().unwrap()))
        .init();

    let args: Vec<String> = std::env::args().collect();
    let cmd = args.get(1).map(String::as_str).unwrap_or("reconcile");

    match cmd {
        "reconcile" => run_reconcile(),
        "collect-date" => {
            let date = args
                .get(2)
                .expect("usage: momento-research-collector collect-date YYYY-MM-DD");
            run_collect_date(date);
        }
        "schedule-info" => {
            let schedule = collection_schedule();
            let next = next_collection_run(Utc::now());
            info!(
                timezone = schedule.timezone,
                hour_local = schedule.hour_local,
                next_run_utc = %next,
                "collection schedule"
            );
        }
        "export-csv" => {
            let sport = args.get(2).expect("usage: export-csv MLB|WNBA YYYY-MM-DD");
            let date = args.get(3).expect("usage: export-csv MLB|WNBA YYYY-MM-DD");
            run_export(sport, date);
        }
        "catalog" => run_catalog(),
        "w1-foundation" => run_w1_foundation_cmd(&args),
        other => {
            eprintln!(
                "unknown command {other}. commands: reconcile, collect-date, schedule-info, export-csv, catalog, w1-foundation"
            );
            std::process::exit(2);
        }
    }
}

fn run_reconcile() {
    let config = CollectorConfig::default_sports();
    let paths = config.paths.clone();
    let season = config.season.clone();
    let now = Utc::now();
    let collector = Collector::new(config);

    for sport in [
        momento_research_data::ResearchSport::Mlb,
        momento_research_data::ResearchSport::Wnba,
    ] {
        let dates = backfill_dates(&paths, sport, &season, now).expect("backfill dates");
        if dates.is_empty() {
            info!(sport = sport.dir_name(), "no missing dates");
            continue;
        }
        info!(
            sport = sport.dir_name(),
            count = dates.len(),
            "backfilling dates"
        );
        match collector.reconcile(&dates) {
            Ok(reports) => {
                for r in reports {
                    info!(
                        sport = r.sport.dir_name(),
                        date = %r.date,
                        status = ?r.status,
                        markets = r.markets_collected,
                        "day collected"
                    );
                }
            }
            Err(err) => warn!(%err, "reconcile failed"),
        }
    }

    if let Ok(catalog) = ResearchCatalog::rebuild(&paths, &season) {
        catalog.write(&paths).expect("catalog write");
    }
}

fn run_collect_date(date_str: &str) {
    let date = chrono::NaiveDate::parse_from_str(date_str, "%Y-%m-%d").expect("date");
    let config = CollectorConfig::default_sports();
    let collector = Collector::new(config);
    for sport in [
        momento_research_data::ResearchSport::Mlb,
        momento_research_data::ResearchSport::Wnba,
    ] {
        let report = collector.collect_day(sport, date).expect("collect");
        info!(?report, "collected");
    }
}

fn run_export(sport_str: &str, date_str: &str) {
    let sport = match sport_str {
        "MLB" => momento_research_data::ResearchSport::Mlb,
        "WNBA" => momento_research_data::ResearchSport::Wnba,
        other => panic!("unknown sport {other}"),
    };
    let date = chrono::NaiveDate::parse_from_str(date_str, "%Y-%m-%d").expect("date");
    let paths = ResearchPaths::from_env_or_default();
    let dataset = ReplayDataset::load(&paths, sport, date).expect("load");
    let out = paths
        .exports_dir()
        .join(format!("{}_{}.csv", sport.dir_name(), date));
    export_csv(&out, &dataset.trades, &dataset.orderbook_events).expect("export");
    info!(path = %out.display(), "exported csv");
}

fn run_catalog() {
    let paths = ResearchPaths::from_env_or_default();
    let season = ResearchSeason::current();
    let catalog = ResearchCatalog::rebuild(&paths, &season).expect("catalog");
    catalog.write(&paths).expect("write");
    info!(path = %paths.catalog_path().display(), "catalog updated");
}

fn run_w1_foundation_cmd(args: &[String]) {
    let mut config = W1RunConfig::data_real_defaults();
    let mut i = 2usize;
    while i < args.len() {
        match args[i].as_str() {
            "--lake" => {
                config.lake_root = args.get(i + 1).expect("--lake PATH").into();
                i += 2;
            }
            "--out" => {
                config.out_dir = args.get(i + 1).expect("--out PATH").into();
                i += 2;
            }
            "--class" => {
                config.lake_class = args.get(i + 1).expect("--class REAL|DEMO").clone();
                i += 2;
            }
            other => {
                eprintln!("unknown flag {other}");
                std::process::exit(2);
            }
        }
    }
    match run_w1_foundation(&config) {
        Ok(result) => {
            info!(
                run_id = %result.run_id,
                status = %result.status,
                digest = %result.lake_content_digest,
                out = %result.out_dir,
                "W1 foundation complete"
            );
        }
        Err(err) => {
            eprintln!("w1-foundation failed: {err}");
            std::process::exit(1);
        }
    }
}
