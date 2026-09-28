from terminal_efficiency.validation.temporal_split import assign_split


def test_cut_is_temporal():
    assert assign_split("2025-02-28", "2024-2025") == "TRAIN"
    assert assign_split("2025-03-01", "2024-2025") == "VAL"
    assert assign_split("2025-10-22", "2025-2026") == "TEST_FROZEN"


def test_no_random_split_api():
    assert assign_split("2024-12-01", "2024-2025") == "TRAIN"
