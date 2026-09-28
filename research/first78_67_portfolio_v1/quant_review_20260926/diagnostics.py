from pathlib import Path
import csv,json,random,statistics,math,hashlib
from collections import defaultdict,Counter
O=Path(__file__).resolve().parent;E=O.parent;R=E/'runs/first78_67_20260926T074540Z'
def read(p):return list(csv.DictReader(p.open()))
def out(n,v):(O/n).write_text(json.dumps(v,indent=2))
t=read(R/'01_trade_logs/trades.csv');pair=read(R/'05_profitability_dissection/paired_stop_vs_hold.csv');byid={r['trade_id']:r for r in t}
def bootstrap(rows,value,seed=78267):
    g=defaultdict(list)
    for r in rows:g[byid[r['trade_id']]['signal_pacific'][:10]].append(value(r))
    units=list(g.values());rng=random.Random(seed);means=[]
    for _ in range(10000):
        sample=[units[rng.randrange(len(units))] for _ in units]
        means.append(sum(map(sum,sample))/sum(map(len,sample)))
    means.sort()
    return dict(mean=statistics.mean(value(r) for r in rows),ci95=[means[249],means[9749]],ci90=[means[499],means[9499]],days=len(g),trades=len(rows),seed=seed,replicates=10000,method='percentile bootstrap of local signal-day clusters; no p-value; conditional sample')
cis={s:bootstrap([r for r in t if s=='Universe' or r['sport']==s],lambda r:int(r['net_pnl_cents'])/int(r['contracts'])) for s in ['Universe','NBA','NCAAB']}
cis['paired_stop_minus_hold']=bootstrap(pair,lambda r:int(r['paired_diff_cents'])/int(byid[r['trade_id']]['contracts']))
out('conditional_cluster_intervals.json',cis)
states={}
for ordering in ['entry_sequence','completion_sequence']:
    for sport in ['Universe','NBA','NCAAB']:
        seq=sorted([r for r in t if sport=='Universe' or r['sport']==sport],key=lambda x:int(x[ordering]));labels=['W' if int(r['net_pnl_cents'])>0 else 'L' for r in seq];c=Counter(zip(labels,labels[1:]));nw=c['W','W']+c['W','L'];nl=c['L','W']+c['L','L'];a=c['W','L']/nw;b=c['L','W']/nl;pi=b/(a+b)
        states[sport+'_'+ordering]=dict(n=len(seq),counts={x+y:c[x,y] for x in ['W','L'] for y in ['W','L']},p_win_after_win=1-a,p_win_after_loss=b,stationary_W=pi,stationary_L=1-pi,residual=abs(pi*(1-a)+(1-pi)*b-pi),interpretation='Observed W/L subchain only; F unobserved and full 3-state stationary solution undefined; descriptive, not validated forecasting')
out('descriptive_markov_audit.json',states)
requirements={
 'root_run_metadata':['README.md','schemas.json','data_inventory.csv','requirements_traceability.csv','prospective_validation_protocol.json','research_trial_registry.csv'],
 'trade_evidence':['01_trade_logs/trade_path_observations.csv','01_trade_logs/exclusions.csv'],
 'portfolio':['02_portfolio_logs/events.csv','02_portfolio_logs/equity_curve.csv','02_portfolio_logs/sizing_epochs.csv','02_portfolio_logs/completion_batches.csv','02_portfolio_logs/entry_cohorts.csv','02_portfolio_logs/strict_batches.csv','02_portfolio_logs/exposure_timeline.csv','02_portfolio_logs/cash_reconciliation.csv'],
 'execution':['03_statistical_validation/execution_model_validation.csv','03_statistical_validation/fill_selection_analysis.csv'],
 'paired':['05_profitability_dissection/paired_stop_vs_hold.csv','05_profitability_dissection/paired_effect_intervals.csv','05_profitability_dissection/portfolio_stop_vs_hold.csv'],
 'forecast':['07_final_report/launch_assessment.md','07_final_report/launch_gates.csv','07_final_report/target_window_forecast.csv','07_final_report/forecast_assumptions.json','07_final_report/monthly_forecast.csv','07_final_report/summary_tables.csv']}
coverage=[]
for area,paths in requirements.items():
    for p in paths:coverage.append(dict(area=area,path=p,in_run=(R/p).exists(),at_experiment_root=(E/p).exists(),bytes=(R/p).stat().st_size if (R/p).exists() else None))
with (O/'deliverable_coverage.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(coverage[0]));w.writeheader();w.writerows(coverage)
byday=defaultdict(int)
for r in t:byday[r['signal_pacific'][:10]]+=int(r['net_pnl_cents'])
total=sum(byday.values());tradenets=sorted((int(r['net_pnl_cents']) for r in t),reverse=True);daynets=sorted(byday.values(),reverse=True)
out('concentration.json',dict(top5_game_share_net=sum(tradenets[:5])/total,top10_game_share_net=sum(tradenets[:10])/total,top5_signal_day_share_net=sum(daynets[:5])/total,top10_signal_day_share_net=sum(daynets[:10])/total,days=len(byday),losing_signal_days=sum(v<0 for v in byday.values()),note='Realized final trade P&L attributed to entry date; not daily MTM return'))
print(json.dumps(cis,indent=2))
