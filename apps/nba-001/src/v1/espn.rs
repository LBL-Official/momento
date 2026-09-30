//! ESPN summary adapter. Explicit event/team IDs only; no name or home/away guessing.
//! ESPN's public site endpoint has no contracted freshness SLA. Receipt time is
//! not provider event time, so provider_ms remains None unless verified upstream.
use momento_strategy_nba::live_v1::{Mapping, Sport, SportsState};
use serde_json::Value;
use std::{io::Read, time::Duration};
pub fn parse_summary(raw: &Value, m: &Mapping, received_ms: i64) -> Result<SportsState, String> {
    let h = raw.get("header").ok_or("ESPN_HEADER_MISSING")?;
    if h.get("id").and_then(Value::as_str) != Some(m.espn_event_id.as_str()) {
        return Err("ESPN_EVENT_MISMATCH".into());
    }
    let competitions = h
        .get("competitions")
        .and_then(Value::as_array)
        .ok_or("ESPN_COMPETITION_MISSING")?;
    if competitions.len() != 1 {
        return Err("ESPN_COMPETITION_AMBIGUOUS".into());
    }
    let c = &competitions[0];
    let competitors = c
        .get("competitors")
        .and_then(Value::as_array)
        .ok_or("ESPN_TEAMS_MISSING")?;
    if competitors.len() != 2 || m.espn_team_ids[0] == m.espn_team_ids[1] {
        return Err("ESPN_TEAMS_AMBIGUOUS".into());
    }
    let mut scores = [0; 2];
    for (i, id) in m.espn_team_ids.iter().enumerate() {
        let matching: Vec<_> = competitors
            .iter()
            .filter(|t| t.pointer("/team/id").and_then(Value::as_str) == Some(id.as_str()))
            .collect();
        if matching.len() != 1 {
            return Err("ESPN_TEAM_MISMATCH".into());
        }
        scores[i] = matching[0]
            .get("score")
            .and_then(Value::as_str)
            .ok_or("ESPN_SCORE_MISSING")?
            .parse()
            .map_err(|_| "ESPN_SCORE_INVALID")?;
    }
    let s = c.get("status").ok_or("ESPN_STATUS_MISSING")?;
    let status = s
        .pointer("/type/state")
        .and_then(Value::as_str)
        .ok_or("ESPN_STATE_MISSING")?;
    if !["pre", "in", "post"].contains(&status) {
        return Err("ESPN_STATE_UNKNOWN".into());
    }
    // Delayed/postponed/suspended competitions may retain an 'in' state.
    if s.pointer("/type/name")
        .and_then(Value::as_str)
        .is_some_and(|name| {
            name.contains("POSTPONED")
                || name.contains("SUSPENDED")
                || name.contains("CANCELED")
                || name.contains("DELAYED")
        })
    {
        return Err("ESPN_GAME_NOT_ACTIVE".into());
    }
    let period = u8::try_from(
        s.get("period")
            .and_then(Value::as_u64)
            .ok_or("ESPN_PERIOD_MISSING")?,
    )
    .map_err(|_| "ESPN_PERIOD_INVALID")?;
    let clock = s
        .get("displayClock")
        .and_then(Value::as_str)
        .ok_or("ESPN_CLOCK_MISSING")?;
    let (min, sec) = clock.split_once(':').ok_or("ESPN_CLOCK_INVALID")?;
    let minutes: u16 = min.parse().map_err(|_| "ESPN_CLOCK_INVALID")?;
    let seconds: u16 = sec.parse().map_err(|_| "ESPN_CLOCK_INVALID")?;
    let maximum = match m.sport {
        Sport::NBA => 720,
        Sport::NCAAB => 1200,
    };
    let clock_seconds = minutes
        .checked_mul(60)
        .and_then(|v| v.checked_add(seconds))
        .filter(|v| *v <= maximum)
        .ok_or("ESPN_CLOCK_INVALID")?;
    if seconds >= 60 || (status == "in" && period == 0) {
        return Err("ESPN_CLOCK_INVALID".into());
    }
    Ok(SportsState {
        event_id: m.event_id.clone(),
        status: status.into(),
        period,
        clock_seconds,
        scores,
        received_ms,
        provider_ms: None,
    })
}
pub fn fetch(m: &Mapping) -> Result<Value, String> {
    if m.espn_event_id.is_empty() || !m.espn_event_id.bytes().all(|b| b.is_ascii_digit()) {
        return Err("ESPN_EVENT_ID_INVALID".into());
    }
    let sport = match m.sport {
        Sport::NBA => "nba",
        Sport::NCAAB => "mens-college-basketball",
    };
    let url = format!(
        "https://site.api.espn.com/apis/site/v2/sports/basketball/{sport}/summary?event={}",
        m.espn_event_id
    );
    let response = ureq::AgentBuilder::new()
        .timeout(Duration::from_secs(5))
        .redirects(0)
        .build()
        .get(&url)
        .call()
        .map_err(|e| format!("ESPN_HTTP:{e}"))?;
    let mut bytes = Vec::new();
    response
        .into_reader()
        .take(4_194_305)
        .read_to_end(&mut bytes)
        .map_err(|e| e.to_string())?;
    if bytes.len() > 4_194_304 {
        return Err("ESPN_RESPONSE_TOO_LARGE".into());
    }
    serde_json::from_slice(&bytes).map_err(|e| format!("ESPN_JSON:{e}"))
}
pub fn probe(args: &[String]) -> Result<(), (i32, String)> {
    let run = || -> Result<(), String> {
        if args.len() != 1 {
            return Err("usage: v1-espn MAPPING_JSON".into());
        }
        let m: Mapping =
            serde_json::from_slice(&std::fs::read(&args[0]).map_err(|e| e.to_string())?)
                .map_err(|e| e.to_string())?;
        let raw = fetch(&m)?;
        let s = parse_summary(&raw, &m, crate::engine::now_ms())?;
        println!(
            "{}",
            serde_json::json!({"mode":"OBSERVE_ONLY","state":s,"raw":raw})
        );
        Ok(())
    };
    run().map_err(|e| (78, e))
}
#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    fn mapping() -> Mapping {
        Mapping {
            event_id: "KX-event".into(),
            sport: Sport::NBA,
            tickers: ["A".into(), "B".into()],
            espn_event_id: "123".into(),
            espn_team_ids: ["1".into(), "2".into()],
            season: "2026-27".into(),
            membership_evidence: None,
            both_p5: false,
            complement_evidence: "fixture".into(),
        }
    }
    fn raw() -> Value {
        json!({"header":{"id":"123","competitions":[{"competitors":[
        {"team":{"id":"2"},"score":"50"},{"team":{"id":"1"},"score":"60"}],
        "status":{"period":3,"displayClock":"10:05","type":{"state":"in","name":"STATUS_IN_PROGRESS"}}}]}})
    }
    #[test]
    fn identity_order_and_clock_are_explicit() {
        let s = parse_summary(&raw(), &mapping(), 100).unwrap();
        assert_eq!(s.scores, [60, 50]);
        assert_eq!(s.clock_seconds, 605);
        assert_eq!(s.provider_ms, None);
    }
    #[test]
    fn mismatches_and_malformed_clock_block() {
        let mut r = raw();
        r["header"]["id"] = json!("456");
        assert!(parse_summary(&r, &mapping(), 100).is_err());
        let mut r = raw();
        r["header"]["competitions"][0]["status"]["displayClock"] = json!("10:99");
        assert!(parse_summary(&r, &mapping(), 100).is_err());
    }
}
