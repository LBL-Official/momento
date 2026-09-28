//! Exact parsers for Kalshi fixed-point dollar and count strings.
//! No floating-point arithmetic.

use momento_core::error::VenueError;
use momento_core::{Contracts, Money, Price};

/// Official prices are fixed-point dollars (up to 4 decimal places).
/// Domain [`Price`] is integer cents. Sub-cent values fail closed.
pub fn dollars_to_price_cents(raw: &str) -> Result<Price, VenueError> {
    let cents = dollars_to_whole_cents(raw)?;
    if !(0..=100).contains(&cents) {
        return Err(VenueError::Unrepresentable(format!(
            "price {raw} is outside 0..=100 cents"
        )));
    }
    Price::from_cents(cents as u16).map_err(|e| VenueError::Unrepresentable(e.to_string()))
}

/// Whole USD cents only. Sub-cent amounts fail closed.
pub fn dollars_to_money_cents(raw: &str) -> Result<Money, VenueError> {
    let cents = dollars_to_whole_cents(raw)?;
    Ok(Money::from_cents(cents))
}

fn dollars_to_whole_cents(raw: &str) -> Result<i64, VenueError> {
    let (sign, s) = if let Some(rest) = raw.strip_prefix('-') {
        (-1i64, rest)
    } else {
        (1i64, raw)
    };
    let (whole, frac) = match s.split_once('.') {
        Some((w, f)) => (w, f),
        None => (s, ""),
    };
    if whole.is_empty() || !whole.chars().all(|c| c.is_ascii_digit()) {
        return Err(VenueError::MalformedResponse(format!("bad dollars {raw}")));
    }
    if !frac.chars().all(|c| c.is_ascii_digit()) {
        return Err(VenueError::MalformedResponse(format!("bad dollars {raw}")));
    }
    if frac.len() > 6 {
        return Err(VenueError::Unrepresentable(format!(
            "dollars {raw} has more than 6 decimal places"
        )));
    }
    let whole_n: i64 = whole
        .parse()
        .map_err(|_| VenueError::MalformedResponse(format!("bad dollars {raw}")))?;
    let mut frac_cents: i64 = 0;
    for (i, ch) in frac.chars().enumerate() {
        let d = i64::from(ch.to_digit(10).unwrap_or(0));
        match i {
            0 => frac_cents += d * 10,
            1 => frac_cents += d,
            _ if d != 0 => {
                return Err(VenueError::Unrepresentable(format!(
                    "sub-cent dollars {raw} cannot map to integer cents"
                )));
            }
            _ => {}
        }
    }
    whole_n
        .checked_mul(100)
        .and_then(|v| v.checked_add(frac_cents))
        .and_then(|v| v.checked_mul(sign))
        .ok_or_else(|| VenueError::Unrepresentable(format!("dollars overflow {raw}")))
}

/// Official counts are fixed-point with 2 decimals. Fractional contracts fail closed.
pub fn count_fp_to_contracts(raw: &str) -> Result<Contracts, VenueError> {
    let (whole, frac) = match raw.split_once('.') {
        Some((w, f)) => (w, f),
        None => (raw, ""),
    };
    if whole.is_empty() || !whole.chars().all(|c| c.is_ascii_digit()) {
        return Err(VenueError::MalformedResponse(format!("bad count {raw}")));
    }
    if !frac.chars().all(|c| c.is_ascii_digit()) || frac.len() > 2 {
        return Err(VenueError::MalformedResponse(format!("bad count {raw}")));
    }
    if frac.chars().any(|c| c != '0') {
        return Err(VenueError::Unrepresentable(format!(
            "fractional count {raw} cannot map to integer contracts"
        )));
    }
    let n: u32 = whole
        .parse()
        .map_err(|_| VenueError::MalformedResponse(format!("bad count {raw}")))?;
    Ok(Contracts::from_u32(n))
}

/// Official `count_fp` has 2 decimals. Book levels may be fractional contracts
/// (venue minimum 0.01). Returns quantity in hundredths of a contract.
/// Domain [`Contracts`] fills still use [`count_fp_to_contracts`].
pub fn count_fp_to_hundredths(raw: &str) -> Result<i64, VenueError> {
    let (sign, s) = if let Some(rest) = raw.strip_prefix('-') {
        (-1i64, rest)
    } else if let Some(rest) = raw.strip_prefix('+') {
        (1i64, rest)
    } else {
        (1i64, raw)
    };
    let (whole, frac) = match s.split_once('.') {
        Some((w, f)) => (w, f),
        None => (s, ""),
    };
    if whole.is_empty() || !whole.chars().all(|c| c.is_ascii_digit()) {
        return Err(VenueError::MalformedResponse(format!("bad count {raw}")));
    }
    if !frac.chars().all(|c| c.is_ascii_digit()) || frac.len() > 2 {
        return Err(VenueError::MalformedResponse(format!("bad count {raw}")));
    }
    let whole_n: i64 = whole
        .parse()
        .map_err(|_| VenueError::MalformedResponse(format!("bad count {raw}")))?;
    let mut frac_hundredths: i64 = 0;
    for (i, ch) in frac.chars().enumerate() {
        let d = i64::from(ch.to_digit(10).unwrap_or(0));
        match i {
            0 => frac_hundredths += d * 10,
            1 => frac_hundredths += d,
            _ => {}
        }
    }
    whole_n
        .checked_mul(100)
        .and_then(|v| v.checked_add(frac_hundredths))
        .and_then(|v| v.checked_mul(sign))
        .ok_or_else(|| VenueError::Unrepresentable(format!("count overflow {raw}")))
}

/// Signed whole-contract delta. Fractional contracts fail closed.
/// Book levels use [`count_fp_to_hundredths`] instead.
pub fn signed_count_fp_to_i64(raw: &str) -> Result<i64, VenueError> {
    let (sign, rest) = if let Some(rest) = raw.strip_prefix('-') {
        (-1i64, rest)
    } else if let Some(rest) = raw.strip_prefix('+') {
        (1i64, rest)
    } else {
        (1i64, raw)
    };
    let n = count_fp_to_contracts(rest)?;
    i64::from(n.get())
        .checked_mul(sign)
        .ok_or_else(|| VenueError::Unrepresentable(format!("count overflow {raw}")))
}

/// Encode our u128 client id as a hyphenated 128-bit hex string (UUID layout).
pub fn client_order_id_to_kalshi(raw: u128) -> String {
    format!(
        "{:08x}-{:04x}-{:04x}-{:04x}-{:012x}",
        (raw >> 96) as u32,
        (raw >> 80) as u16,
        (raw >> 64) as u16,
        (raw >> 48) as u16,
        raw & 0x0000_ffff_ffff_ffff
    )
}

pub fn kalshi_to_u128(s: &str) -> Result<u128, VenueError> {
    let hex: String = s.chars().filter(|c| *c != '-').collect();
    if hex.len() != 32 || !hex.chars().all(|c| c.is_ascii_hexdigit()) {
        return Err(VenueError::Unrepresentable(format!(
            "id {s} is not 128-bit hex"
        )));
    }
    u128::from_str_radix(&hex, 16)
        .map_err(|_| VenueError::Unrepresentable(format!("id {s} is not 128-bit hex")))
}

/// Encode integer-cent domain prices as official fixed-point dollars.
pub fn price_to_dollars(price: Price) -> String {
    format!("{}.{:02}00", price.cents() / 100, price.cents() % 100)
}
pub fn signature_payload(timestamp_ms: &str, method: &str, path_without_query: &str) -> String {
    let path = path_without_query
        .split('?')
        .next()
        .unwrap_or(path_without_query);
    format!("{timestamp_ms}{method}{path}")
}
