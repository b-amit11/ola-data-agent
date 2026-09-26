"""Router → SQL generate/check/review/execute, or bounded ETL action/observation loop."""
import time
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

from .database import Database, validate_sql
from .etl import ETLTools
from .seed import ROOT


class State(TypedDict,total=False):
    question:str
    route:str
    sql:str
    explanation:str
    error:str
    attempts:int
    trace:list
    result:dict
    answer:str
    approved:bool
    etl_action:dict
    steps:int
    observation:dict
    finished:bool
    exports:list


def event(state,node,message):
    return state.get('trace',[])+[{'node':node,'message':message}]


def build_graph(provider,database=None,root=ROOT):
    db=database or Database()
    etl=ETLTools(root,offline=provider.mode!='live LLM')
    def route(s):
        decision=provider.route(s['question'])
        return {'route':decision.destination,'answer':decision.message,
                'trace':event(s,'router',decision.message)}
    def generate(s):
        proposal=provider.sql(s['question'],db.schema(),db.dialect,s.get('error',''))
        return {'sql':proposal.sql,'explanation':proposal.explanation,'attempts':s.get('attempts',0)+1,
                'error':'','trace':event(s,'sql.generate','Generated a candidate query.')}
    def guard(s):
        try:
            validate_sql(s['sql'],db.dialect)
            return {'approved':True,'trace':event(s,'sql.guard','AST checks passed; execution will also use read-only database controls.')}
        except ValueError as exc:
            return {'approved':False,'error':str(exc),'answer':'Query blocked: '+str(exc),'trace':event(s,'sql.guard',str(exc))}
    def judge(s):
        review=provider.review(s['question'],s['sql'])
        return {'approved':review.approved,'error':'' if review.approved else review.feedback,
                'answer':review.feedback,'trace':event(s,'sql.review',review.feedback)}
    def execute(s):
        try:
            result=db.query(s['sql'])
            return {'result':result,'error':'','trace':event(s,'sql.execute',f"Returned {len(result['rows'])} rows; truncated={result['truncated']}.")}
        except Exception as exc:
            # No connection URLs, secrets, or full exception trace are sent to a model/UI.
            detail=str(exc)[:180] if type(exc).__module__=='sqlite3' else type(exc).__name__
            return {'error':'Execution failed: '+detail,'trace':event(s,'sql.execute','Execution failed; one repair is allowed.')}
    def sql_next(s):
        if s.get('error'): return 'generate' if s.get('attempts',0)<2 else 'finish_sql'
        return 'finish_sql'
    def judge_next(s):
        return 'execute' if s['approved'] else ('generate' if s['attempts']<2 else 'finish_sql')
    def finish_sql(s):
        if s.get('error'): answer='No answer produced. '+s['error']
        else:
            result=s['result']
            answer=f"Query completed: {len(result['rows'])} result rows. Values below come directly from the database."
            if result['truncated']: answer+=' Display capped at 100 rows; this is not the full result.'
        return {'answer':answer,'trace':event(s,'sql.finish',answer)}
    def plan_etl(s):
        action=provider.etl(s['question'],s.get('trace',[]),etl.observe(),s.get('steps',0))
        return {'etl_action':action.model_dump(),'finished':action.action=='finish',
                'trace':event(s,'etl.plan',action.model_dump_json())}
    def tool_etl(s):
        from .schemas import ETLAction
        try:
            observation=etl.execute(ETLAction(**s['etl_action']))
            return {'steps':s.get('steps',0)+1,'observation':observation,'exports':observation['exports'],
                    'trace':event(s,'etl.tool',f"{s['etl_action']['action']}: {observation['row_count']} rows remain."),'error':''}
        except Exception as exc:
            detail=str(exc) if isinstance(exc,(ValueError,TypeError,KeyError)) else type(exc).__name__
            return {'steps':s.get('steps',0)+1,'error':detail,'trace':event(s,'etl.tool','Failed: '+detail)}
    def after_tool(s):
        return 'finish_etl' if s.get('error') or s['steps']>=6 else 'plan_etl'
    def finish_etl(s):
        observation=etl.observe()
        if s.get('error'): answer='ETL stopped: '+s['error']
        elif not s.get('finished'): answer='Stopped at the 6-step tool budget. Task may be incomplete.'
        else: answer=f"ETL finished with {observation['row_count']} rows and {len(etl.exported)} export file(s)."
        return {'answer':answer,'observation':observation,'exports':etl.exported.copy(),
                'result':{'columns':list(etl.frame.columns),'rows':etl.frame.head(100).values.tolist(),'truncated':len(etl.frame)>100},
                'trace':event(s,'etl.finish',answer)}
    g=StateGraph(State)
    for name,node in [('route',route),('generate',generate),('guard',guard),('judge',judge),('execute',execute),('finish_sql',finish_sql),('plan_etl',plan_etl),('tool_etl',tool_etl),('finish_etl',finish_etl)]:g.add_node(name,node)
    g.add_edge(START,'route')
    g.add_conditional_edges('route',lambda s:s['route'],{'sql':'generate','etl':'plan_etl','clarify':END})
    g.add_edge('generate','guard')
    g.add_conditional_edges('guard',lambda s:s['approved'],{True:'judge',False:END})
    g.add_conditional_edges('judge',judge_next)
    g.add_conditional_edges('execute',sql_next)
    g.add_edge('finish_sql',END)
    g.add_conditional_edges('plan_etl',lambda s:s['finished'],{True:'finish_etl',False:'tool_etl'})
    g.add_conditional_edges('tool_etl',after_tool)
    g.add_edge('finish_etl',END)
    return g.compile()


def run(question,provider,database=None,root=ROOT):
    if not question.strip() or len(question)>2000: raise ValueError('Provide a question of 1–2000 characters')
    start=time.perf_counter()
    result=build_graph(provider,database,root).invoke({'question':question,'trace':[],'steps':0,'attempts':0},config={'recursion_limit':25})
    result['elapsed_ms']=round((time.perf_counter()-start)*1000,1)
    result['mode']=provider.mode
    result['model_calls']=provider.calls
    return result
