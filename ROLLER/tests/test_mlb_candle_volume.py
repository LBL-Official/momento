"""Candle volume is copied only from parquet columns. Never from print count."""

from roller.mlb.ingest import candles_have_quality_volume, volume_from_record
from roller.research_query.compiler import compile_draft
from roller.research_query.models import ResearchStatus


def test_volume_from_record_uses_only_named_columns():
    assert volume_from_record({"print_count": 12, "quantity_hundredths": 400}, {"print_count", "quantity_hundredths"}) == ""
    assert volume_from_record({"volume": 7}, {"volume"}) == "7"
    assert volume_from_record({"volume_hundredths": 15}, {"volume_hundredths"}) == "15"
    assert volume_from_record({"volume_fp": 3}, {"volume_fp"}) == "3"
    assert volume_from_record({"volume": ""}, {"volume"}) == ""
    assert volume_from_record({}, set()) == ""


def test_empty_volume_is_not_quality_ready():
    assert candles_have_quality_volume([{"volume": ""}, {"volume": "0"}]) is False
    assert candles_have_quality_volume([{"volume": "4"}]) is True


def test_compile_mlb_candles_is_data_required(monkeypatch):
    monkeypatch.setattr(
        "roller.research_query.market_path.candles_quality_ready",
        lambda *args, **kwargs: False,
    )
    compiled = compile_draft(
        {
            "universe": {
                "sports": ["baseball"],
                "leagues": ["MLB"],
                "seasons": ["2025-26"],
                "markets": ["kalshi"],
                "marketData": ["candles"],
            },
            "entryConditions": [{"id": "e1", "family": "first_touch", "priceCents": 80}],
            "exitConditions": [{"id": "p1", "kind": "path", "family": "reach", "priceCents": 40}],
        }
    )
    assert compiled.status is ResearchStatus.DATA_REQUIRED
    assert compiled.to_dict()["observation_basis"]
    blob = " ".join(compiled.reasons).lower()
    assert "volume" in blob or "candle" in blob or "quality" in blob
