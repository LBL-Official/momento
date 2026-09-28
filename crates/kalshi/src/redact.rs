//! Redact API signatures, key IDs, and token headers from logs.

const REDACTED: &str = "[REDACTED]";

const SECRET_HEADERS: &[&str] = &[
    "kalshi-access-key",
    "kalshi-access-signature",
    "kalshi-access-timestamp",
    "authorization",
    "proxy-authorization",
];

/// Returns true when a header name must never be logged in plaintext.
pub fn is_secret_header(name: &str) -> bool {
    let lower = name.to_ascii_lowercase();
    SECRET_HEADERS.contains(&lower.as_str()) || lower.contains("token")
}

/// Redact a single header value.
pub fn redact_header_value(name: &str, value: &str) -> String {
    if is_secret_header(name) {
        REDACTED.to_string()
    } else {
        redact_secrets(value)
    }
}

/// Redact PEM blocks, Kalshi auth headers, and bearer tokens from a log line.
pub fn redact_secrets(input: &str) -> String {
    let mut out = strip_pem(input);
    out = redact_header_assignments(&out, "KALSHI-ACCESS-KEY");
    out = redact_header_assignments(&out, "KALSHI-ACCESS-SIGNATURE");
    out = redact_header_assignments(&out, "KALSHI-ACCESS-TIMESTAMP");
    out = redact_header_assignments(&out, "Authorization");
    out = redact_header_assignments(&out, "MOMENTO_KALSHI_API_KEY_ID");
    out = redact_header_assignments(&out, "api_key_id");
    out = redact_header_assignments(&out, "private_key_pem");
    out = redact_bearer(&out);
    out
}

fn strip_pem(input: &str) -> String {
    let mut out = String::with_capacity(input.len());
    let mut rest = input;
    while let Some(start) = rest.find("-----BEGIN ") {
        out.push_str(&rest[..start]);
        out.push_str("[REDACTED_PEM]");
        if let Some(end_rel) = rest[start..].find("-----END ") {
            let after_end = start + end_rel + "-----END ".len();
            if let Some(nl) = rest[after_end..].find("-----") {
                rest = &rest[after_end + nl + 5..];
                continue;
            }
        }
        return out;
    }
    out.push_str(rest);
    out
}

fn redact_header_assignments(input: &str, header: &str) -> String {
    let mut hay = input.to_string();
    for name in [header, &header.to_ascii_lowercase()] {
        let prefixes = [
            format!("{name}:"),
            format!("{name}="),
            format!("\"{name}\":"),
        ];
        for prefix in prefixes {
            let mut search_from = 0;
            while let Some(idx) = hay[search_from..].find(&prefix) {
                let abs = search_from + idx + prefix.len();
                let rest = &hay[abs..];
                let skip = rest.chars().take_while(|c| c.is_whitespace()).count();
                let value_start = abs + skip;
                let value = &hay[value_start..];
                let value_len = value
                    .find('\n')
                    .unwrap_or_else(|| value.find(['"', ',', '}']).unwrap_or(value.len()));
                hay.replace_range(value_start..value_start + value_len, REDACTED);
                search_from = value_start + REDACTED.len();
            }
        }
    }
    hay
}

fn redact_bearer(input: &str) -> String {
    let lower = input.to_ascii_lowercase();
    if let Some(idx) = lower.find("bearer ") {
        let start = idx + "bearer ".len();
        let mut out = input[..idx].to_string();
        out.push_str("bearer ");
        out.push_str(REDACTED);
        let rest = &input[start..];
        let skip = rest
            .find(|c: char| c.is_whitespace() || c == '"' || c == ',')
            .unwrap_or(rest.len());
        out.push_str(&rest[skip..]);
        out
    } else {
        input.to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn redacts_signature_key_id_and_pem() {
        let raw = concat!(
            "KALSHI-ACCESS-KEY: 11111111-2222-3333-4444-555555555555\n",
            "KALSHI-ACCESS-SIGNATURE: aaaabbbbcccc\n",
            "Authorization: Bearer tok_live_secret\n",
            "api_key_id: 11111111-2222-3333-4444-555555555555\n",
            "private_key_pem: SECRETPEM\n",
            "-----BEGIN RSA PRIVATE KEY-----\nMIIEogIBAAKCAQEA\n-----END RSA PRIVATE KEY-----\n",
        );
        let redacted = redact_secrets(raw);
        assert!(!redacted.contains("11111111-2222-3333-4444-555555555555"));
        assert!(!redacted.contains("aaaabbbbcccc"));
        assert!(!redacted.contains("tok_live_secret"));
        assert!(!redacted.contains("SECRETPEM"));
        assert!(!redacted.contains("MIIEogIBAAKCAQEA"));
        assert!(redacted.contains("[REDACTED]"));
        assert!(redacted.contains("[REDACTED_PEM]"));
    }

    #[test]
    fn secret_headers_are_classified() {
        assert!(is_secret_header("KALSHI-ACCESS-SIGNATURE"));
        assert!(is_secret_header("KALSHI-ACCESS-KEY"));
        assert!(!is_secret_header("Content-Type"));
    }
}
