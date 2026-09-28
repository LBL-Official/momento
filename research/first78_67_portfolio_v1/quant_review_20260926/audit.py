"""Read-only audit of Cursor's run. Writes only into this review directory."""
from pathlib import Path
import csv, json, hashlib, sys, statistics, math, bisect, subprocess
from collections import Counter, defaultdict
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal, ROUND_CEILING
from zoneinfo import ZoneInfo

OUT=Path(__file__).resolve().parent
EXP=OUT.parent
RUN=EXP/'runs/first78_67_20260926T074540Z'
sys.path.insert(0,str(EXP/'src'))
LA=ZoneInfo('America/Los_Angeles')
def read(p):
    with p.open() as f:return list(csv.DictReader(f))
def write(name,rows):
    if not rows:return
    with (OUT/name).open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows(rows)
def dump(name,obj): (OUT/name).write_text(json.dumps(obj,indent=2,default=str))
def fee(q,p):return int((Decimal('0.0175')*q*Decimal(p)/100*(1-Decimal(p)/100)*100).to_integral_value(rounding=ROUND_CEILING))
def day(ts):return datetime.fromtimestamp(int(ts),LA).date().isoformat()
def dd(values):
    peak=values[0];pi=0;best=(0,0,0,0)
    for i,v in enumerate(values):
        if v>peak:peak=v;pi=i
        if peak and 1-v/peak>best[0]:best=(1-v/peak,peak-v,pi,i)
    return dict(fraction=best[0],dollars=best[1]/100,peak_index=best[2],trough_index=best[3])

# All files parsed / hashed, including every trade text; duplicate copies kept separate from totals.
inventory=[];groups=defaultdict(list);docs=[]
for p in sorted(RUN.rglob('*')):
    if not p.is_file():continue
    b=p.read_bytes();h=hashlib.sha256(b).hexdigest();rel=str(p.relative_to(RUN));groups[h].append(rel)
    row=dict(path=rel,bytes=len(b),sha256=h,rows=None,columns=None,parse_status='READ',error='')
    try:
        if p.suffix=='.csv':
            with p.open() as f:
                r=csv.reader(f);header=next(r,None);row['columns']=len(header) if header else 0;row['rows']=sum(1 for _ in r)
            row['parse_status']='OK' if header else 'EMPTY_NO_HEADER'
        elif p.suffix=='.json':json.loads(b);row['parse_status']='OK'
        elif p.suffix in ('.md','.txt'):
            text=b.decode('utf-8');row['parse_status']='OK'
            if p.suffix=='.md':docs.append(f'\n## {rel}\n\n{text}')
    except Exception as e:row['parse_status']='ERROR';row['error']=str(e)
    inventory.append(row)
write('file_inventory.csv',inventory)
dump('duplicate_content_groups.json',[v for v in groups.values() if len(v)>1])
(OUT/'source_documentation_snapshot.md').write_text('# Read-only documentation snapshot\n'+''.join(docs))
trades=read(RUN/'01_trade_logs/trades.csv');events=read(RUN/'02_portfolio_logs/events.csv')
for t in trades:
    for k in ['contracts','principal_cents','entry_fee_cents','exit_fee_cents','entry_ts','exit_ts','cash_ts','entry_price_cents','exit_price_cents','net_pnl_cents','gross_pnl_cents','sizing_balance_cents','epoch_id','completion_sequence','entry_sequence','r0_cents']:
        t[k]=int(t[k])
byid={t['trade_id']:t for t in trades};checks=[]
def check(name,condition,detail=''):checks.append(dict(check=name,status='PASS' if condition else 'FAIL',detail=detail))
check('unique trade IDs',len(byid)==len(trades));check('unique games',len({t['game_id'] for t in trades})==len(trades))
for t in trades:
    q=t['contracts'];p=t['entry_price_cents'];x=t['exit_price_cents'];ef=fee(q,p);xf=fee(q,x) if t['exit_reason']=='STOP' else 0
    check('trade arithmetic '+t['trade_id'],t['principal_cents']==q*p and t['entry_fee_cents']==ef and t['exit_fee_cents']==xf and t['gross_pnl_cents']==q*(x-p) and t['net_pnl_cents']==q*(x-p)-ef-xf)
    check('sizing '+t['trade_id'],q==(t['sizing_balance_cents']*600//10000)//p)
    check('chronology '+t['trade_id'],t['entry_ts']<t['exit_ts']<=t['cash_ts'])

# Reconstruct each supplied event without calling the original portfolio engine.
cash=2000000;rec=0;openp={};b=2000000;comp=0;netclosed=0;maxopen=0;evout=[]
for i,e in enumerate(events):
    t=byid.get(e.get('trade_id'));kind=e['kind']
    if kind=='entry':
        check('epoch balance at entry '+t['trade_id'],b==t['sizing_balance_cents'])
        cash-=t['principal_cents']+t['entry_fee_cents'];openp[t['trade_id']]=t
    elif kind=='exit':
        openp.pop(t['trade_id']);rec+=t['contracts']*t['exit_price_cents']-t['exit_fee_cents'];comp+=1;netclosed+=t['net_pnl_cents']
        if comp%10==0:b=cash+rec+sum(x['principal_cents'] for x in openp.values())
    elif kind=='cash':
        proceeds=t['contracts']*t['exit_price_cents']-t['exit_fee_cents'];cash+=proceeds;rec-=proceeds
    eq=cash+rec+sum(x['principal_cents'] for x in openp.values())
    check('event '+str(i),cash==int(e['cash_cents']) and rec==int(e['receivable_cents']) and eq==int(e['equity_cents']) and len(openp)==int(e['open_count']) and b==int(e['sizing_balance_cents']) and cash>=0 and rec>=0 and len(openp)<=7)
    check('realized identity '+str(i),eq==2000000+netclosed-sum(x['entry_fee_cents'] for x in openp.values()))
    maxopen=max(maxopen,len(openp))
    evout.append(dict(index=i,ts=int(e['ts']),local_day=day(e['ts']),kind=kind,cash_cents=cash,receivable_cents=rec,realized_equity_cents=eq,open_count=len(openp),open_principal_cents=sum(x['principal_cents'] for x in openp.values())))
write('independent_event_reconciliation.csv',evout)
write('checks.csv',checks)

from first78.extract import extract, _index_candles, _read_bars, _quality, NBA_ROOT, NCAAB_ROOT
from first78.materialize import build_candidates
from first78.portfolio import replay
print('Re-extracting the frozen population using existing readers (not independent clock validation)',flush=True)
games=extract(progress=lambda *a:None);candidates,audit=build_candidates(games,'CONTRACT_WISE_FIRST',cash_mode='settlement')
write('reextracted_candidate_audit.csv',audit)
rb=replay([{k:v for k,v in c.items() if k!='path'} for c in candidates])
matches=[]
for t,u in zip(trades,rb.trades):
    matches.append(dict(trade_id=t['trade_id'],match=all(t[k]==u[k] for k in ['game_id','contract_id','entry_ts','exit_ts','contracts','net_pnl_cents'])))
write('source_replay_comparison.csv',matches)

# Both teams' scan metadata, including selected-side identity and timing.
sources=[];allcontracts={}
for g in games:
    for c in g['contracts']:
        if c.get('contract_id'):allcontracts[c['contract_id']]=c
        sources.append(dict(game_id=g['game_id'],sport=g['sport'],contract_id=c.get('contract_id',c.get('ticker')),cross_found=c.get('cross_found'),signal_ts=c.get('signal_ts'),window_eligible=c.get('window_eligible'),date_eligible=c.get('date_eligible'),reason=c.get('reason')))
write('both_side_signal_audit.csv',sources)
paths={};rawdiag=[];idx={'NBA':_index_candles(NBA_ROOT),'NCAAB':_index_candles(NCAAB_ROOT)}
for t in trades:
    bars=_read_bars(idx[t['sport']][t['contract_id']]);had=False;qp=[]
    for bar in bars:
        if _quality(bar['bid'],bar['ask'],bar['vol'],had):had=True;qp.append((bar['ts'],bar['bid']/100))
    paths[t['trade_id']]=qp
    cs=allcontracts[t['contract_id']]
    unfiltered=next((v for v in bars if v['ts']>t['entry_ts'] and v['bid'] is not None and v['bid']<=6700),None)
    stop=cs.get('stop_ts');qs=[v for v in qp if t['entry_ts']<=v[0]<=t['exit_ts']]
    rawdiag.append(dict(trade_id=t['trade_id'],observed_entry_bid_cents=int(t['observed_entry_close_cents']),stop_close_cents=cs.get('stop_close_cents'),stop_gap_cents=cs.get('stop_gap_cents'),next_bar_ts=cs.get('next_bar_ts'),next_bar_bid_cents=cs.get('next_bar_bid_cents'),next_bar_lag_seconds=None if cs.get('next_bar_ts') is None else cs['next_bar_ts']-t['entry_ts'],stop_on_next_bar=stop is not None and stop==cs.get('next_bar_ts'),first_valid_unfiltered_stop_ts=None if unfiltered is None else unfiltered['ts'],quality_stop_ts=stop,unfiltered_stop_earlier=unfiltered is not None and (stop is None or unfiltered['ts']<stop),max_held_observation_gap_seconds=max([v[0]-u[0] for u,v in zip(qs,qs[1:])],default=None),settlement_ts=cs.get('settlement_time_ts'),close_ts=cs.get('close_time_ts'),stop_after_settlement=stop is not None and cs.get('settlement_time_ts') is not None and stop>cs['settlement_time_ts']))
write('raw_path_diagnostics.csv',rawdiag)

# Mark at all observed held closes AND every cash/position event, not just trade events.
timestamps=set(int(e['ts']) for e in events)
for t in trades:
    timestamps.update(ts for ts,px in paths[t['trade_id']] if t['entry_ts']<=ts<t['exit_ts'])
bytime=defaultdict(list)
for e in evout:bytime[e['ts']].append(e)
event_lookup=defaultdict(list)
for e in events:event_lookup[int(e['ts'])].append(e)
active=set();state=dict(cash_cents=2000000,receivable_cents=0,realized_equity_cents=2000000);marks=[]
path_ts={k:[x[0] for x in v] for k,v in paths.items()}
for ts in sorted(timestamps):
    # End-of-timestamp marks. Event-order accounting remains in the independent event table.
    for e in event_lookup[ts]:
        if e['kind']=='entry':active.add(e['trade_id'])
        elif e['kind']=='exit':active.discard(e['trade_id'])
    if bytime[ts]:state=bytime[ts][-1]
    value=0;ages=[];missing=0
    for tid in active:
        j=bisect.bisect_right(path_ts[tid],ts)-1
        if j<0:missing+=1;continue
        pt,px=paths[tid][j];value+=byid[tid]['contracts']*px;ages.append(ts-pt)
    marks.append(dict(ts=ts,local_day=day(ts),realized_equity_cents=state['realized_equity_cents'],bid_marked_equity_cents=None if missing else state['cash_cents']+state['receivable_cents']+value,open_count=len(active),max_mark_age_seconds=max(ages,default=0),marks_older_than_60s=sum(a>60 for a in ages),missing_marks=missing))
write('all_observed_close_marks.csv',marks)
md=dd([2000000]+[r['bid_marked_equity_cents'] for r in marks if r['bid_marked_equity_cents'] is not None])

# Actual prior-equity calendar returns; realized accounting diagnostic, not MTM Sharpe.
endofday={e['local_day']:e['realized_equity_cents'] for e in evout};daily=[];prev=2000000;d=date(2025,11,1)
while d<=date(2026,4,1):
    eq=endofday.get(d.isoformat(),prev);daily.append(dict(day=d.isoformat(),equity_dollars=eq/100,pnl_dollars=(eq-prev)/100,return_fraction=eq/prev-1));prev=eq;d+=timedelta(days=1)
write('calendar_realized_returns.csv',daily)
returns=[d['return_fraction'] for d in daily];sr=statistics.mean(returns)/statistics.stdev(returns)
monthly=[]
for month in sorted({x['day'][:7] for x in daily}):
    rows=[x for x in daily if x['day'].startswith(month)];closing=defaultdict(int)
    for t in trades:
        if day(t['exit_ts']).startswith(month):closing[t['sport']]+=t['net_pnl_cents']
    monthly.append(dict(month=month,calendar_days=len(rows),realized_equity_change_dollars=sum(r['pnl_dollars'] for r in rows),NBA_closed_trade_net_dollars=closing['NBA']/100,NCAAB_closed_trade_net_dollars=closing['NCAAB']/100,partial_month=month=='2026-04'))
write('monthly_attribution.csv',monthly)

# Exact fixed-opening-size diagnostic and stop/hold paired mean per contract.
fixed=sum((1538*(t['exit_price_cents']-78)-fee(1538,78)-(fee(1538,67) if t['exit_reason']=='STOP' else 0)) for t in trades)
pair=read(RUN/'05_profitability_dissection/paired_stop_vs_hold.csv')
pairedpc=[int(p['paired_diff_cents'])/byid[p['trade_id']]['contracts'] for p in pair]
metrics=dict(run=str(RUN),files=len(inventory),empty_files=[r['path'] for r in inventory if r['bytes']==0],parse_errors=[r for r in inventory if r['parse_status']=='ERROR'],checks=len(checks),failures=[r for r in checks if r['status']=='FAIL'],n=len(trades),unique_games=len({t['game_id'] for t in trades}),sport_counts=dict(Counter(t['sport'] for t in trades)),net_dollars=sum(t['net_pnl_cents'] for t in trades)/100,gross_dollars=sum(t['gross_pnl_cents'] for t in trades)/100,fees_dollars=sum(t['entry_fee_cents']+t['exit_fee_cents'] for t in trades)/100,ending_cash_dollars=cash/100,max_open=maxopen,source_reextracted_candidates=len(candidates),source_replay_matches=sum(x['match'] for x in matches),fixed_1538_net_dollars=fixed/100,realized_dd=dd([2000000]+[e['realized_equity_cents'] for e in evout]),all_close_mark_dd=md,mark_points=len(marks),mark_points_with_stale=sum(r['max_mark_age_seconds']>60 for r in marks),max_mark_age_seconds=max(r['max_mark_age_seconds'] for r in marks),calendar_sharpe_unannualized=sr,calendar_sharpe_annualized=sr*math.sqrt(365),calendar_days=len(daily),zero_equity_change_days=sum(d['pnl_dollars']==0 for d in daily),entry_overshoots=sum(int(t['observed_entry_close_cents'])>78 for t in trades),average_entry_bid=statistics.mean(int(t['observed_entry_close_cents']) for t in trades),average_stop_gap=statistics.mean(r['stop_gap_cents'] for r in rawdiag if r['stop_gap_cents'] is not None),max_stop_gap=max(r['stop_gap_cents'] or 0 for r in rawdiag),stops_after_settlement=sum(r['stop_after_settlement'] for r in rawdiag),unfiltered_stops_earlier=sum(r['unfiltered_stop_earlier'] for r in rawdiag),nextbar_same_as_stop=sum(r['stop_on_next_bar'] for r in rawdiag),paired_net_dollars=sum(int(p['paired_diff_cents']) for p in pair)/100,paired_mean_cents_per_contract=statistics.mean(pairedpc),positive_rate=sum(t['net_pnl_cents']>0 for t in trades)/len(trades),mean_net_cents_per_contract=statistics.mean(t['net_pnl_cents']/t['contracts'] for t in trades),stop_then_win=sum(t['stopped_then_won']=='True' for t in trades),terminal_win_rate=sum(t['terminal_result']=='yes' for t in trades)/len(trades),original_input_hashes={str(p.relative_to(RUN)):hashlib.sha256(p.read_bytes()).hexdigest() for p in RUN.rglob('*') if p.is_file()})
dump('audit_metrics.json',metrics)
print(json.dumps({k:v for k,v in metrics.items() if k!='original_input_hashes'},indent=2),flush=True)
