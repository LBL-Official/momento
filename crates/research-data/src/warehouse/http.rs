//! Retrying unsigned Kalshi client for research ingest.

use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

use momento_kalshi::PublicMarketClient;
use serde_json::Value;

use super::error::WarehouseError;

pub struct RateLimiter {
    min_interval: Duration,
    last: Mutex<Option<Instant>>,
}

impl RateLimiter {
    pub fn new(requests_per_second: f64) -> Self {
        let rps = if requests_per_second <= 0.0 {
            1.0
        } else {
            requests_per_second
        };
        Self {
            min_interval: Duration::from_secs_f64(1.0 / rps),
            last: Mutex::new(None),
        }
    }

    pub fn wait(&self) {
        let sleep_for = {
            let mut guard = self.last.lock().unwrap_or_else(|e| e.into_inner());
            let now = Instant::now();
            let wait = guard
                .map(|prev| {
                    let next = prev + self.min_interval;
                    next.saturating_duration_since(now)
                })
                .unwrap_or_default();
            *guard = Some(now + wait);
            wait
        };
        if !sleep_for.is_zero() {
            thread::sleep(sleep_for);
        }
    }
}

pub struct RetryingClient {
    inner: PublicMarketClient,
    limiter: RateLimiter,
    retries: u32,
}

impl RetryingClient {
    pub fn new(requests_per_second: f64, retries: u32) -> Self {
        Self {
            inner: PublicMarketClient::production_research(),
            limiter: RateLimiter::new(requests_per_second),
            retries,
        }
    }

    pub fn get_json(&self, path: &str) -> Result<Value, WarehouseError> {
        let mut attempt = 0u32;
        loop {
            self.limiter.wait();
            match self.inner.get_status_body(path) {
                Ok((200, body)) => {
                    return serde_json::from_str(&body).map_err(WarehouseError::from);
                }
                Ok((status, body)) if matches!(status, 429 | 500 | 502 | 503 | 504) => {
                    attempt += 1;
                    if attempt > self.retries {
                        return Err(WarehouseError::Api(format!(
                            "HTTP {status} after {attempt} attempts: {}",
                            truncate(&body)
                        )));
                    }
                    let wait = backoff(attempt, &body);
                    thread::sleep(if status == 429 {
                        wait.max(Duration::from_secs(2))
                    } else {
                        wait
                    });
                }
                Ok((status, body)) => {
                    return Err(WarehouseError::Api(format!(
                        "HTTP {status}: {}",
                        truncate(&body)
                    )));
                }
                Err(e) => {
                    attempt += 1;
                    if attempt > self.retries {
                        return Err(WarehouseError::api(e));
                    }
                    thread::sleep(backoff(attempt, ""));
                }
            }
        }
    }

    pub fn paginate(
        &self,
        path: &str,
        base_query: &str,
        array_key: &str,
        max_pages: u32,
    ) -> Result<(Vec<Value>, u32), WarehouseError> {
        let mut items = Vec::new();
        let mut cursor: Option<String> = None;
        let mut pages = 0u32;
        loop {
            pages += 1;
            if pages > max_pages {
                return Err(WarehouseError::Pagination(format!(
                    "{path} exceeded {max_pages} pages"
                )));
            }
            let q = match &cursor {
                Some(c) if base_query.is_empty() => format!("cursor={c}"),
                Some(c) => format!("{base_query}&cursor={c}"),
                None => base_query.to_string(),
            };
            let url = if q.is_empty() {
                path.to_string()
            } else {
                format!("{path}?{q}")
            };
            let body = self.get_json(&url)?;
            let batch = body
                .get(array_key)
                .and_then(|v| v.as_array())
                .cloned()
                .unwrap_or_default();
            items.extend(batch);
            cursor = body
                .get("cursor")
                .and_then(|c| c.as_str())
                .filter(|s| !s.is_empty())
                .map(str::to_string);
            if cursor.is_none() {
                return Ok((items, pages));
            }
        }
    }
}

fn backoff(attempt: u32, body: &str) -> Duration {
    let retry_after = body
        .to_ascii_lowercase()
        .split("retry-after")
        .nth(1)
        .and_then(|s| {
            s.chars()
                .filter(|c| c.is_ascii_digit())
                .take(3)
                .collect::<String>()
                .parse::<u64>()
                .ok()
        });
    if let Some(secs) = retry_after {
        return Duration::from_secs(secs.min(60));
    }
    let exp = 2u64.saturating_pow(attempt.min(6));
    let jitter_ms = u64::from(attempt) * 37 % 250;
    Duration::from_millis(100 * exp + jitter_ms)
}

fn truncate(s: &str) -> String {
    const N: usize = 400;
    if s.len() <= N {
        s.to_string()
    } else {
        format!("{}…", &s[..N])
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn backoff_grows() {
        assert!(backoff(1, "") < backoff(4, ""));
    }

    #[test]
    fn empty_response_is_json_error() {
        let err = serde_json::from_str::<Value>("").err();
        assert!(err.is_some());
    }
}
