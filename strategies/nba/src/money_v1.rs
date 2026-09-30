//! Lossless money and quantity parsers for V1 recon. No f64.

use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub enum MoneyParseError {
    Empty,
    Malformed,
    TooManyDecimals,
    Overflow,
    UnitMismatch { cents: i64, dollars_cents: i64 },
}

/// Dollar string → centicents ($0.0001). Accepts up to 4 decimal places.
/// Never casts through floating point.
pub fn dollar_string_to_centicents(raw: &str) -> Result<i64, MoneyParseError> {
    let s = raw.trim();
    if s.is_empty() {
        return Err(MoneyParseError::Empty);
    }
    let (sign, s) = if let Some(rest) = s.strip_prefix('-') {
        (-1i64, rest)
    } else if let Some(rest) = s.strip_prefix('+') {
        (1i64, rest)
    } else {
        (1i64, s)
    };
    let (whole, frac) = match s.split_once('.') {
        Some((w, f)) => (w, f),
        None => (s, ""),
    };
    if whole.is_empty() || !whole.chars().all(|c| c.is_ascii_digit()) {
        return Err(MoneyParseError::Malformed);
    }
    if !frac.chars().all(|c| c.is_ascii_digit()) {
        return Err(MoneyParseError::Malformed);
    }
    if frac.len() > 4 {
        return Err(MoneyParseError::TooManyDecimals);
    }
    let whole_n: i64 = whole.parse().map_err(|_| MoneyParseError::Overflow)?;
    let mut frac_cc = 0i64;
    for (i, ch) in frac.chars().enumerate() {
        let d = i64::from(ch.to_digit(10).unwrap_or(0));
        let place = 10i64.pow(3 - i as u32);
        frac_cc = frac_cc
            .checked_add(d.checked_mul(place).ok_or(MoneyParseError::Overflow)?)
            .ok_or(MoneyParseError::Overflow)?;
    }
    whole_n
        .checked_mul(10_000)
        .and_then(|v| v.checked_add(frac_cc))
        .and_then(|v| v.checked_mul(sign))
        .ok_or(MoneyParseError::Overflow)
}

/// Kalshi `GetBalance.balance` is documented as integer cents in this crate.
/// If `balance_dollars` is also present, both must agree or recon fails closed.
pub fn reconcile_balance_cents(
    api_integer_cents: i64,
    balance_dollars: Option<&str>,
) -> Result<i64, MoneyParseError> {
    if api_integer_cents < 0 {
        return Err(MoneyParseError::Malformed);
    }
    let Some(raw) = balance_dollars.filter(|s| !s.trim().is_empty()) else {
        return Ok(api_integer_cents);
    };
    let cc = dollar_string_to_centicents(raw)?;
    let from_dollars_cents = if cc % 100 == 0 {
        cc / 100
    } else {
        return Err(MoneyParseError::TooManyDecimals);
    };
    if from_dollars_cents != api_integer_cents {
        return Err(MoneyParseError::UnitMismatch {
            cents: api_integer_cents,
            dollars_cents: from_dollars_cents,
        });
    }
    Ok(api_integer_cents)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn twenty_and_nineteen_ninety_eight_are_exact() {
        assert_eq!(dollar_string_to_centicents("20.00").unwrap(), 200_000);
        assert_eq!(dollar_string_to_centicents("19.98").unwrap(), 199_800);
        assert_eq!(dollar_string_to_centicents("20000").unwrap(), 200_000_000);
    }

    #[test]
    fn rejects_float_and_too_many_decimals() {
        assert!(dollar_string_to_centicents("20.00001").is_err());
        assert!(dollar_string_to_centicents("").is_err());
        assert!(dollar_string_to_centicents("1e2").is_err());
    }

    #[test]
    fn integer_cents_must_match_dollar_string() {
        assert_eq!(reconcile_balance_cents(2000, Some("20.00")).unwrap(), 2000);
        assert!(matches!(
            reconcile_balance_cents(2000, Some("19.98")),
            Err(MoneyParseError::UnitMismatch { .. })
        ));
    }
}
