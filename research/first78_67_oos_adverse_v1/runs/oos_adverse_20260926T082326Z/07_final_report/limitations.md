# Limitations

- October was already present in the v1 identity audit. Signals and settlement labels were computed there. This is a retrospective validation.
- April NBA coverage is the raw ticker subset on disk. The NCAAB market file has no 25APR dates; its APR stamps are 26APR, and candlesticks are absent.
- April stop-fail quotas on four triggered stops round to zero, so STOP_FAIL_1 and STOP_FAIL_5 match REF on that window.
- October Holm-adjusted p-values are in primary_inference_holm.json. A positive sign is not a 5% rejection after Holm.
- Assumed 78/67 fills are not maker fills. Depth flags are not a queue.
- Oracle acceptance uses later outcomes on purpose. It is a bound, not a policy.
- Random stop-failure rates are assumptions. The reported figure is the mean of 30 paths.
- With short calendars, dependence-aware intervals are fragile. A missing p-value is `P_VALUE_NOT_ESTIMABLE`.
- The launch window is not identified from these tests.
