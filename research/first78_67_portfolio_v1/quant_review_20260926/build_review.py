"""Build static charts and a self-contained head-quant review from audit evidence."""
from pathlib import Path
import csv,json,math,html,statistics,hashlib,zipfile
from collections import Counter,defaultdict
from datetime import datetime
from PIL import Image,ImageDraw,ImageFont
O=Path(__file__).resolve().parent;E=O.parent;R=E/'runs/first78_67_20260926T074540Z';C=O/'charts';C.mkdir(exist_ok=True)
def read(p):return list(csv.DictReader(p.open()))
M=json.loads((O/'audit_metrics.json').read_text());T=read(R/'01_trade_logs/trades.csv');D=read(O/'calendar_realized_returns.csv');EV=read(O/'independent_event_reconciliation.csv');MK=read(O/'all_observed_close_marks.csv');CI=json.loads((O/'conditional_cluster_intervals.json').read_text());P=json.loads((O/'defect_reproductions.json').read_text())
BLUE='#21618c';RED='#b0473d';GRAY='#65747d';BLACK='#192f3d';GRID='#dce3e8';GREEN='#26766c'
class Figure:
    def __init__(self,title,subtitle):
        self.im=Image.new('RGB',(1320,650),'white');self.d=ImageDraw.Draw(self.im);self.svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1320" height="650" viewBox="0 0 1320 650"><rect width="1320" height="650" fill="white"/>'];self.text(45,25,title,28,BLACK);self.text(45,66,subtitle,16,GRAY)
    def text(self,x,y,s,size=15,col=BLACK):
        font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',size)
        self.d.text((x,y),str(s),font=font,fill=col)
        self.svg.append(f'<text x="{x}" y="{y+size}" font-family="Arial,sans-serif" font-size="{size}" fill="{col}">{html.escape(str(s))}</text>')
    def line(self,points,col=BLUE,width=3):
        self.d.line(points,fill=col,width=width);self.svg.append(f'<polyline points="'+ ' '.join(f'{x:.2f},{y:.2f}' for x,y in points)+f'" fill="none" stroke="{col}" stroke-width="{width}"/>')
    def rect(self,x,y,w,h,col):
        self.d.rectangle((x,y,x+w,y+h),fill=col);self.svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{col}"/>')
    def save(self,name,source):
        self.text(45,606,source,13,GRAY);self.svg.append('</svg>');(C/(name+'.svg')).write_text(''.join(self.svg));self.im.save(C/(name+'.png'));return ''.join(self.svg)
def linechart(name,title,subtitle,series,labels,ylabel):
    f=Figure(title,subtitle);left=110;right=1270;top=145;bottom=540;vals=[v for _,v,c in series for v in v];lo=min(0,min(vals));hi=max(vals);span=hi-lo or 1
    def xy(i,v,n):return (left+(right-left)*i/max(1,n-1),bottom-(bottom-top)*(v-lo)/span)
    for j in range(6):
        v=lo+span*j/5;y=xy(0,v,1)[1];f.line([(left,y),(right,y)],GRID,1);f.text(18,y-9,f'{v:,.1f}' if hi<20 else f'{v:,.0f}',14,GRAY)
    f.text(18,112,ylabel,14,GRAY)
    for k,(label,v,col) in enumerate(series):
        f.rect(120+k*340,108,18,5,col);f.text(146+k*340,98,label,16,col);f.line([xy(i,x,len(v)) for i,x in enumerate(v)],col)
    for j in range(6):
        i=round(j*(len(labels)-1)/5);x=xy(i,0,len(labels))[0];f.text(x-35,550,labels[i],14,GRAY)
    return f.save(name,'Source: independent audit of saved trades/events; Nov 1, 2025–Apr 1, 2026, Pacific. X-axis: date.')
svgs={}
fixed_byday=defaultdict(int)
for t in T:fixed_byday[t['exit_pacific'][:10]]+=33374 if t['exit_reason']=='WIN_SETTLEMENT' else -17976
v=20000;fixed=[]
for d in D:v+=fixed_byday[d['day']]/100;fixed.append(v)
svgs['01_equity']=linechart('01_equity','Compounding amplifies the assumed-fill result','Same selected trades. Fixed-size curve charges exact aggregate-order cent-ceiling fees.', [('Completion-sized equity',[float(d['equity_dollars']) for d in D],BLUE),('Fixed 1,538 contracts',[x for x in fixed],GRAY)],[d['day'][5:] for d in D],'Equity ($)')
endmarks={r['local_day']:float(r['bid_marked_equity_cents'])/100 for r in MK};ddday=defaultdict(lambda:[0,0]);peak=20000
for r in MK:
    e=float(r['bid_marked_equity_cents'])/100;peak=max(peak,e);ddday[r['local_day']][0]=max(ddday[r['local_day']][0],100*(1-e/peak))
peak=20000
for r in EV:
    e=float(r['realized_equity_cents'])/100;peak=max(peak,e);ddday[r['local_day']][1]=max(ddday[r['local_day']][1],100*(1-e/peak))
svgs['02_drawdown']=linechart('02_drawdown','Price-path risk exceeds the accounting drawdown','Daily maximum drawdown from a global running peak; stale bids carried and flagged, not executable fills.', [('All observed closes',[ddday[d['day']][0] for d in D],RED),('Realized accounting',[ddday[d['day']][1] for d in D],GRAY)],[d['day'][5:] for d in D],'Drawdown (%)')
def bars(name,title,subtitle,labels,values,unit,colors=None):
    f=Figure(title,subtitle);left=380;right=1190;top=130;bottom=550;lo=min(0,min(values));hi=max(0,max(values));span=hi-lo or 1;zero=left+(right-left)*(-lo)/span
    for j in range(5):
        v=lo+span*j/4;x=left+(right-left)*(v-lo)/span;f.line([(x,top),(x,bottom)],GRID,1);f.text(x-25,bottom+12,f'{v:,.0f}',14,GRAY)
    h=(bottom-top)/len(values)
    for i,(lab,v) in enumerate(zip(labels,values)):
        y=top+i*h;end=left+(right-left)*(v-lo)/span;f.text(40,y+h*.3,lab,17);f.rect(min(zero,end),y+8,max(abs(end-zero),1),h-17,(colors or [BLUE]*len(values))[i]);f.text(min(end+8,1220),y+h*.3,f'{v:,.1f}',15,BLACK)
    f.text(600,581,unit,14,GRAY)
    return f.save(name,'Source: saved run tables and independent audit. Same historical selected population; no forecast.')
stress=read(R/'05_profitability_dissection/stresses.csv');S={x['name']:int(x['net_pnl_cents'])/100 for x in stress}
svgs['03_sensitivity']=bars('03_sensitivity','Small price changes materially reduce compounded P&L','Hypothetical prices only. Next-bar result withheld because its entry timestamp uses future information.', ['78 / 67 reference','79 / 67','80 / 67','78 / 66','78 / 65','80 / 65','Fee coefficient 0.07'],[M['net_dollars'],S['entry_plus_1'],S['entry_plus_2'],S['stop_minus_1'],S['stop_minus_2'],S['entry_plus_2_stop_minus_2'],S['fee_coef_0.07']],'Net P&L ($)')
monthly=read(O/'monthly_attribution.csv')
f=Figure('Monthly P&L attribution in the single shared portfolio','Closed-trade net P&L by actual Pacific exit month. April is one day only; not a full-month comparison.')
maxv=max(float(x['NBA_closed_trade_net_dollars'])+float(x['NCAAB_closed_trade_net_dollars']) for x in monthly);left=100;bottom=540
for j in range(6):
    val=maxv*j/5;y=bottom-380*j/5;f.line([(left,y),(1270,y)],GRID,1);f.text(10,y-9,f'{val:,.0f}',14,GRAY)
for i,r in enumerate(monthly):
    x=150+i*183;a=float(r['NBA_closed_trade_net_dollars']);b=float(r['NCAAB_closed_trade_net_dollars']);ha=380*a/maxv;hb=380*b/maxv;f.rect(x,bottom-ha,95,ha,BLUE);f.rect(x,bottom-ha-hb,95,hb,GREEN);f.text(x-5,553,r['month']+('*' if r['partial_month']=='True' else ''),15)
f.text(15,113,'Net P&L ($)',14,GRAY);f.text(200,105,'NBA',17,BLUE);f.text(320,105,'NCAAB',17,GREEN)
svgs['04_monthly']=f.save('04_monthly','Source: monthly_attribution.csv. X-axis: Pacific exit month. *April 1 only. Attribution is not separate funding.')
svgs['05_outcomes']=bars('05_outcomes','Strategy wins and terminal team wins are different outcomes','330 winning settlements; 317 stopped trades, of which 212 later won. Zero held-to-zero in this sample.', ['Win settlement','Stop, later team win','Stop, later team loss'],[330,212,105],'Trades (count)',[BLUE,GRAY,RED])
gaps=[int(t['stop_gap_cents']) for t in T if t['stop_gap_cents']];overs=[int(t['overshoot_cents']) for t in T]
svgs['06_price_gaps']=bars('06_price_gaps','The observed closes differ from assumed fills','Entry bid is not a buyable quote. Stop-close prices are evidence of gaps, not guaranteed sale prices.', ['Mean entry bid above 78¢','Mean stop bid below 67¢','Maximum stop bid below 67¢'],[statistics.mean(overs),statistics.mean(gaps),max(gaps)],'Price difference (cents per contract)',[BLUE,RED,GRAY])

findings=[
('Q01','CRITICAL','Statistical significance is unsupported','complete_plan_outputs.py:75','Bootstrap resamples the observed nonzero-mean distribution, counts means <=0 and calls that a p-value. It does not simulate a null. Holm cannot repair invalid input p-values.','Withdraw reported p-values and Holm claims; retain conditional percentile intervals with limitations.'),
('Q02','CRITICAL','Primary calendar simulator changes the calendar','src/first78/stats.py:142','Every sampled active day advances by 7 days + 5 seconds in the 7-day setting. Zero-candidate calendar days are omitted and each day is independently anchored to its first signal. The path-subsample repeats this error.','Rebuild complete local-day blocks, including empty days, consistent offsets and tails. Rerun portfolio distributions before interpreting them.'),
('Q03','HIGH','Next-bar proxy uses future price at the earlier entry time','src/first78/materialize.py:91','use_next_bar_price changes price but not signal_ts; caller does not also request delay_one_bar. Quantity therefore uses a price not yet known.','Withdraw $65,814.78 as a causally valid replay; re-extract subsequent stop chronology after delayed entry.'),
('Q04','HIGH','Risk was measured only at trade/cash events','finish_report_artifacts.py:410','Marks are sampled only on event rows; source drops rows when marks are missing and does not publish mark-age flags. All observed held closes show a larger diagnostic drawdown.','Publish a full observation-time series, retain missing/stale states, and separate carried-mark diagnostics from reliable MTM.'),
('Q05','LIMITATION','Population conditions on later FIRST80 qualification','contract.json','The locked 936 is the requested historical population, not a prospective FIRST78 opportunity set. Preserving it is correct for the conditional study.','Do not generalize the expectancy. Define and validate a separate future-information-free prospective population.'),
('Q06','HIGH','No executable economics or available-size evidence','01_trade_logs/trades.csv','434 entry closes exceed 78; stop close gaps average 3.46 cents. All modeled quantities assume fills without measured depth or queue.','Keep threshold accounting explicitly hypothetical; collect executable quotes and actual authorized order evidence before forecasting.'),
('Q07','HIGH','The survival deliverable is an entry-cell frequency model','complete_plan_outputs.py:139','One row per trade, entry price distance and period-clock bins; no snapshot hazard, recent volatility covariate, censoring model or time-varying competing risks. Duration is last minus first observed close rather than cash/settlement exit time.','Label as an empirical baseline only; implement the required time-dependent model and validate against a training-only baseline.'),
('Q08','HIGH','Unfinished outputs are presented as a completed package','finish_report_artifacts.py:527','Identical trade rollups populate six different report sections. Nested refits were not run; regime counts are not a regime-switching simulator. Several required named files are absent.','Use deliverable_coverage.csv; distinguish missing implementation from unavailable data, and issue a versioned repaired run.'),
('Q09','MEDIUM','Daily Sharpe is based on the wrong denominator','run_backtest.py','Original divides P&L by starting capital and initially omits zero days. This is not prior-day portfolio equity return.','Use equal-interval prior-equity returns, with zero days and separate realized versus MTM series. Annualization is convention, not a year of evidence.'),
('Q10','MEDIUM','Variant trade exports misstate their actual entry price','src/first78/portfolio.py:281','Returned entry_price_cents is the function default even when candidate-specific price funds principal. A probe buys at 82 but exports 78.','Store actual per-position price and reconcile exported price times quantity to principal in every variant.'),
('Q11','MEDIUM','Unresolved candidates are excluded using future completion availability','src/first78/materialize.py:159','build_candidates omits UNRESOLVED before admission; the engine rejects unsupported exits. It cannot represent unresolved holdings or voids as specified. No such baseline cases were found here.','Retain unresolved positions and explicit terminal valuation states; add void and partial-fill tests before supported execution scenarios.'),
('Q12','MEDIUM','Chronology tests and tie ordering are incomplete','src/first78/portfolio.py:98','Equal-time candidates use insertion sequence rather than the required game/contract ID sort. The engine permits entry_ts == exit_ts; one-bar delay can reuse the original stop bar.','Add deterministic tie sorting and strictly later stop evidence; test overlapping epoch changes, pending orders and partial exits.'),
('Q13','HIGH','Reproducibility and freeze evidence are incomplete','manifest.json','Only four input hashes are stored; raw candles, markets and PBP are not comprehensively hashed. Root contract differs from run contract; supplements overwrite a fixed run and docs claim pre-inspection freezing without an immutable chronology.','Archive complete permissible manifests, source version and dirty diff, immutable contracts, configs and versioned outputs. A historical freeze cannot be recreated retroactively.'),
('Q14','MEDIUM','Clock and resolution diagnostics are retrospective','src/first78/clocks.py:95','NBA walls are interpolated from period/replay knots, not historical receive times; as-of lookup on a modeled wall does not establish point-in-time availability. Settlement volatility ends at settlement_ts without explicit resolution-jump removal.','Keep retrospective clock uncertainty explicit, and censor volatility windows before resolution mechanics.'),
('Q15','MEDIUM','NCAAB 600-second prose contradicts the implementation','assumptions.md','Code assigns exactly 600 seconds to H1_2 and H2_2, while prose says the first ten minutes. FIRST78 uses H1_2/H2_1, so the exact boundary matters.','Use the reference code boundaries explicitly and test both halves at 600 seconds.'),
]
with (O/'findings_register.csv').open('w') as f:w=csv.writer(f);w.writerow(['id','severity','finding','source','evidence','remediation']);w.writerows(findings)
code=lambda p:f'[{p}]({E/p})'
money=lambda x:f'${x:,.2f}'
report=f'''# FIRST78→67 — independent head-quant assessment

Review date: September 26, 2026. Source run: `first78_67_20260926T074540Z`. Author role: independent quant review of the saved Cursor artifacts and their implementation. This is an audit, not a new strategy version or live authorization.

## Decision

**Accept the baseline as reproducible conditional threshold accounting. Do not accept this package as validated executable profitability, a reliable portfolio risk forecast, or a completed implementation of the original research specification.**

I reproduced all 647 baseline trades from the existing source readers, independently reconstructed every cash event, and passed 6,472 audit checks. Net {money(M['net_dollars'])} is not a simple addition or fee error. It is the result of favorable modeled payoff economics on a FIRST80-conditioned population, fixed 78¢/67¢ assumed prices, and repeated reinvestment. Several surrounding validation claims are materially defective: invalid p-values, calendar-distorting simulation, a next-bar timing leak and incomplete marked risk. The earlier completion claims should be superseded by this assessment.

## Scope and evidence

All {M['files']} files in the run were read and fingerprinted; CSVs were parsed, JSON validated, all trade TXT records ingested, and narrative documents examined. There were no parse errors or empty files. The file inventory records row counts and hashes; duplicate-content groups prevent repeated views from inflating totals. I also inspected the experiment's Python modules, three report generators, tests, root contract/schema/inventory/protocol, and the referenced clock implementations. Original artifacts were not edited. Sealed Austin cohorts, live control and orders were not accessed.

The source replay deliberately reuses the original source readers and clock conventions. Agreement establishes reproducibility; it does not independently validate exchange timestamps, raw-feed authenticity or point-in-time clock reconstruction. The cash calculation is independent of the original portfolio engine. Supplemental intervals and chart calculations are review diagnostics on already examined data, not a prospectively frozen experiment.

## What the ledger supports

The requested historical population is 936 games: 604 NBA and 332 NCAAB. Candidate exclusions are 104 date-window, 179 first-cross outside-window, and six no-cross classifications. These are mutually exclusive program reasons, not proof that the source underwent a complete independent missing-data funnel. The final 647 positions comprise 382 NBA and 265 NCAAB. All were admitted; no baseline cap or cash rejection occurred. The maximum verified open count is six under the supplied close/cash assumptions.

Gross P&L is {money(M['gross_dollars'])}; charged fees are {money(M['fees_dollars'])}; net is {money(M['net_dollars'])}. Ending cash and realized accounting equity are {money(M['ending_cash_dollars'])}, with no remaining baseline holdings/receivables. Net divided by $20,000 is {M['net_dollars']/20000*100:,.2f}% for this historical scenario, not an expected annual return. NBA contributes $120,607.86 and NCAAB $114,880.32 to this one shared portfolio.

Checks independently covered principal = quantity × entry price, aggregate-order ceiling fees, gross minus fees, 6% frozen-balance integer sizing at every entry, completion-driven balance updates, entry-before-exit chronology, nonnegative cash/receivables, open-count limits, and cash + receivables + cost principal at every event. All 13 original acceptance tests also passed. Passing those narrow fixtures does not cover the missing partial-fill, void, uncertainty or full mark-path requirements.

There are 330 profitable settlements and 317 negative stop exits, no flats and no held-to-zero settlements. Positive strategy rate is {M['positive_rate']*100:.2f}%; terminal team win rate is {M['terminal_win_rate']*100:.2f}%. Of the 317 stopped positions, 212 later won and 105 later lost. A stopped-then-winning team remains a negative strategy outcome. These observed zero held-to-zero losses do not mean stops prevent failed-exit losses.

## Why the dollar result is so large

At the opening balance, 1,538 contracts cost $1,199.64 plus $4.62 entry fee. A winning settlement nets $333.74 and a modeled 67¢ stop nets −$179.76. That binary example breaks even at 35.0068% profitable outcomes; this selected sample records 51.00%. Mean trade-level net P&L per contract is 5.3415¢. Increasing quantities after each tenth completion amplifies that modeled edge; sizes reach 18,036 contracts.

Keeping every admitted trade at exactly 1,538 contracts and applying exact rounded aggregate fees gives **{money(M['fixed_1538_net_dollars'])}**, versus {money(M['net_dollars'])} with resizing. This is a fixed-quantity economic diagnostic on the same entries and exits, not a new admission replay. The earlier approximately $53,152 estimate scaled rounded fees linearly; the exact fixed-size figure is $53,150.28.

![Equity comparison](charts/01_equity.png)

The growth is highly sensitive to assumed price concessions: 434 of 647 entry bids already exceed 78¢; their overall mean is {M['average_entry_bid']:.4f}¢. The stop-trigger bid averages {67-M['average_stop_gap']:.4f}¢, yet the reference credits a 67¢ sale. The worst observed stop trigger is 25¢, a 42¢ gap. These are quote-close observations, not guaranteed executable prices; a bid is particularly not a buyable entry quote.

![Price gaps](charts/06_price_gaps.png)

## Sensitivity assessment

The saved adverse-price scenarios retain the 78/67 signal policy but worsen assumed transaction prices and rerun sizing. Entry +1¢ reduces net to $135,557.08; entry +2¢ to $75,525.17. Joint entry 80¢ / stop sale 65¢ gives $39,725.73, an approximately 83% reduction from reference. The user-fee coefficient 0.07 scenario gives $106,370.83. They are useful conditional cost sensitivities; none verifies actual historical fee eligibility, size or fills. Contractual settlement payouts are unchanged.

**Withdraw the $65,814.78 next-bar number as a causally valid replay.** `candidate_from_contract(use_next_bar_price=True)` uses the next observed bid to size at the original signal timestamp. A minimal reproduction uses a price from timestamp 160 at timestamp 100. Moreover, the trade exporter labels default 78¢ even when actual principal was funded at another candidate price. One-bar-delay mode is separate and can allow entry and stop at the same timestamp; the original stop is not always recomputed strictly after entry. Changing a label to PRICE_PROXY did not correct these chronology errors.

![Cost sensitivity](charts/03_sensitivity.png)

## Risk, marks and calendar performance

The independent realized-accounting drawdown reproduces 6.5106%, or $8,801.50 from its relevant peak. Original bid marks at portfolio event times report about 6.92%. I rebuilt {M['mark_points']:,} observation/event timestamps while holdings are open: the carried-bid-close diagnostic drawdown rises to **{M['all_close_mark_dd']['fraction']*100:.4f}%**, or **{money(M['all_close_mark_dd']['dollars'])}**. This compares end-of-timestamp marks against a global peak including opening equity.

This 7.44% is still not clean executable liquidation risk: {M['mark_points_with_stale']:,} timestamps have a carried mark older than 60 seconds; maximum mark age is {M['max_mark_age_seconds']/60:.2f} minutes. Missing/stale quote risk, price moves within a minute and order-size impact remain unresolved. The audit CSV retains mark ages rather than silently declaring the path complete.

![Drawdown](charts/02_drawdown.png)

The original Sharpe used daily P&L divided by initial capital, initially on active dates only. A separate audit diagnostic uses 152 Pacific calendar days from November 1 through April 1, includes 12 zero-change days, and computes realized-equity return from the previous day's equity. Unannualized Sharpe is {M['calendar_sharpe_unannualized']:.4f}; applying sqrt(365) gives {M['calendar_sharpe_annualized']:.4f}. This is a corrected **realized-accounting** statistic, not MTM Sharpe and not a prospective performance claim. It remains conditional on the same selected sample and hypothetical fills; I have not established dependence-adjusted uncertainty for it.

![Monthly attribution](charts/04_monthly.png)

Monthly closed-trade attribution totals: November $11,057.01; December $12,780.90; January $40,464.99; February $50,884.14; March $104,646.14; April 1 only $15,655.00. This pattern partly reflects increasing exposure, not proof that later months have a stronger edge. The top five signal dates contribute 24.15% of total net and the top ten 39.03%; top ten games contribute 15.76%. These concentration ratios use final trade P&L attributed to entry dates, not a daily MTM return definition.

## Does the 67¢ stop add value?

The same-entry, same-quantity stop-minus-hold sum is −$51,075.03. That is a dollar-weighted economic comparison using quantities determined by the stop strategy. It is not the result of an independently cash-funded hold portfolio. The full saved hold replay admits 645 and nets $203,108.14; the stop portfolio exceeds it by $32,379.04, combining different timings, admissions, quantities and resizing.

At an unweighted trade-level per-contract denominator, the paired stop effect is only **{CI['paired_stop_minus_hold']['mean']:.4f}¢**. A 10,000-draw local-signal-day clustered percentile interval is **[{CI['paired_stop_minus_hold']['ci95'][0]:.4f}, {CI['paired_stop_minus_hold']['ci95'][1]:.4f}]¢** at 95%. This spans zero. The much larger dollar difference reflects when larger quantities occurred and must not be presented as a uniform per-contract stop penalty. The data do not establish a robust standalone stop advantage or disadvantage. No policy change is recommended from this reviewed sample.

![Outcomes](charts/05_outcomes.png)

## Statistical inference: what survives and what does not

Conditional day-cluster percentile intervals can describe variability in the selected historical trade mean. My independent 10,000-draw recomputation gives combined mean 5.3415¢ and 95% interval [{CI['Universe']['ci95'][0]:.4f}, {CI['Universe']['ci95'][1]:.4f}]¢; NBA mean 4.9187¢ with [{CI['NBA']['ci95'][0]:.4f}, {CI['NBA']['ci95'][1]:.4f}]¢; NCAAB mean 5.9510¢ with [{CI['NCAAB']['ci95'][0]:.4f}, {CI['NCAAB']['ci95'][1]:.4f}]¢. These are day-cluster diagnostics, not contiguous multi-day dependence protection, not a portfolio-return confidence interval, and not a correction for population selection or prior research reuse.

The original one-sided p-value counts bootstrap means <=0 after resampling from the observed distribution. No null distribution is constructed. Adding one to numerator and denominator does not make it a valid Monte Carlo null test; Holm adjustment does not cure this. **The p≈0.0001 / Holm≈0.0003 significance claims should be removed.** I provide no replacement significance claim.

The stated timing-null blocker is also too broad. FIRST80 selection prevents extrapolation to all prospective FIRST78 opportunities, but does not alone prove that every explicitly conditional timing comparison is unidentifiable. Such a comparison still needs a defensible matched support set, executable/price assumptions and causal follow-up. Those components were not implemented here.

## Monte Carlo: the primary simulation is not a valid calendar replay

A direct probe of `block_bootstrap_equity(block=7)` gives **604,805 seconds between adjacent sampled days**, rather than approximately one local day. The code adds `86400 * block + 5` after every sampled day, not after a whole seven-day block. It uses active days rather than all calendar days, and rebases every day's first arrival to the same time. This distorts cross-day overlap, capacity pressure, settlement funding and simulated horizon. The 400-path risk subsample repeats the same bug.

Therefore the original median $229,554.86, tail quantiles, no-terminal-loss result, and simulated drawdown frequencies are **not approved portfolio-risk estimates**. Monte Carlo standard error only measures numerical noise conditional on that flawed generator. More paths cannot fix it. Family A's fixed-dollar permutations and family B's dollar bootstrap are labeled reduced-form and may be read as such, but they are not capital-feasible account paths. Family D is transition counts, not an implemented regime-switching simulation. Family E is a deterministic stress grid, not an estimated tail mixture. Nested parameter uncertainty was not run.

## Markov and within-game modeling

Entry-order combined outcome transitions give P(next win | win)=48.33% and P(next win | loss)=53.63%. On the observed W/L subchain, both directions and self-loops exist; its stationary W occupancy is about 50.93% with zero numerical residual at shown precision. This is descriptive trade-step occupancy. F has no observations; the full W/L/F matrix has an undefined row, and stationary convergence for that three-state process is not established. Overlapping games, sport composition and time-varying sizing make a synchronized-market interpretation inappropriate.

The within-game artifact is not the mandated survival/competing-risk model. It is one observation per trade, binned by entry distance and period time; it omits recent-volatility covariates, changing game-time hazards, game-clustered snapshot dependence, censoring and proper stop-versus-terminal transitions. Its duration uses observed path endpoints rather than settlement cash time. On 279 scored later-segment observations, Brier is {P['later_model_brier']:.6f}; a training-only constant base rate scores {P['fit_base_rate_brier']:.6f}, and a constant 0.5 scores 0.25. The model does not improve this probability-score baseline. This does not by itself establish absence of discrimination; Brier measures calibration and resolution jointly. The later split remains previously examined development data.

## Data-quality and contract details

The scan filters crossed/wide quotes before both entry and stop detection. Of 224 earlier low-bid observations excluded by that quality convention, 222 are 0¢ bid / 100¢ ask empty-book-like records; the other two have 20¢ and 26¢ spreads. These should not simply be reclassified as executable stops. They demonstrate why signal quality, disappearance of liquidity and failed-stop behavior need separate explicit rules. No baseline stop was found after the recorded settlement timestamp. The audit preserves these observations separately.

NCAAB has halves: H1_2 includes exactly 600 seconds remaining and H2_1 excludes exactly 600. The prose claiming the 600-second boundary belongs to the first ten contradicts the code. NBA period clocks use retrospective interpolation; an as-of lookup over modeled walls is not historical receive-time availability. The reference scan and inherited labels were preserved, not promoted into a deployable real-time specification.

## Completeness and auditability

All seven named report folders exist, but folder existence is not completion. Six sections contain repeated trade-period rollups generated by the same function; they are views, not independent statistical, simulation or model validation results. The run lacks several specified artifacts, including canonical trade-path observations, strict-batch records, cash-reconciliation and exposure tables, paired effect intervals, fill-selection analysis and machine-readable launch/forecast gates. Some metadata exists only at the experiment root, outside the run/review subfolder. `deliverable_coverage.csv` records exact existence checks; absence of a named file is distinguished from a related result elsewhere.

The original manifest hashes four sources but not the full raw candle/market/PBP inputs, and has no commit or dirty diff. Supplemental scripts target and rewrite the same historical run. Root and run contract copies differ. A protocol field asserting `written_before_outcome_inspection` cannot itself prove historical preregistration. The review records current hashes and does not manufacture a past freeze. The original review_bundle directory is an index/questions/summary, not a self-contained copy of all evidence.

## Head-quant assessment and repair priorities

1. Preserve the reproduced baseline as a **conditional assumed-fill reference** and issue a versioned erratum withdrawing the invalid p-values, primary MC inference and next-bar timing claim.
2. Repair chronology, candidate-specific price exports, deterministic tie order, same-bar stop handling, unresolved/void bookkeeping and source-observation audit trails; add targeted regression tests before generating a new run.
3. Rebuild observation-time MTM with missing/stale rules, correct calendar block episodes and admission-aware simulations. Reconcile every variant and preserve immutable versioned source/config/output manifests.
4. Treat entry-cell probabilities and stationary outcome occupancy as descriptive until the mandated time-dependent survival model, prospective validation protocol, dependence-aware inference and nested uncertainty are implemented.
5. Define a separately registered prospective FIRST78 population without later FIRST80 membership and measure executable costs, fills, cash releases and capacity. Do not tune the 78/67 thresholds to these audit results.

For November 1, 2026–April 1, 2027, **launch performance expectation remains NOT_YET_IDENTIFIABLE**. Accounting validity is a pass within the supplied assumptions; population transportability, execution, capacity and prospective validation remain insufficient. Risk limits and live authorization remain user decisions, not outputs of this audit.

## External methodological context

[Bailey et al., The Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf) motivates treating repeated strategy selection as a distinct uncertainty problem; no numerical PBO is estimated here because complete trial history is absent. [Kalshi fee-rounding documentation](https://docs.kalshi.com/getting_started/fee_rounding), consulted September 26, 2026, is current documentation, not proof of the historical series fee schedule. All fee computations above remain the user-imposed hypothetical formula.

## Reproduction and review files

Run `PYTHONDONTWRITEBYTECODE=1 ROLLER/.venv/bin/python research/first78_67_portfolio_v1/quant_review_20260926/audit.py`, then `probes.py` and `diagnostics.py` with the same interpreter. Render with the bundled Python executable and `build_review.py` (Pillow dependency). Exact original source hashes are recorded in `file_inventory.csv`; current review results are in `audit_metrics.json`; independent event evidence is `independent_event_reconciliation.csv`. `checks.csv` contains every audit check, `defect_reproductions.json` the minimal bug demonstrations, and `findings_register.csv` the prioritized remediation record. No repaired strategy or live trading is implied by this package.
'''
# Make source/figure references absolute for desktop navigation.
for name in svgs:report=report.replace(f'(charts/{name}.png)',f'({C/(name+".png")})')
(O/'HEAD_QUANT_ASSESSMENT.md').write_text(report)

# Standalone HTML: all figures/data embedded, usable offline, with trade filtering.
cards=''.join(f'<div><small>{label}</small><strong>{val}</strong></div>' for label,val in [('Arithmetic checks','6,472 passed'),('Reproduced trades','647 / 647'),('Reference net P&L','$235,488'),('Audited mark drawdown','7.44%*')])
findhtml=''.join(f'<tr><td>{a}</td><td>{b}</td><td><b>{c}</b><p>{e}</p></td><td>{f}</td></tr>' for a,b,c,d,e,f in findings)
paragraphs=[]
for line in report.splitlines():
    if line.startswith('!['):continue
    if line.startswith('### '):paragraphs.append('<h3>'+html.escape(line[4:])+'</h3>')
    elif line.startswith('## '):paragraphs.append('<h2>'+html.escape(line[3:])+'</h2>')
    elif line.startswith('# '):continue
    elif line.strip():paragraphs.append('<p>'+html.escape(line).replace('**','')+'</p>')
tradejson=json.dumps([{k:r[k] for k in ['trade_id','sport','matchup','signal_pacific','contracts','net_pnl_cents','exit_reason','observed_entry_close_cents','stop_gap_cents']} for r in T]).replace('</','<\\/')
page='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>FIRST78–67 | Independent quant assessment</title><style>
body{margin:0;background:#f5f7f9;color:#192f3d;font:16px/1.6 system-ui,sans-serif}main{max-width:1260px;margin:auto;padding:36px}h1{font-size:32px;line-height:1.2}h2{margin-top:38px}header{border-bottom:2px solid #192f3d;padding-bottom:22px}.verdict{border-left:4px solid #b0473d;padding:15px 22px;background:white}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:20px;margin:25px 0}.metrics strong{display:block;font-size:26px}.metrics small{color:#65747d}figure{margin:24px 0;background:white}svg{width:100%;height:auto}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:12px;text-align:left;border-bottom:1px solid #dce3e8;vertical-align:top}td p{margin:4px 0}input,select,button{font:inherit;padding:8px;margin:8px}details{background:white;padding:16px;margin:24px 0}summary{cursor:pointer;font-weight:600}nav a{margin-right:24px;color:#21618c}small{color:#65747d}.scroll{overflow:auto;max-height:540px}article{max-width:1000px} @media(max-width:700px){main{padding:18px}.metrics{grid-template-columns:1fr 1fr}}@media print{details{display:block}input,button{display:none}.scroll{max-height:none}}
</style><main><header><small>INDEPENDENT QUANT REVIEW · 26 SEPTEMBER 2026</small><h1>Reproducible accounting.<br>Unvalidated execution and inference.</h1><p>FIRST78→67 · source run first78_67_20260926T074540Z · 936-game FIRST80-conditioned population</p><nav><a href="#charts">Charts</a><a href="#findings">Findings</a><a href="#trades">Trade explorer</a><a href="#report">Full assessment</a></nav></header>
<p class="verdict">The $235,488 hypothetical net reconciles. Do not treat it as executable profit or a 2026–27 forecast. The primary simulator has a calendar bug, significance claims lack a valid null, and the next-bar scenario uses future information.</p>'''+f'<section class="metrics">{cards}</section><small>*Carried-bid-close diagnostic; 3,553 marked timestamps have a quote older than 60 seconds.</small><section id="charts">'+''.join('<figure>'+s+'</figure>' for s in svgs.values())+f'</section><section id="findings"><h2>Prioritized findings</h2><table><thead><tr><th>ID</th><th>Severity</th><th>Evidence</th><th>Required remediation</th></tr></thead><tbody>{findhtml}</tbody></table></section>'+'''<section id="trades"><h2>647 audited trades</h2><label>Sport <select id="sport"><option>All</option><option>NBA</option><option>NCAAB</option></select></label><label>Search <input id="search" placeholder="Trade ID or matchup"></label><p id="count"></p><div class="scroll"><table><thead><tr><th>ID</th><th>Sport / matchup</th><th>Pacific signal</th><th>Contracts</th><th>Net $</th><th>Exit</th><th>Bid close ¢</th><th>Stop gap ¢</th></tr></thead><tbody id="rows"></tbody></table></div></section>'''+ '<details id="report"><summary>Read the full head-quant assessment</summary><article>'+''.join(paragraphs)+'</article></details>'+f'<footer><p>Audit artifacts: {html.escape(str(O))}</p><p>Original source preserved. Historical assumed fills only. No orders, monitoring or future review arranged.</p></footer></main><script>const trades={tradejson};'+'''
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));function render(){let sport=document.getElementById('sport').value,q=document.getElementById('search').value.toLowerCase();let rows=trades.filter(t=>(sport==='All'||t.sport===sport)&&(t.trade_id+' '+t.matchup).toLowerCase().includes(q));document.getElementById('count').textContent=rows.length+' trades · hypothetical net $'+(rows.reduce((a,t)=>a+Number(t.net_pnl_cents),0)/100).toLocaleString(undefined,{maximumFractionDigits:2});document.getElementById('rows').innerHTML=rows.map(t=>'<tr>'+[t.trade_id,t.sport+' · '+t.matchup,t.signal_pacific,t.contracts,(Number(t.net_pnl_cents)/100).toFixed(2),t.exit_reason,t.observed_entry_close_cents,t.stop_gap_cents||'—'].map(x=>'<td>'+esc(x)+'</td>').join('')+'</tr>').join('')}document.getElementById('sport').onchange=render;document.getElementById('search').oninput=render;render();</script></html>'''
(O/'review.html').write_text(page)
(O/'README.md').write_text('# Independent review\n\nOpen [interactive review](review.html) or [full assessment](HEAD_QUANT_ASSESSMENT.md).\n\nSix charts are available as PNG and SVG in charts/. Audit scripts write only to this review folder. The original run is unchanged.\n')
summary={k:v for k,v in M.items() if k!='original_input_hashes'};summary['assessment']='CONDITIONAL_ACCOUNTING_REPRODUCED; EXECUTION_AND_INFERENCE_NOT_VALIDATED';summary['invalidated_claims']=['primary calendar Monte Carlo','p-values and Holm significance','causal next-bar replay'];(O/'review_summary.json').write_text(json.dumps(summary,indent=2))
print('Wrote assessment, six PNG/SVG charts, findings register and offline review.html')
