"""Compare tool outputs with independent Pandas oracles. Offline ≠ LLM evaluation."""
import argparse
import json
from pathlib import Path

import pandas as pd

from .database import Database,validate_sql
from .examples import EXAMPLES
from .graph import run
from .provider import DemoProvider,GroqProvider
from .seed import ROOT


def oracle(question,root=ROOT):
    rides=pd.read_csv(root/'data/rides.csv'); payments=pd.read_csv(root/'data/payments.csv')
    vehicles=pd.read_csv(root/'data/vehicles.csv'); ratings=pd.read_csv(root/'data/ratings.csv')
    captured=rides[rides.status.eq('Completed')].merge(payments[payments.payment_status.eq('Captured')],on='ride_id')
    if question=='What payment methods are available?':
        return pd.DataFrame({'payment_method':sorted(payments.payment_method.unique())})
    if question=='Show collected revenue by city.':
        return captured.groupby('city').amount_inr.sum().round(2).rename('collected_revenue_inr').reset_index().sort_values('collected_revenue_inr',ascending=False)
    if question=='What is the cancellation rate by city?':
        out=rides.assign(cancelled=rides.status.ne('Completed')).groupby('city').agg(total_rides=('ride_id','size'),cancelled=('cancelled','sum')).reset_index()
        out['cancellation_pct']=(100*out.cancelled/out.total_rides).round(2)
        return out[['city','total_rides','cancellation_pct']].sort_values('cancellation_pct',ascending=False)
    if question=='Who are the top 5 riders by collected revenue?':
        return captured.groupby('user_id').amount_inr.sum().round(2).rename('collected_revenue_inr').reset_index().sort_values(['collected_revenue_inr','user_id'],ascending=[False,True]).head(5)
    if question=='Show average rating by vehicle type.':
        out=rides.merge(vehicles,on='vehicle_id').merge(ratings,on='ride_id').groupby('vehicle_type').agg(average_rating=('rating','mean'),rated_rides=('ride_id','size')).reset_index()
        out.average_rating=out.average_rating.round(2)
        return out.sort_values(['average_rating','vehicle_type'],ascending=[False,True])
    if question=='How many rides have no payment record?':
        return pd.DataFrame({'rides_without_payment':[int((~rides.ride_id.isin(payments.ride_id)).sum())]})
    raise ValueError('No oracle for question')


def compare(actual,expected):
    actual=actual.reset_index(drop=True);expected=expected.reset_index(drop=True)
    pd.testing.assert_frame_equal(actual,expected,check_dtype=False,check_exact=False,atol=.011,rtol=0)


def evaluate(live=False,database=None):
    checks=[]
    for q,case in EXAMPLES.items():
        # Live extraction depends on a changing external API, not this fixed fixture.
        if live and 'Pokemon' in q: continue
        try:
            result=run(q,GroqProvider() if live else DemoProvider(),database)
            if result.get('error'): raise AssertionError(result['error'])
            if result['route']!=case['route']: raise AssertionError('Incorrect route')
            if case['route']=='sql':
                table=result['result']; compare(pd.DataFrame(table['rows'],columns=table['columns']),oracle(q))
            else:
                if not result.get('exports'): raise AssertionError('Expected an export')
                path=ROOT/'exports'/result['exports'][-1]
                output=pd.read_json(path) if path.suffix=='.json' else pd.read_csv(path)
                rides=pd.read_csv(ROOT/'data/rides.csv')
                if 'Pokemon' in q:
                    expected=pd.DataFrame(json.loads((ROOT/'data/pokemon_fixture.json').read_text())['results'])
                elif 'Count completed' in q:
                    expected=rides[rides.status.eq('Completed')].groupby('city').size().reset_index(name='row_count')
                else:
                    expected=rides[rides.status.eq('Completed')]
                    if '20 km' in q: expected=expected[expected.distance_km.gt(20)]
                compare(output,expected)
            checks.append({'case':q,'passed':True,'detail':'Matches independent expected result'})
        except Exception as exc:
            checks.append({'case':q,'passed':False,'detail':type(exc).__name__})
    if not live:
        for sql in ['DROP TABLE rides','SELECT * FROM rides; DELETE FROM rides','SELECT * FROM sqlite_master','SELECT load_extension(\'x\')','SELECT * FROM secret.customers']:
            try: validate_sql(sql);passed=False
            except ValueError: passed=True
            checks.append({'case':'Block: '+sql,'passed':passed,'detail':'Deterministic guard check'})
    report={'mode':'live LLM' if live else 'offline scripted fixtures','backend':(database or Database()).dialect,
            'passed':sum(c['passed'] for c in checks),'total':len(checks),'checks':checks,
            'interpretation':'Live result correctness on a small developer-authored suite; not a held-out benchmark.' if live else 'Tests orchestration and tools only. No LLM accuracy is measured.'}
    folder=ROOT/'reports';folder.mkdir(exist_ok=True)
    name='live-evaluation.json' if live else ('evaluation-postgres.json' if report['backend']=='postgres' else 'evaluation.json')
    (folder/name).write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    return report


if __name__=='__main__':
    import os
    from dotenv import load_dotenv
    load_dotenv(ROOT/'.env')
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true');parser.add_argument('--postgres',action='store_true')
    args=parser.parse_args()
    db=Database(url=os.getenv('DATABASE_URL','postgresql+psycopg://demo_reader:demo_reader_local@localhost:5433/ola_demo')) if args.postgres else Database()
    report=evaluate(args.live,db)
    raise SystemExit(0 if report['passed']==report['total'] else 1)
