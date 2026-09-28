//! Research-only CLI for the Kalshi KXATPMATCH / KXWTAMATCH warehouses.
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
            eprintln!("tennis-data error: {err}");
            ExitCode::FAILURE
        }
    }
}

/// ATP and WTA are separate Kalshi series and separate warehouse layers under
/// the shared `TENNIS` data directory.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Tour {
    Atp,
    Wta,
}

impl Tour {
    fn parse(raw: &str) -> Result<Self, String> {
        match raw.trim().to_ascii_lowercase().as_str() {
            "atp" => Ok(Self::Atp),
            "wta" => Ok(Self::Wta),
            other => Err(format!("unknown --tour {other}; expected atp or wta")),
        }
    }

    fn config(self) -> WarehouseConfig {
        match self {
            Self::Atp => WarehouseConfig::tennis_atp_season_2025_26(),
            Self::Wta => WarehouseConfig::tennis_wta_season_2025_26(),
        }
    }
}

fn run(args: &[String]) -> Result<(), String> {
    let cmd = args[0].as_str();
    let flags = parse_flags(&args[1..])?;
    let mut config = flags
        .tour
        .config()
        .with_season(flags.season.as_deref().unwrap_or("2025-2026"));
    if flags.candles_only || cmd == "download-candles" {
        config = config.candles_only();
    }
    config.event_filter = flags.event;
    config.ticker_filter = flags.ticker;
    if let Some(w) = flags.workers {
        config.max_workers = w;
    }
    if let Some(rps) = flags.rps {
        config.requests_per_second = rps;
    }
    if let Some(retries) = flags.retries {
        config.retry_attempts = retries;
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
                    "dry-run tour={} series={} season={}\nevents={}\nmarkets={}\nmatches={}\nestimated_requests={}\nalready_downloaded_candles={}\nalready_downloaded_trades={}\npending_candles={}\npending_trades={}\ninclude_trades={}",
                    warehouse.config.league(),
                    warehouse.config.series,
                    warehouse.config.season,
                    dry.events,
                    dry.markets,
                    dry.games,
                    dry.estimated_requests,
                    dry.already_downloaded_candles,
                    dry.already_downloaded_trades,
                    dry.pending_candles,
                    dry.pending_trades,
                    warehouse.config.include_trades
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

struct Flags {
    tour: Tour,
    season: Option<String>,
    event: Option<String>,
    ticker: Option<String>,
    dry_run: bool,
    candles_only: bool,
    data_dir: Option<PathBuf>,
    workers: Option<usize>,
    rps: Option<f64>,
    retries: Option<u32>,
}

impl Default for Flags {
    fn default() -> Self {
        Self {
            tour: Tour::Atp,
            season: None,
            event: None,
            ticker: None,
            dry_run: false,
            candles_only: false,
            data_dir: None,
            workers: None,
            rps: None,
            retries: None,
        }
    }
}

fn parse_flags(args: &[String]) -> Result<Flags, String> {
    let mut flags = Flags::default();
    let mut i = 0;
    while i < args.len() {
        match args[i].as_str() {
            "--tour" => {
                i += 1;
                let raw = args
                    .get(i)
                    .ok_or_else(|| "--tour requires atp or wta".to_string())?;
                flags.tour = Tour::parse(raw)?;
            }
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
            "--retries" => {
                i += 1;
                flags.retries = args.get(i).and_then(|v| v.parse().ok());
            }
            "--dry-run" => flags.dry_run = true,
            "--candles-only" => flags.candles_only = true,
            _ => {}
        }
        i += 1;
    }
    Ok(flags)
}

fn print_help() {
    println!(
        "momento-tennis-data — Kalshi KXATPMATCH/KXWTAMATCH historical warehouse (research only)\n\n\
Commands:\n\
  discover            Enumerate events and markets\n\
  download-events     Same as discover (events are part of catalog)\n\
  download-markets    Same as discover\n\
  download-candles    Download 1-minute candles then normalize (no trades)\n\
  download-trades     Download trades (+ candles) then normalize\n\
  download-all        Discover + candles + trades + derive + validate\n\
  validate            Rebuild derived tables and write validation report\n\
  coverage            Alias for validate\n\
  rebuild-derived     Normalize/derive from raw without re-downloading\n\n\
Flags:\n\
  --tour atp|wta      ATP (KXATPMATCH) or WTA (KXWTAMATCH); default atp\n\
  --season 2025-26|2025-2026\n\
  --event KXATPMATCH-...\n\
  --ticker KXATPMATCH-...\n\
  --dry-run\n\
  --candles-only\n\
  --data-dir PATH\n\
  --max-workers N\n\
  --rps N\n\
  --retries N\n\n\
Layout:\n\
  ATP and WTA share the TENNIS data directory and split into the atp/ and wta/\n\
  warehouse layers. Folder 2025-2026 holds the 2025 and 2026 tennis calendars.\n\n\
Side codes:\n\
  Tennis has no home/away. The shared schema's home_team_code/away_team_code\n\
  columns carry ordered player side A / side B, derived from the two market\n\
  ticker suffixes. An event without exactly two markets is left unresolved and\n\
  reported, never guessed.\n\n\
Research only:\n\
  Does not submit orders. Does not change live FIRST01 or any live trading.\n\
  Historical L2 is NOT available and is never fabricated.\n\
  A candlestick or print path is NOT a fill.\n\
  A last trade is NOT a yes bid.\n"
    );
}
