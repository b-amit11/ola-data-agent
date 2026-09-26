import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from ola_agent.seed import ROOT, TABLES, generate
from ola_agent.database import Database
from ola_agent.examples import EXAMPLES
from ola_agent.graph import run
from ola_agent.provider import DemoProvider, GroqProvider

load_dotenv(ROOT/'.env')
st.set_page_config(page_title='Ola Data Agent · RideOps',page_icon='🚕',layout='wide')
st.markdown('''<style>
.block-container{max-width:1240px;padding-top:2.5rem;}
h1{font-size:3.1rem!important;letter-spacing:-.045em;}
.eyebrow{font-size:.8rem;letter-spacing:.2em;color:#a5a1ff;font-weight:700;}
.intro{font-size:1.1rem;line-height:1.6;color:#aeb8cb;max-width:790px;}
[data-testid="stMetric"]{border:1px solid #30344a;border-radius:12px;background:#191d2d;padding:16px;}
</style>''',unsafe_allow_html=True)
if not (ROOT/'data/ola.db').exists(): generate()

with st.sidebar:
    st.markdown('### RIDEOPS / DATA AGENT')
    mode=st.radio('Execution mode',['Offline demo','Live LLM'])
    db_mode=st.selectbox('Database',['SQLite demo','PostgreSQL (local Docker)'])
    st.caption('All ride-booking data is synthetic. January–March 2026. No real customers or Ola records.')
    if mode=='Offline demo':
        st.info('Preset plans, real tool execution. No model calls or API key needed.')
    elif not os.getenv('GROQ_API_KEY'):
        st.warning('Live mode needs GROQ_API_KEY in your local .env. Never put a key in a public repository.')
    else: st.caption('Live provider: Groq. Questions, schema and tool observations are sent to the configured model.')
    st.markdown('[Tutorial by Ansh Lamba](https://www.youtube.com/watch?v=7yOmi4IX-Rs)')
    st.caption('Independent implementation inspired by the tutorial; not affiliated with Ola.')

context=(mode,db_mode)
if st.session_state.get('context')!=context:
    st.session_state.pop('result',None)
    st.session_state.context=context

st.markdown('<div class="eyebrow">RIDE ANALYTICS / SQL + PYTHON ETL</div>',unsafe_allow_html=True)
st.title('One question. The right workflow.')
st.markdown('<p class="intro">Explore ride-booking data, inspect the query behind an answer, and export transformed datasets. Follow every routing decision and tool result.</p>',unsafe_allow_html=True)
a,b,c,d=st.columns(4)
a.metric('Synthetic rides','1,200');b.metric('Related tables','5');c.metric('SQL attempts','2 max');d.metric('ETL tool steps','6 max')

workbench,dataset,evaluation,architecture=st.tabs(['01 / Workbench','02 / Dataset','03 / Evaluation','04 / Architecture'])
with workbench:
    st.subheader('Ask, inspect, verify')
    if mode=='Offline demo':
        question=st.selectbox('Choose an example',list(EXAMPLES),index=2)
        st.caption('Offline mode uses explicitly scripted plans. This demonstrates orchestration and tools, not natural-language model accuracy.')
    else:
        question=st.text_area('Your question',value='Show collected revenue by city.',max_chars=2000)
        st.caption('Try: “What percentage of rides were cancelled in Bengaluru?” or “Export completed rides longer than 20 km as JSON.”')
    unavailable=mode=='Live LLM' and not os.getenv('GROQ_API_KEY')
    if st.button('Run workflow',type='primary',disabled=unavailable):
        st.session_state.pop('result',None)
        try:
            provider=DemoProvider() if mode=='Offline demo' else GroqProvider()
            url=None if db_mode=='SQLite demo' else os.getenv('DATABASE_URL','postgresql+psycopg://demo_reader:demo_reader_local@localhost:5433/ola_demo')
            with st.spinner('Running the workflow…'):
                st.session_state.result=run(question,provider,Database(url=url))
        except Exception as exc:
            if type(exc).__name__=='RateLimitError':
                st.error('Groq rate limit reached. Wait at least a minute before retrying; longer account limits may also apply. No successful result is claimed.')
            else:
                st.error(f'Workflow could not finish ({type(exc).__name__}). Check the selected database, local .env and provider availability. No successful result is claimed.')
    result=st.session_state.get('result')
    if result:
        st.divider()
        l,r=st.columns([3,1])
        with l:
            st.markdown(f"**{result.get('answer','No answer produced.')}**")
            st.caption(f"Request: {result['question']}")
        with r:
            st.caption(f"Route: {result['route'].upper()} · {result['mode']}")
            st.caption(f"Elapsed: {result['elapsed_ms']:.0f} ms · Model calls: {result['model_calls']}")
        if result.get('sql'):
            with st.expander('Inspect generated SQL',expanded=True):
                st.code(result['sql'],language='sql')
                st.caption(result.get('explanation',''))
        if result.get('result'):
            table=result['result']
            frame=pd.DataFrame(table['rows'],columns=table['columns'])
            st.dataframe(frame,hide_index=True,width='stretch')
            if table['truncated']: st.info('Preview capped at 100 rows. ETL exports contain all rows in the transformed dataframe.')
            if len(frame)>1 and frame.shape[1]>=2:
                numeric=frame.select_dtypes('number').columns.tolist()
                labels=frame.select_dtypes(exclude='number').columns.tolist()
                if labels and numeric: st.bar_chart(frame,x=labels[0],y=numeric[0],horizontal=True)
        for name in result.get('exports',[]):
            path=ROOT/'exports'/Path(name).name
            st.download_button(f'Download {name}',path.read_bytes(),file_name=name,mime='text/csv' if path.suffix=='.csv' else 'application/json')
        with st.expander('Execution trace',expanded=True):
            for i,item in enumerate(result['trace'],1):
                st.markdown(f"**{i:02d} · {item['node']}**")
                st.text(item['message'])

with dataset:
    st.subheader('Know the data before asking the model')
    st.write('Original, seeded synthetic fixtures: 250 users, 80 vehicles and 1,200 rides. Payments and ratings exist only for completed rides. Some payments fail; quoted fares and collected revenue differ.')
    name=st.selectbox('Table',TABLES)
    frame=pd.read_csv(ROOT/f'data/{name}.csv')
    st.caption(f'{len(frame):,} rows · Showing first 50 rows of the local fixture, regardless of selected query backend.')
    st.dataframe(frame.head(50),hide_index=True,width='stretch')
    st.markdown('**Collected revenue** = captured payments on completed rides. **Cancellation rate** = cancelled rides ÷ all rides. Ride city and user signup city are different fields.')

with evaluation:
    st.subheader('Workflow evidence, with honest boundaries')
    report_path=ROOT/'reports/evaluation.json'
    if report_path.exists():
        report=json.loads(report_path.read_text())
        st.metric('Offline fixture checks',f"{report['passed']}/{report['total']}")
        st.warning('These are deterministic workflow checks. They do not measure LLM accuracy, hallucination rate, or production reliability.')
        st.dataframe(pd.DataFrame(report['checks']),hide_index=True,width='stretch')
        st.download_button('Download offline evaluation',report_path.read_bytes(),'evaluation.json','application/json')
    else: st.info('Run python -m ola_agent.evaluate to create the evaluation report.')
    st.write('Live evaluation requires an API key. The included runner compares SQL results against independently computed pandas answers and checks selected ETL outputs. It records failures rather than substituting demo answers.')

with architecture:
    st.subheader('A visible decision process')
    st.code('''Question → Router
  ├─ SQL → Schema → Generate → AST guard → Semantic review → Read-only query → Result
  │                  ↑                         │                 │
  │                  └──── one bounded repair ──┴─────────────────┘
  ├─ ETL → Choose tool → Execute Python tool → Observe → Repeat (maximum 6)
  └─ Clarify → Explain unsupported or ambiguous request''',language='text')
    st.write('LangGraph manages the routes and loops. Pydantic validates model responses. LangChain connects the live Groq model. SQLite runs the portable demo; PostgreSQL is available through Docker Compose.')
    st.markdown('''**Deliberate differences from the tutorial**

- A deterministic SQL parser and database permissions enforce read-only access. An LLM review cannot override them.
- ETL uses typed filter, aggregate, extraction and export tools. Generated Python is never passed to `exec`.
- Exports use application-generated filenames. Network extraction is limited to one named public demonstration endpoint.
- Offline fixtures and live LLM responses are visibly distinguished. The app does not report simulated answers as model performance.''')
    st.caption('This is a local educational application, not a multi-user production service. Semantic correctness still depends on the model and the question; shared-model review is not independent validation.')

st.divider()
st.caption('OLA DATA AGENT / RIDEOPS · Tutorial-inspired, independently implemented · Synthetic ride data · No affiliation with Ola')
