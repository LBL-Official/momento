# INFERENCE_CONTRACT

- Every interval names its object (proportion, mean return, Sharpe).
- Wilson: binomial proportion under the stated sampling interpretation.
- Student-t: mean of observed path returns; IID-like assumption labeled; sports rows are not assumed independent.
- Bootstrap: observation resample default; game-cluster when `n_games < n` and ≥ 2 games. Not a forecast.
- Dependence disclosure: observations, unique games, tickers, dates.
- Multiple testing: disclosure of bucket count. Bonferroni / Holm / BH available; not auto-applied to the main page.
- Risk of ruin: **NOT COMPUTED** without an explicit sequential process.
