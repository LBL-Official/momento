//! Local order book from official Kalshi WebSocket snapshot/delta frames.
//! No sockets. No production HTTP.

use momento_core::Price;
use momento_kalshi::{
    ApplyResult, LocalOrderBook, SeqOutcome, SeqTracker, parse_orderbook_delta,
    parse_orderbook_snapshot, parse_ws_frame, signed_count_fp_to_i64,
};

fn snapshot_frame(seq: u64, yes: &str, no: &str) -> String {
    format!(
        r#"{{"type":"orderbook_snapshot","sid":2,"seq":{seq},"msg":{{"market_ticker":"KXMLBGAME-TEST","market_id":"9b0f6b43-5b68-4f9f-9f02-9a2d1b8ac1a1","yes_dollars_fp":{yes},"no_dollars_fp":{no}}}}}"#
    )
}

fn delta_frame(seq: u64, price: &str, delta: &str, side: &str) -> String {
    format!(
        r#"{{"type":"orderbook_delta","sid":2,"seq":{seq},"msg":{{"market_ticker":"KXMLBGAME-TEST","market_id":"9b0f6b43-5b68-4f9f-9f02-9a2d1b8ac1a1","price_dollars":"{price}","delta_fp":"{delta}","side":"{side}","ts_ms":1715793600123}}}}"#
    )
}

#[test]
fn snapshot_then_delta_updates_best_yes_bid() {
    let mut book = LocalOrderBook::new();
    let snap = parse_ws_frame(&snapshot_frame(
        2,
        r#"[["0.8000","10.00"]]"#,
        r#"[["0.1900","4.00"]]"#,
    ))
    .unwrap();
    let snap_msg = parse_orderbook_snapshot(&snap).unwrap();
    let applied = book.apply_snapshot(2, 2, &snap_msg).unwrap();
    let ApplyResult::Updated { quote: Some(q), .. } = applied else {
        panic!("expected quote, got {applied:?}");
    };
    assert_eq!(q.yes_bid, Price::from_cents(80).unwrap());
    assert_eq!(q.yes_ask, Price::from_cents(81).unwrap());
    assert!(q.ts_ms.is_none());

    let delta = parse_ws_frame(&delta_frame(3, "0.8100", "5.00", "yes")).unwrap();
    let delta_msg = parse_orderbook_delta(&delta).unwrap();
    let applied = book.apply_delta(2, 3, &delta_msg).unwrap();
    let ApplyResult::Updated { quote: Some(q), .. } = applied else {
        panic!("expected quote, got {applied:?}");
    };
    assert_eq!(q.yes_bid, Price::from_cents(81).unwrap());
    assert_eq!(q.yes_ask, Price::from_cents(81).unwrap());
    assert_eq!(q.ts_ms, Some(1715793600123));
}

#[test]
fn seq_gap_fails_closed_and_does_not_quote() {
    let mut book = LocalOrderBook::new();
    let snap = parse_ws_frame(&snapshot_frame(
        2,
        r#"[["0.8000","10.00"]]"#,
        r#"[["0.1900","4.00"]]"#,
    ))
    .unwrap();
    book.apply_snapshot(2, 2, &parse_orderbook_snapshot(&snap).unwrap())
        .unwrap();
    let delta = parse_ws_frame(&delta_frame(4, "0.8100", "5.00", "yes")).unwrap();
    let applied = book
        .apply_delta(2, 4, &parse_orderbook_delta(&delta).unwrap())
        .unwrap();
    assert_eq!(applied, ApplyResult::Gap);
    assert!(book.has_gap());
    assert!(book.quote("KXMLBGAME-TEST").is_none());
}

#[test]
fn delta_before_snapshot_is_unready() {
    let mut book = LocalOrderBook::new();
    let delta = parse_ws_frame(&delta_frame(1, "0.8000", "5.00", "yes")).unwrap();
    let applied = book
        .apply_delta(2, 1, &parse_orderbook_delta(&delta).unwrap())
        .unwrap();
    assert!(matches!(applied, ApplyResult::Unready { .. }));
    assert!(book.quote("KXMLBGAME-TEST").is_none());
}

#[test]
fn fractional_book_size_still_quotes_best_yes_bid() {
    let mut book = LocalOrderBook::new();
    let snap = parse_ws_frame(&snapshot_frame(
        2,
        r#"[["0.8000","4047.13"]]"#,
        r#"[["0.1900","1.50"]]"#,
    ))
    .unwrap();
    let applied = book
        .apply_snapshot(2, 2, &parse_orderbook_snapshot(&snap).unwrap())
        .unwrap();
    let ApplyResult::Updated { quote: Some(q), .. } = applied else {
        panic!("expected quote, got {applied:?}");
    };
    assert_eq!(q.yes_bid, Price::from_cents(80).unwrap());
    assert_eq!(q.yes_ask, Price::from_cents(81).unwrap());
    assert_eq!(q.yes_bid_depth, None);
    assert_eq!(q.yes_ask_depth, None);
}

#[test]
fn last_trade_is_not_a_book_level() {
    let mut book = LocalOrderBook::new();
    let snap = parse_ws_frame(&snapshot_frame(
        2,
        r#"[["0.7900","10.00"]]"#,
        r#"[["0.2000","4.00"]]"#,
    ))
    .unwrap();
    book.apply_snapshot(2, 2, &parse_orderbook_snapshot(&snap).unwrap())
        .unwrap();
    let quote = book.quote("KXMLBGAME-TEST").unwrap();
    assert_eq!(quote.yes_bid, Price::from_cents(79).unwrap());
    assert_eq!(quote.yes_ask, Price::from_cents(80).unwrap());
}

#[test]
fn subcent_snapshot_fails_closed() {
    let mut book = LocalOrderBook::new();
    let snap = parse_ws_frame(&snapshot_frame(
        2,
        r#"[["0.8050","10.00"]]"#,
        r#"[["0.1900","4.00"]]"#,
    ))
    .unwrap();
    assert!(
        book.apply_snapshot(2, 2, &parse_orderbook_snapshot(&snap).unwrap())
            .is_err()
    );
}

#[test]
fn signed_delta_zeroes_a_level() {
    let mut book = LocalOrderBook::new();
    let snap = parse_ws_frame(&snapshot_frame(
        2,
        r#"[["0.8000","10.00"],["0.8100","2.00"]]"#,
        r#"[["0.1800","4.00"]]"#,
    ))
    .unwrap();
    book.apply_snapshot(2, 2, &parse_orderbook_snapshot(&snap).unwrap())
        .unwrap();
    assert_eq!(
        book.quote("KXMLBGAME-TEST").unwrap().yes_bid,
        Price::from_cents(81).unwrap()
    );
    let delta = parse_ws_frame(&delta_frame(3, "0.8100", "-2.00", "yes")).unwrap();
    book.apply_delta(2, 3, &parse_orderbook_delta(&delta).unwrap())
        .unwrap();
    assert_eq!(
        book.quote("KXMLBGAME-TEST").unwrap().yes_bid,
        Price::from_cents(80).unwrap()
    );
}

#[test]
fn seq_tracker_detects_gap_and_duplicate() {
    let mut seq = SeqTracker::new();
    assert_eq!(seq.check(1, 3), SeqOutcome::Apply);
    assert_eq!(seq.check(1, 3), SeqOutcome::Duplicate);
    assert_eq!(seq.check(1, 4), SeqOutcome::Apply);
    assert_eq!(seq.check(1, 6), SeqOutcome::Gap);
}

#[test]
fn signed_count_fp_accepts_negative_whole_contracts() {
    assert_eq!(signed_count_fp_to_i64("-54.00").unwrap(), -54);
    assert_eq!(signed_count_fp_to_i64("5.00").unwrap(), 5);
    assert!(signed_count_fp_to_i64("-1.50").is_err());
}
