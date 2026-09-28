//! Canonical time contract: absolute UTC internally. Never machine-local TZ.

use chrono::{DateTime, SecondsFormat, Utc};
use serde::{Deserialize, Serialize};

use crate::error::W5Error;

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub struct NormalizedInstant {
    pub source_raw: String,
    pub utc: DateTime<Utc>,
    pub offset_seconds: i32,
    pub fractional_digits: u8,
}

/// Parse a source timestamp. Offset is required (`Z` or `±HH:MM`).
/// Missing offset is INVALID — never fill with the host timezone.
pub fn normalize_source_timestamp(raw: &str) -> Result<NormalizedInstant, W5Error> {
    let s = raw.trim();
    if s.is_empty() {
        return Err(W5Error::InvalidTimestamp("empty timestamp".into()));
    }
    if !has_explicit_offset(s) {
        return Err(W5Error::InvalidTimestamp(format!(
            "timestamp missing explicit offset (refusing host TZ): {s}"
        )));
    }
    let parsed = DateTime::parse_from_rfc3339(s)
        .map_err(|e| W5Error::InvalidTimestamp(format!("unparseable RFC3339 {s}: {e}")))?;
    Ok(NormalizedInstant {
        source_raw: s.to_string(),
        utc: parsed.with_timezone(&Utc),
        offset_seconds: parsed.timezone().local_minus_utc(),
        fractional_digits: fractional_digits(s),
    })
}

fn has_explicit_offset(s: &str) -> bool {
    s.ends_with('Z') || s.ends_with('z') || offset_suffix(s).is_some()
}

fn offset_suffix(s: &str) -> Option<&str> {
    let bytes = s.as_bytes();
    for i in (0..bytes.len()).rev() {
        if bytes[i] == b'+' || (bytes[i] == b'-' && i > 10) {
            return Some(&s[i..]);
        }
    }
    None
}

pub fn fractional_digits(s: &str) -> u8 {
    let Some((_, rest)) = s.split_once('.') else {
        return 0;
    };
    rest.chars()
        .take_while(|c| c.is_ascii_digit())
        .count()
        .min(255) as u8
}

pub fn utc_rfc3339(ts: DateTime<Utc>) -> String {
    ts.to_rfc3339_opts(SecondsFormat::Millis, true)
}

/// Documented source precision. Does not invent finer resolution.
pub fn precision_label(fractional_digits: u8) -> &'static str {
    match fractional_digits {
        0 => "seconds",
        1..=3 => "milliseconds_or_finer_up_to_ms",
        _ => "sub_millisecond_source_digits_preserved_in_raw",
    }
}
