//! CSV export for small research tables.

use std::fs::File;
use std::io::Write;
use std::path::Path;

use crate::schema::{OrderbookEvent, PublicTrade};

pub fn export_csv(
    path: &Path,
    trades: &[PublicTrade],
    orderbook: &[OrderbookEvent],
) -> std::io::Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let mut file = File::create(path)?;
    writeln!(
        file,
        "kind,exchange_time,received_time,ticker,market_id,game_id,yes_price_cents,qty_hundredths,event_type,sequence_gap"
    )?;
    for t in trades {
        writeln!(
            file,
            "trade,{},{},{},{},{},{},{},,false",
            t.exchange_timestamp,
            t.received_timestamp.to_rfc3339(),
            t.ticker,
            t.market_id,
            t.game_id,
            t.yes_price_cents,
            t.quantity_hundredths,
        )?;
    }
    for o in orderbook {
        writeln!(
            file,
            "orderbook,{},{},{},{},{},{},{},{},{}",
            o.exchange_timestamp_ms
                .map(|ms| ms.to_string())
                .unwrap_or_default(),
            o.received_timestamp.to_rfc3339(),
            o.ticker,
            o.market_id,
            o.game_id,
            o.yes_bid_cents.unwrap_or(0),
            o.yes_ask_cents.unwrap_or(0),
            o.event_type,
            o.sequence_gap,
        )?;
    }
    Ok(())
}
