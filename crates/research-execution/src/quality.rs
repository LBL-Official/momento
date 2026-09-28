//! Execution evidence quality classification.

use momento_research_data::{NormalizedSource, OrderbookEvent};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Default, serde::Serialize, serde::Deserialize)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ExecutionDataQuality {
    #[default]
    NoExecutionData,
    FullL2,
    TopOfBookOnly,
    CandlestickOnly,
}

impl ExecutionDataQuality {
    pub fn supports_maker_simulation(self) -> bool {
        matches!(self, Self::FullL2 | Self::TopOfBookOnly)
    }

    pub fn supports_liquidation_simulation(self) -> bool {
        matches!(self, Self::FullL2 | Self::TopOfBookOnly)
    }

    pub fn as_str(self) -> &'static str {
        match self {
            Self::FullL2 => "FULL_L2",
            Self::TopOfBookOnly => "TOP_OF_BOOK_ONLY",
            Self::CandlestickOnly => "CANDLESTICK_ONLY",
            Self::NoExecutionData => "NO_EXECUTION_DATA",
        }
    }
}

pub fn classify_orderbook_event(ob: &OrderbookEvent) -> ExecutionDataQuality {
    if ob.sequence_gap {
        return ExecutionDataQuality::NoExecutionData;
    }
    if ob.source == NormalizedSource::RestCandlestick {
        return ExecutionDataQuality::CandlestickOnly;
    }
    let has_l2 = !ob.levels.is_empty()
        && matches!(
            ob.source,
            NormalizedSource::WebSocketDelta | NormalizedSource::WebSocketSnapshot
        );
    if has_l2 {
        return ExecutionDataQuality::FullL2;
    }
    if ob.yes_bid_cents.is_some() && ob.yes_ask_cents.is_some() {
        return ExecutionDataQuality::TopOfBookOnly;
    }
    ExecutionDataQuality::NoExecutionData
}

pub fn aggregate_execution_quality(samples: &[ExecutionDataQuality]) -> ExecutionDataQuality {
    if samples.is_empty() {
        return ExecutionDataQuality::NoExecutionData;
    }
    let mut full = 0usize;
    let mut top = 0usize;
    let mut candle = 0usize;
    let mut none = 0usize;
    for q in samples {
        match q {
            ExecutionDataQuality::FullL2 => full += 1,
            ExecutionDataQuality::TopOfBookOnly => top += 1,
            ExecutionDataQuality::CandlestickOnly => candle += 1,
            ExecutionDataQuality::NoExecutionData => none += 1,
        }
    }
    if full > 0 && candle == 0 && none == 0 {
        if top == 0 {
            return ExecutionDataQuality::FullL2;
        }
        return ExecutionDataQuality::TopOfBookOnly;
    }
    if full > 0 {
        return ExecutionDataQuality::TopOfBookOnly;
    }
    if top > 0 {
        return ExecutionDataQuality::TopOfBookOnly;
    }
    if candle > 0 {
        return ExecutionDataQuality::CandlestickOnly;
    }
    ExecutionDataQuality::NoExecutionData
}
