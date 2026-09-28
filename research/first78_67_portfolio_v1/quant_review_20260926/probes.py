"""Minimal reproductions of review findings; no source modifications."""
from pathlib import Path
import sys,json,csv,importlib.util
from types import SimpleNamespace
OUT=Path(__file__).resolve().parent;EXP=OUT.parent;RUN=EXP/'runs/first78_67_20260926T074540Z'
sys.path.insert(0,str(EXP/'src'))
from first78 import stats
from first78.materialize import candidate_from_contract
from first78.portfolio import replay
observed=[]
old=stats.replay
def capture(c,**kw):
    observed.extend(c);return SimpleNamespace(ending_equity_cents=2000000)
stats.replay=capture
inputs=[dict(game_id=f'g{i}',contract_id=f'c{i}',sport='NBA',local_day=f'2026-01-{i+1:02d}',signal_ts=10000+i*86400,exit_ts=11000+i*86400,cash_ts=11000+i*86400,exit_reason='WIN_SETTLEMENT') for i in range(7)]
stats.block_bootstrap_equity(inputs,block=7,n_paths=1,seed=1)
stats.replay=old
spacing=observed[1]['signal_ts']-observed[0]['signal_ts']
assert spacing==604805
g=dict(game_id='g',event_id='e',sport='NBA',slice='Q2',matchup='A B',first80_ticker='A')
c=dict(contract_id='A',signal_ts=100,result='yes',next_bar_ts=160,next_bar_bid_cents=82,settlement_time_ts=1000)
n=candidate_from_contract(g,c,use_next_bar_price=True)
assert n['signal_ts']==100 and n['entry_price_cents']==82
b=replay([n]);assert b.trades[0]['entry_price_cents']==78 and b.trades[0]['principal_cents']==b.trades[0]['contracts']*82
equal=dict(game_id='eq',contract_id='eq',sport='NBA',signal_ts=100,exit_ts=100,cash_ts=100,exit_reason='STOP')
assert len(replay([equal]).trades)==1
preds=list(csv.DictReader((RUN/'06_markov_chains/within_game_predictions.csv').open()))
later=[r for r in preds if r['split']=='LATER_SEGMENT' and r['p_stop_from_fit_cell']]
y=[r['stopped']=='True' for r in later];rate=sum(y)/len(y)
brier=sum((float(r['p_stop_from_fit_cell'])-yy)**2 for r,yy in zip(later,y))/len(y)
fit=[r for r in preds if r['split']=='FIT'];base=sum(r['stopped']=='True' for r in fit)/len(fit)
out=dict(mc_sampled_day_spacing_seconds=spacing,mc_expected_adjacent_day_spacing_seconds=86400,nextbar_price_used_at_ts=n['signal_ts'],price_known_at_ts=c['next_bar_ts'],trade_export_entry_price=b.trades[0]['entry_price_cents'],actual_principal_price=82,engine_allows_same_time_entry_exit=True,later_model_n=len(y),later_model_brier=brier,constant_half_brier=.25,fit_base_rate=base,fit_base_rate_brier=sum((base-v)**2 for v in y)/len(y),later_stop_rate=rate,model_time_bin_counts=dict(__import__('collections').Counter(r['time_bin'] for r in preds)))
(OUT/'defect_reproductions.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
