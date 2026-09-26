"""Bounded Pandas tools; models never provide executable Python or output paths."""
import uuid
import json
from urllib.request import urlopen
import pandas as pd
from .seed import ROOT
from .schemas import ETLAction


class ETLTools:
    def __init__(self,root=ROOT,offline=True):
        self.root=root
        self.offline=offline
        self.frame=pd.read_csv(root/'data/rides.csv')
        self.exported=[]

    def observe(self):
        return {'row_count':len(self.frame),'columns':list(self.frame.columns),
                'preview':self.frame.head(5).to_dict('records')}

    def execute(self,action:ETLAction):
        df=self.frame
        if action.action=='extract':
            if self.offline:
                payload=json.loads((self.root/'data/pokemon_fixture.json').read_text())
            else:
                # The model chooses a named source, never an arbitrary URL.
                with urlopen('https://pokeapi.co/api/v2/pokemon?limit=20',timeout=10) as response:
                    raw=response.read(1_000_001)
                    if len(raw)>1_000_000: raise ValueError('API response exceeds 1 MB')
                    payload=json.loads(raw)
            self.frame=pd.json_normalize(payload['results'])
        elif action.action=='filter':
            if not action.filters: raise ValueError('Filter requires a condition')
            # Atomic operation: reject the whole tool call if any condition fails.
            for condition in action.filters:
                if condition.column not in df: raise ValueError('Unknown filter column')
                series=df[condition.column]
                value=condition.value
                if pd.api.types.is_numeric_dtype(series): value=float(value)
                operation={'eq':series.eq,'ne':series.ne,'gt':series.gt,'gte':series.ge,'lt':series.lt,'lte':series.le}[condition.operator]
                df=df[operation(value)]
            self.frame=df.copy()
        elif action.action=='aggregate':
            if not action.group_by or any(c not in df for c in action.group_by):
                raise ValueError('Provide valid group_by columns')
            if action.aggregation=='count':
                self.frame=df.groupby(action.group_by,dropna=False).size().reset_index(name='row_count')
            else:
                if action.metric not in df or not pd.api.types.is_numeric_dtype(df[action.metric]):
                    raise ValueError('Aggregation requires a numeric metric')
                self.frame=df.groupby(action.group_by,dropna=False)[action.metric].agg(action.aggregation).reset_index()
        elif action.action=='export':
            folder=self.root/'exports';folder.mkdir(exist_ok=True)
            path=folder/f'rides_{uuid.uuid4().hex[:12]}.{action.format}'
            # CSV formula escaping is a download safeguard, not data interpretation.
            if action.format=='csv':
                out=self.frame.copy()
                for col in out.select_dtypes(include=['object','str']):
                    out[col]=out[col].map(lambda x:"'"+x if isinstance(x,str) and x.startswith(('=','+','-','@')) else x)
                out.to_csv(path,index=False)
            else: self.frame.to_json(path,orient='records',indent=2)
            self.exported.append(path.name)
        return {**self.observe(),'exports':self.exported.copy()}
