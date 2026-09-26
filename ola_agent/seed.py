"""Generate original synthetic fixtures. These are NOT real Ola business data."""
import json
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLES = ('users','vehicles','rides','payments','ratings')


def generate(root=ROOT):
    rng=random.Random(42)
    folder=root/'data'
    folder.mkdir(parents=True,exist_ok=True)
    cities=['Bengaluru','Mumbai','Delhi','Hyderabad','Pune']
    users=[{'user_id':i,'city':rng.choice(cities),'signup_date':str(date(2025,1,1)+timedelta(days=rng.randrange(365)))} for i in range(1,251)]
    vehicles=[{'vehicle_id':i,'vehicle_type':rng.choice(['Auto','Mini','Prime Sedan','Prime SUV']),'driver_id':i} for i in range(1,81)]
    rides=[]; payments=[]; ratings=[]
    for i in range(1,1201):
        distance=round(rng.uniform(1,32),2)
        status=rng.choices(['Completed','Customer Cancelled','Driver Cancelled'],[.78,.13,.09])[0]
        ride={'ride_id':i,'user_id':rng.randint(1,250),'vehicle_id':rng.randint(1,80),
              'ride_date':str(date(2026,1,1)+timedelta(days=rng.randrange(90))),
              'city':rng.choice(cities),'status':status,'distance_km':distance,
              'fare_inr':round(45+distance*14+rng.uniform(0,55),2)}
        rides.append(ride)
        if status=='Completed':
            pay_status=rng.choices(['Captured','Failed'],[.96,.04])[0]
            payments.append({'payment_id':i,'ride_id':i,'payment_method':rng.choice(['UPI','Card','Cash']),
                             'payment_status':pay_status,'amount_inr':ride['fare_inr']})
            ratings.append({'rating_id':i,'ride_id':i,'rating':rng.choices([1,2,3,4,5],[.03,.04,.13,.34,.46])[0]})
    frames={name:pd.DataFrame(rows) for name,rows in zip(TABLES,[users,vehicles,rides,payments,ratings])}
    for name,frame in frames.items(): frame.to_csv(folder/f'{name}.csv',index=False)
    database=folder/'ola.db'
    # Only seed our dedicated local fixture database, never DATABASE_URL.
    with sqlite3.connect(database) as conn:
        for name,frame in frames.items(): frame.to_sql(name,conn,if_exists='replace',index=False)
        conn.execute('CREATE INDEX idx_payments_ride ON payments(ride_id)')
        conn.execute('CREATE INDEX idx_rides_date ON rides(ride_date)')
    summary={'synthetic':True,'seed':42,'period':'2026-01-01 to 2026-03-31','rows':{n:len(f) for n,f in frames.items()},
             'note':'Generated educational fixture; no affiliation with Ola; not suitable for business conclusions.'}
    (folder/'manifest.json').write_text(json.dumps(summary,indent=2))
    return summary


if __name__=='__main__': print(json.dumps(generate(),indent=2))
