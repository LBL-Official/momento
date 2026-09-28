//! Parsers for Google Sheet experiment inputs.

use chrono::NaiveDate;

use crate::error::{BacktestError, BacktestErrorCode};

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct EntryPriceRange {
    pub minimum_entry_price_cents: u16,
    pub maximum_entry_price_cents: u16,
    pub confirmation_threshold_cents: u16,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum ExitPriceInput {
    /// Use the model's native exit rule (FIRST01 → 50% VWAP loss).
    ModelNative,
    /// Explicit loss fraction override, e.g. 50% → (1, 2) or (50, 100).
    LossFraction { numerator: u32, denominator: u32 },
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct NormalizedSeason {
    pub original: String,
    pub label: String,
    pub start_year: i32,
    pub end_year: i32,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct NormalizedTimeFrame {
    pub original: String,
    pub start: NaiveDate,
    pub end: NaiveDate,
}

pub fn parse_series_list(raw: &str) -> Result<Vec<String>, BacktestError> {
    let parts: Vec<String> = raw
        .split([',', ';'])
        .map(|s| s.trim().to_uppercase())
        .filter(|s| !s.is_empty())
        .collect();
    if parts.is_empty() {
        return Err(BacktestError::coded(
            BacktestErrorCode::UnsupportedSeries,
            "ticker list is empty",
        ));
    }
    for p in &parts {
        if momento_research_data::ResearchSport::from_series(p).is_none() {
            return Err(BacktestError::coded(
                BacktestErrorCode::UnsupportedSeries,
                format!("unsupported series '{p}'"),
            ));
        }
    }
    Ok(parts)
}

pub fn parse_season(raw: &str) -> Result<NormalizedSeason, BacktestError> {
    let trimmed = raw.trim();
    let compact = trimmed.replace(' ', "");
    let (a, b) = if let Some((left, right)) = compact.split_once('-') {
        (left, right)
    } else if let Some((left, right)) = compact.split_once('/') {
        (left, right)
    } else {
        return Err(BacktestError::coded(
            BacktestErrorCode::InvalidDateRange,
            format!("invalid season '{trimmed}'"),
        ));
    };

    let start_year = parse_year_token(a)?;
    let end_year = parse_year_token(b)?;
    if end_year != start_year + 1 && end_year != start_year {
        // Allow 2025-2026 and also identical calendar labels; reject wild gaps.
        if end_year < start_year || end_year > start_year + 1 {
            return Err(BacktestError::coded(
                BacktestErrorCode::InvalidDateRange,
                format!("invalid season year span '{trimmed}'"),
            ));
        }
    }
    let label = format!("{start_year}-{end_year}");
    Ok(NormalizedSeason {
        original: trimmed.to_string(),
        label,
        start_year,
        end_year,
    })
}

fn parse_year_token(token: &str) -> Result<i32, BacktestError> {
    if token.len() == 2 {
        let yy: i32 = token.parse().map_err(|_| {
            BacktestError::coded(
                BacktestErrorCode::InvalidDateRange,
                format!("invalid year token '{token}'"),
            )
        })?;
        return Ok(2000 + yy);
    }
    if token.len() == 4 {
        return token.parse().map_err(|_| {
            BacktestError::coded(
                BacktestErrorCode::InvalidDateRange,
                format!("invalid year token '{token}'"),
            )
        });
    }
    Err(BacktestError::coded(
        BacktestErrorCode::InvalidDateRange,
        format!("invalid year token '{token}'"),
    ))
}

/// Resolve human date ranges using season context.
///
/// Rule: months Aug–Dec map to `season.start_year`; months Jan–Jul map to
/// `season.end_year`. Explicit ISO dates (`YYYY-MM-DD`) are accepted as-is.
pub fn parse_time_frame(
    raw: &str,
    season: &NormalizedSeason,
) -> Result<NormalizedTimeFrame, BacktestError> {
    let trimmed = raw.trim();
    let (left, right) = trimmed.split_once('-').ok_or_else(|| {
        BacktestError::coded(
            BacktestErrorCode::InvalidDateRange,
            format!("time frame must be START-END, got '{trimmed}'"),
        )
    })?;
    let start = parse_date_token(left.trim(), season)?;
    let end = parse_date_token(right.trim(), season)?;
    if end < start {
        return Err(BacktestError::coded(
            BacktestErrorCode::InvalidDateRange,
            format!("time frame end before start: {start} < {end}"),
        ));
    }
    Ok(NormalizedTimeFrame {
        original: trimmed.to_string(),
        start,
        end,
    })
}

fn parse_date_token(token: &str, season: &NormalizedSeason) -> Result<NaiveDate, BacktestError> {
    if let Ok(iso) = NaiveDate::parse_from_str(token, "%Y-%m-%d") {
        return Ok(iso);
    }
    let parts: Vec<&str> = token.split('/').collect();
    if parts.len() != 2 {
        return Err(BacktestError::coded(
            BacktestErrorCode::InvalidDateRange,
            format!("invalid date token '{token}'"),
        ));
    }
    let month: u32 = parts[0].parse().map_err(|_| {
        BacktestError::coded(
            BacktestErrorCode::InvalidDateRange,
            format!("invalid month in '{token}'"),
        )
    })?;
    let day: u32 = parts[1].parse().map_err(|_| {
        BacktestError::coded(
            BacktestErrorCode::InvalidDateRange,
            format!("invalid day in '{token}'"),
        )
    })?;
    let year = if (8..=12).contains(&month) {
        season.start_year
    } else {
        season.end_year
    };
    NaiveDate::from_ymd_opt(year, month, day).ok_or_else(|| {
        BacktestError::coded(
            BacktestErrorCode::InvalidDateRange,
            format!("invalid calendar date '{token}' in season {}", season.label),
        )
    })
}

pub fn parse_entry_price_range(raw: &str) -> Result<EntryPriceRange, BacktestError> {
    let trimmed = raw.trim();
    let (lo, hi) = trimmed.split_once('-').ok_or_else(|| {
        BacktestError::coded(
            BacktestErrorCode::InvalidEntryRange,
            format!("entry price range must be MIN-MAX cents, got '{trimmed}'"),
        )
    })?;
    let minimum_entry_price_cents: u16 = lo.trim().parse().map_err(|_| {
        BacktestError::coded(
            BacktestErrorCode::InvalidEntryRange,
            format!("invalid minimum entry '{lo}'"),
        )
    })?;
    let maximum_entry_price_cents: u16 = hi.trim().parse().map_err(|_| {
        BacktestError::coded(
            BacktestErrorCode::InvalidEntryRange,
            format!("invalid maximum entry '{hi}'"),
        )
    })?;
    if minimum_entry_price_cents == 0
        || maximum_entry_price_cents == 0
        || maximum_entry_price_cents > 99
        || minimum_entry_price_cents > maximum_entry_price_cents
    {
        return Err(BacktestError::coded(
            BacktestErrorCode::InvalidEntryRange,
            format!("entry range out of bounds '{trimmed}'"),
        ));
    }
    let confirmation_threshold_cents = minimum_entry_price_cents.saturating_add(1);
    if confirmation_threshold_cents > maximum_entry_price_cents {
        return Err(BacktestError::coded(
            BacktestErrorCode::InvalidEntryRange,
            format!(
                "confirmation {confirmation_threshold_cents} exceeds max {maximum_entry_price_cents}"
            ),
        ));
    }
    Ok(EntryPriceRange {
        minimum_entry_price_cents,
        maximum_entry_price_cents,
        confirmation_threshold_cents,
    })
}

pub fn parse_exit_price_input(raw: &str) -> Result<ExitPriceInput, BacktestError> {
    let trimmed = raw.trim();
    if trimmed.eq_ignore_ascii_case("FIRST01") {
        return Ok(ExitPriceInput::ModelNative);
    }
    if let Some(pct) = trimmed.strip_suffix('%') {
        let value: u32 = pct.trim().parse().map_err(|_| {
            BacktestError::coded(
                BacktestErrorCode::UnsupportedExitOverride,
                format!("invalid exit percent '{trimmed}'"),
            )
        })?;
        if value == 0 || value > 100 {
            return Err(BacktestError::coded(
                BacktestErrorCode::UnsupportedExitOverride,
                format!("exit percent out of bounds '{trimmed}'"),
            ));
        }
        return Ok(ExitPriceInput::LossFraction {
            numerator: value,
            denominator: 100,
        });
    }
    Err(BacktestError::coded(
        BacktestErrorCode::UnsupportedExitOverride,
        format!("unsupported exit price input '{trimmed}' (use FIRST01 or e.g. 50%)"),
    ))
}
