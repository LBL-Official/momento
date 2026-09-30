//! Market-data normalization. No order transport; sequence gaps poison history.
use momento_kalshi::{
    ApplyResult, LocalOrderBook, parse_orderbook_delta, parse_orderbook_snapshot, parse_ws_frame,
};
use momento_strategy_nba::live_v1::{Input, Mapping, Quote};
use std::collections::BTreeMap;
pub struct Quotes {
    book: LocalOrderBook,
    routes: BTreeMap<String, (String, usize)>,
}
impl Quotes {
    pub fn new(mappings: &[Mapping]) -> Result<Self, String> {
        let mut routes = BTreeMap::new();
        for m in mappings {
            for (side, ticker) in m.tickers.iter().enumerate() {
                if ticker.is_empty()
                    || routes
                        .insert(ticker.clone(), (m.event_id.clone(), side))
                        .is_some()
                {
                    return Err("KALSHI_TICKER_MAPPING_AMBIGUOUS".into());
                }
            }
        }
        Ok(Self {
            book: LocalOrderBook::new(),
            routes,
        })
    }
    pub fn frame(&mut self, raw: &str, now: i64) -> Result<Option<Input>, String> {
        let parsed = self.parse(raw, now);
        if parsed.is_err() {
            self.book.clear();
        }
        parsed
    }
    fn parse(&mut self, raw: &str, now: i64) -> Result<Option<Input>, String> {
        let env = parse_ws_frame(raw).map_err(|e| format!("{e:?}"))?;
        if env.msg_type == "error" {
            return Err("KALSHI_WS_ERROR".into());
        }
        if !["orderbook_snapshot", "orderbook_delta"].contains(&env.msg_type.as_str()) {
            return Ok(None);
        }
        let sid = env.sid.ok_or("KALSHI_SID_MISSING")?;
        let seq = env.seq.ok_or("KALSHI_SEQUENCE_MISSING")?;
        let result = if env.msg_type == "orderbook_snapshot" {
            let msg = parse_orderbook_snapshot(&env).map_err(|e| format!("{e:?}"))?;
            self.book.apply_snapshot(sid, seq, &msg)
        } else {
            let msg = parse_orderbook_delta(&env).map_err(|e| format!("{e:?}"))?;
            self.book.apply_delta(sid, seq, &msg)
        }
        .map_err(|e| format!("{e:?}"))?;
        match result {
            ApplyResult::Ignored => Ok(None),
            ApplyResult::Gap => Ok(Some(Input::Gap {
                reason: "KALSHI_SEQUENCE_GAP".into(),
            })),
            ApplyResult::Unready { .. } | ApplyResult::Updated { quote: None, .. } => {
                Ok(Some(Input::Gap {
                    reason: "KALSHI_BOOK_UNREADY".into(),
                }))
            }
            ApplyResult::Updated {
                ticker,
                quote: Some(q),
            } => {
                if self.book.has_gap() {
                    return Ok(Some(Input::Gap {
                        reason: "KALSHI_SEQUENCE_GAP".into(),
                    }));
                }
                let (event_id, side) = self.routes.get(&ticker).ok_or("UNMAPPED_KALSHI_TICKER")?;
                Ok(Some(Input::Quote {
                    event_id: event_id.clone(),
                    quote: Quote {
                        side: *side,
                        bid: q.yes_bid.cents(),
                        ask: q.yes_ask.cents(),
                        receive_ms: now,
                        exchange_ms: q.ts_ms,
                    },
                }))
            }
        }
    }
}
/// Bounded read-only capture for adapter verification. Restart requires Gap
/// before future observations; a snapshot never repairs earlier FIRST78 history.
pub fn observe(args: &[String]) -> Result<(), (i32, String)> {
    let run = || -> Result<(), String> {
        if args.len() != 3 {
            return Err(
                "usage: v1-kalshi-observe MAPPINGS_JSON SECRET_FILE DURATION_SECONDS".into(),
            );
        }
        let duration: u64 = args[2].parse().map_err(|_| "INVALID_DURATION")?;
        if !(1..=3600).contains(&duration) {
            return Err("DURATION_MUST_BE_1_TO_3600".into());
        }
        let mappings: Vec<Mapping> =
            serde_json::from_slice(&std::fs::read(&args[0]).map_err(|e| e.to_string())?)
                .map_err(|e| e.to_string())?;
        let mut quotes = Quotes::new(&mappings)?;
        if mappings.is_empty() {
            return Err("MAPPINGS_REQUIRED".into());
        }
        let credentials = momento_kalshi::credentials_from_secret_file(
            momento_kalshi::KalshiEnvironment::Production,
            std::path::Path::new(&args[1]),
        )
        .map_err(|e| format!("{e:?}"))?;
        let mut ws =
            momento_kalshi::ProductionWs::connect(&credentials).map_err(|e| format!("{e:?}"))?;
        ws.subscribe_orderbook(&quotes.routes.keys().cloned().collect::<Vec<_>>())
            .map_err(|e| format!("{e:?}"))?;
        let emit = |input| {
            println!(
                "{}",
                serde_json::to_string(&super::Envelope {
                    at_ms: crate::engine::now_ms(),
                    input
                })
                .unwrap()
            )
        };
        emit(Input::Gap {
            reason: "KALSHI_OBSERVER_STARTED".into(),
        });
        let start = std::time::Instant::now();
        while start.elapsed().as_secs() < duration {
            let read = match ws.read() {
                Ok(read) => read,
                Err(e) => {
                    emit(Input::Gap {
                        reason: "KALSHI_DISCONNECTED".into(),
                    });
                    return Err(format!("{e:?}"));
                }
            };
            match read {
                momento_kalshi::WsRead::Idle => {}
                momento_kalshi::WsRead::Text(raw) => {
                    match quotes.frame(&raw, crate::engine::now_ms()) {
                        Ok(Some(input)) => emit(input),
                        Ok(None) => {}
                        Err(e) => {
                            emit(Input::Gap { reason: e.clone() });
                            return Err(e);
                        }
                    }
                }
            }
        }
        emit(Input::Gap {
            reason: "KALSHI_OBSERVER_STOPPED".into(),
        });
        let _ = ws.close();
        Ok(())
    };
    run().map_err(|e| (78, e))
}
#[cfg(test)]
mod tests {
    use super::*;
    use momento_strategy_nba::live_v1::Sport;
    use serde_json::json;
    #[test]
    fn sequence_gap_and_repeated_snapshot_never_restore_first_touch_history() {
        let m = Mapping {
            event_id: "e".into(),
            sport: Sport::NBA,
            tickers: ["A".into(), "B".into()],
            espn_event_id: "1".into(),
            espn_team_ids: ["1".into(), "2".into()],
            season: "2026-27".into(),
            membership_evidence: None,
            both_p5: false,
            complement_evidence: "fixture".into(),
        };
        let mut q = Quotes::new(&[m]).unwrap();
        let frame = |seq| {
            json!({"type":"orderbook_snapshot","sid":1,"seq":seq,"msg":{"market_ticker":"A","yes_dollars_fp":[["0.7700","10.00"]],"no_dollars_fp":[["0.2100","10.00"]]}}).to_string()
        };
        assert!(matches!(
            q.frame(&frame(1), 100).unwrap(),
            Some(Input::Quote { .. })
        ));
        assert!(q.frame(&frame(1), 100).unwrap().is_none());
        assert!(matches!(
            q.frame(&frame(3), 100).unwrap(),
            Some(Input::Gap { .. })
        ));
        assert!(matches!(
            q.frame(&frame(4), 100).unwrap(),
            Some(Input::Gap { .. })
        ));
    }
}
