//! Research-only CLI for the Kalshi KXWNBAGAME warehouse.
//! Does not submit orders and does not touch live trading.

use std::env;
use std::path::PathBuf;
use std::process::ExitCode;

use momento_research_data::{NbaWarehouse, WarehouseConfig, canonicalize_season, render_report};

fn main() -> ExitCode {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .init();

    let args: Vec<String> = env::args().skip(1).collect();
    if args.is_empty() || args.iter().any(|a| a == "-h" || a == "--help") {
        print_help();
        return ExitCode::SUCCESS;
    }
    match run(&args) {
        Ok(()) => ExitCode::SUCCESS,
        Err(err) => {
            eprintln!("wnba-data error: {err}");
            ExitCode::FAILURE
        }
    }
}

fn run(args: &[String]) -> Result<(), String> {
    let cmd = args[0].as_str();
    let flags = parse_flags(&args[1..]);
    let mut config = WarehouseConfig::wnba_season_2025_26()
        .with_season(flags.season.as_deref().unwrap_or("2025-2026"));
    config.event_filter = flags.event;
    config.ticker_filter = flags.ticker;
    if let Some(w) = flags.workers {
        config.max_workers = w;
    }
    if let Some(rps) = flags.rps {
        config.requests_per_second = rps;
    }
    let warehouse = NbaWarehouse::open(config, flags.data_dir);

    match cmd {
        "discover" | "download-events" | "download-markets" => {
            let u = warehouse.discover().map_err(|e| e.to_string())?;
            println!(
                "discovered events={} markets={} event_pages={} market_pages={}",
                u.events.len(),
                u.markets.len(),
                u.event_pages,
                u.market_pages
            );
        }
        "download-candles" | "download-trades" | "download-all" => {
            if flags.dry_run {
                let dry = warehouse.dry_run().map_err(|e| e.to_string())?;
                println!(
                    "dry-run season={}\nevents={}\nmarkets={}\ngames={}\nestimated_requests={}\nalready_downloaded_candles={}\nalready_downloaded_trades={}\npending_candles={}\npending_trades={}",
                    warehouse.config.season,
                    dry.events,
                    dry.markets,
                    dry.games,
                    dry.estimated_requests,
                    dry.already_downloaded_candles,
                    dry.already_downloaded_trades,
                    dry.pending_candles,
                    dry.pending_trades
                );
                return Ok(());
            }
            let report = warehouse.download_all().map_err(|e| e.to_string())?;
            print!("{}", render_report(&report));
        }
        "validate" | "coverage" => {
            let report = warehouse.validate().map_err(|e| e.to_string())?;
            print!("{}", render_report(&report));
        }
        "rebuild-derived" => {
            let universe = warehouse.load_or_discover().map_err(|e| e.to_string())?;
            let report = warehouse
                .rebuild_all(&universe)
                .map_err(|e| e.to_string())?;
            print!("{}", render_report(&report));
        }
        other => return Err(format!("unknown command {other}")),
    }
    Ok(())
}

#[derive(Default)]
struct Flags {
    season: Option<String>,
    event: Option<String>,
    ticker: Option<String>,
    dry_run: bool,
    data_dir: Option<PathBuf>,
    workers: Option<usize>,
    rps: Option<f64>,
}

fn parse_flags(args: &[String]) -> Flags {
    let mut flags = Flags::default();
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--season" => {
                i += 1;
                if let Some(v) = args.get(i) {
                    flags.season = Some(canonicalize_season(v));
                }
            }
            "--event" => {
                i += 1;
                flags.event = args.get(i).cloned();
            }
            "--ticker" => {
                i += 1;
                flags.ticker = args.get(i).cloned();
            }
            "--data-dir" => {
                i += 1;
                flags.data_dir = args.get(i).map(PathBuf::from);
            }
            "--max-workers" => {
                i += 1;
                flags.workers = args.get(i).and_then(|v| v.parse().ok());
            }
            "--rps" => {
                i += 1;
                flags.rps = args.get(i).and_then(|v| v.parse().ok());
            }
            "--dry-run" => flags.dry_run = true,
            _ => {}
        }
        i += 1;
    }
    flags
}

fn print_help() {
    println!(
        "wnba-data — Kalshi KXWNBAGAME historical warehouse (research only)\n\n\
Commands:\n\
  discover            Enumerate events and markets\n\
  download-events     Same as discover (events are part of catalog)\n\
  download-markets    Same as discover\n\
  download-candles    Download candles (+ trades) then normalize\n\
  download-trades     Download trades (+ candles) then normalize\n\
  download-all        Discover + candles + trades + derive + validate\n\
  validate            Rebuild derived tables and write validation report\n\
  coverage            Alias for validate\n\
  rebuild-derived     Normalize/derive from raw without re-downloading\n\n\
Flags:\n\
  --season 2025-26|2025-2026\n\
  --event KXWNBAGAME-...\n\
  --ticker KXWNBAGAME-...\n\
  --dry-run\n\
  --data-dir PATH\n\
  --max-workers N\n\
  --rps N\n\n\
Folder 2025-2026 holds the 2025 and 2026 WNBA campaigns.\n\
Historical data is 1-minute top-of-book + trades. Historical L2 is not available.\n\
Does not submit orders. Does not change live FIRST01.\n"
    );
}
