//! Integer-cent money. No f64.

use crate::error::W4Error;

/// Parse a Kalshi dollar string (`"0.0100"`) into integer cents.
/// Extra non-zero digits beyond two decimal places fail closed.
pub fn dollars_to_cents(raw: &str) -> Result<i32, W4Error> {
    let s = raw.trim();
    if s.is_empty() {
        return Err(W4Error::Reconstruction("empty dollar string".into()));
    }
    let (whole_s, frac_s) = match s.split_once('.') {
        Some((w, f)) => (w, f),
        None => (s, ""),
    };
    if whole_s.starts_with('-') || whole_s.starts_with('+') {
        return Err(W4Error::Reconstruction(format!(
            "signed dollar string not allowed: {raw}"
        )));
    }
    if !whole_s.chars().all(|c| c.is_ascii_digit()) || whole_s.is_empty() {
        return Err(W4Error::Reconstruction(format!("invalid dollars: {raw}")));
    }
    if !frac_s.chars().all(|c| c.is_ascii_digit()) {
        return Err(W4Error::Reconstruction(format!("invalid dollars: {raw}")));
    }
    let whole: i32 = whole_s
        .parse()
        .map_err(|_| W4Error::Reconstruction(format!("dollar overflow: {raw}")))?;
    let (frac2, rest) = if frac_s.len() >= 2 {
        (&frac_s[..2], &frac_s[2..])
    } else if frac_s.len() == 1 {
        return pad_one_frac(whole, frac_s);
    } else {
        ("00", "")
    };
    if rest.chars().any(|c| c != '0') {
        return Err(W4Error::Reconstruction(format!(
            "dollar precision finer than cents: {raw}"
        )));
    }
    let frac: i32 = frac2
        .parse()
        .map_err(|_| W4Error::Reconstruction(format!("invalid cents: {raw}")))?;
    whole
        .checked_mul(100)
        .and_then(|v| v.checked_add(frac))
        .ok_or_else(|| W4Error::Reconstruction(format!("cent overflow: {raw}")))
}

fn pad_one_frac(whole: i32, frac_s: &str) -> Result<i32, W4Error> {
    let d: i32 = frac_s
        .parse()
        .map_err(|_| W4Error::Reconstruction(format!("invalid cents: {frac_s}")))?;
    whole
        .checked_mul(100)
        .and_then(|v| v.checked_add(d * 10))
        .ok_or_else(|| W4Error::Reconstruction("cent overflow".into()))
}

/// Parse a Kalshi `_fp` quantity into integer hundredths of a contract.
pub fn fp_to_hundredths(raw: &str) -> Result<i64, W4Error> {
    let s = raw.trim();
    if s.is_empty() {
        return Err(W4Error::Reconstruction("empty fp quantity".into()));
    }
    let (whole_s, frac_s) = match s.split_once('.') {
        Some((w, f)) => (w, f),
        None => (s, ""),
    };
    let neg = whole_s.starts_with('-');
    let digits = whole_s.trim_start_matches(['-', '+']);
    if digits.is_empty() || !digits.chars().all(|c| c.is_ascii_digit()) {
        return Err(W4Error::Reconstruction(format!("invalid fp: {raw}")));
    }
    if !frac_s.chars().all(|c| c.is_ascii_digit()) {
        return Err(W4Error::Reconstruction(format!("invalid fp: {raw}")));
    }
    let whole: i64 = digits
        .parse()
        .map_err(|_| W4Error::Reconstruction(format!("fp overflow: {raw}")))?;
    let (frac2, rest) = if frac_s.len() >= 2 {
        (&frac_s[..2], &frac_s[2..])
    } else if frac_s.len() == 1 {
        let d: i64 = frac_s
            .parse()
            .map_err(|_| W4Error::Reconstruction(format!("invalid fp: {raw}")))?;
        let mut v = whole
            .checked_mul(100)
            .and_then(|x| x.checked_add(d * 10))
            .ok_or_else(|| W4Error::Reconstruction("fp overflow".into()))?;
        if neg {
            v = -v;
        }
        return Ok(v);
    } else {
        ("00", "")
    };
    if rest.chars().any(|c| c != '0') {
        return Err(W4Error::Reconstruction(format!(
            "fp precision finer than hundredths: {raw}"
        )));
    }
    let frac: i64 = frac2
        .parse()
        .map_err(|_| W4Error::Reconstruction(format!("invalid fp: {raw}")))?;
    let mut v = whole
        .checked_mul(100)
        .and_then(|x| x.checked_add(frac))
        .ok_or_else(|| W4Error::Reconstruction(format!("fp overflow: {raw}")))?;
    if neg {
        v = -v;
    }
    Ok(v)
}

pub fn optional_dollars_to_cents(raw: Option<&str>) -> Result<Option<i32>, W4Error> {
    match raw {
        None => Ok(None),
        Some(s) if s.trim().is_empty() => Ok(None),
        Some(s) => dollars_to_cents(s).map(Some),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn kalshi_four_decimal_dollars() {
        assert_eq!(dollars_to_cents("0.0100").unwrap(), 1);
        assert_eq!(dollars_to_cents("0.9900").unwrap(), 99);
        assert_eq!(dollars_to_cents("1.0000").unwrap(), 100);
        assert_eq!(dollars_to_cents("0.0000").unwrap(), 0);
        assert_eq!(dollars_to_cents("0.46").unwrap(), 46);
    }

    #[test]
    fn finer_than_cents_fails() {
        assert!(dollars_to_cents("0.0150").is_err());
        assert!(dollars_to_cents("0.011").is_err());
    }

    #[test]
    fn fp_hundredths() {
        assert_eq!(fp_to_hundredths("467.59").unwrap(), 46759);
        assert_eq!(fp_to_hundredths("1").unwrap(), 100);
        assert_eq!(fp_to_hundredths("0.50").unwrap(), 50);
    }
}
