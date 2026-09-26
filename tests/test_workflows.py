import pandas as pd
import pytest
from ola_agent.examples import EXAMPLES
from ola_agent.provider import DemoProvider
from ola_agent.graph import run
from ola_agent.schemas import SQLProposal,Review,ETLAction
from ola_agent.evaluate import compare,oracle


@pytest.mark.parametrize('question',[q for q,c in EXAMPLES.items() if c['route']=='sql'])
def test_sql_results_match_pandas(question,workspace,db):
    result=run(question,DemoProvider(),db,workspace)
    assert not result.get('error')
    assert result['model_calls']==0
    value=result['result'];compare(pd.DataFrame(value['rows'],columns=value['columns']),oracle(question,workspace))


@pytest.mark.parametrize('question',[q for q,c in EXAMPLES.items() if c['route']=='etl'])
def test_etl_finishes_and_exports(question,workspace,db):
    result=run(question,DemoProvider(),db,workspace)
    assert result['finished'] and not result.get('error')
    assert result['steps']<=6 and len(result['exports'])==1
    assert (workspace/'exports'/result['exports'][0]).exists()


def test_demo_does_not_pretend_to_answer_arbitrary_questions(workspace,db):
    result=run('Make something up about profits',DemoProvider(),db,workspace)
    assert result['route']=='clarify' and 'result' not in result


def test_one_sql_execution_repair(workspace,db):
    class Repair(DemoProvider):
        attempts=0
        def sql(self,*args):
            self.attempts+=1
            return SQLProposal(sql='SELECT wrong_field FROM rides' if self.attempts==1 else 'SELECT COUNT(*) AS n FROM rides',explanation='test')
    result=run('What payment methods are available?',Repair(),db,workspace)
    assert result['attempts']==2 and result['result']['rows']==[[1200]]


def test_semantic_rejection_stops_after_two_attempts(workspace,db):
    class Reject(DemoProvider):
        def review(self,*args):return Review(approved=False,feedback='Does not answer the question')
    result=run('What payment methods are available?',Reject(),db,workspace)
    assert result['attempts']==2 and 'result' not in result
    assert 'No answer produced' in result['answer']


def test_unsafe_sql_never_reaches_judge_or_execution(workspace,db):
    class Unsafe(DemoProvider):
        def sql(self,*args):return SQLProposal(sql='DROP TABLE rides',explanation='test')
        def review(self,*args):raise AssertionError('Should never reach the judge')
    result=run('What payment methods are available?',Unsafe(),db,workspace)
    assert 'blocked' in result['answer'].lower()
    assert db.query('SELECT COUNT(*) FROM rides')['rows']==[[1200]]


def test_etl_step_budget(workspace,db):
    class Endless(DemoProvider):
        def etl(self,*args):return ETLAction(action='inspect')
    result=run('Export completed rides as CSV.',Endless(),db,workspace)
    assert result['steps']==6 and 'budget' in result['answer']


def test_state_does_not_leak_between_runs(workspace,db):
    run('Export completed rides as CSV.',DemoProvider(),db,workspace)
    result=run('What is the cancellation rate by city?',DemoProvider(),db,workspace)
    assert sum(r[1] for r in result['result']['rows'])==1200
