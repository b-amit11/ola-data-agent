import sqlite3
import pytest
from pydantic import ValidationError
from ola_agent.database import validate_sql
from ola_agent.etl import ETLTools
from ola_agent.schemas import ETLAction


@pytest.mark.parametrize('sql',[
    'DELETE FROM rides','UPDATE rides SET fare_inr=0','DROP TABLE rides',
    'SELECT 1; SELECT 2','SELECT * FROM rides; -- x\n DELETE FROM users',
    "ATTACH DATABASE '/tmp/other.db' AS other",'PRAGMA table_info(rides)',
    'SELECT * FROM sqlite_master','SELECT * FROM pg_catalog.pg_user',
    "SELECT load_extension('evil')","SELECT pg_read_file('/etc/passwd')",
    'SELECT pg_sleep(5)','SELECT * INTO backup FROM rides','SELECT * FROM rides FOR UPDATE',
    'WITH x AS (DELETE FROM rides RETURNING *) SELECT * FROM x',
    'WITH RECURSIVE x(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM x) SELECT * FROM x',
    'SELECT RANDOM() FROM rides','SELECT * FROM unknown',
])
def test_blocks_non_analytics_sql(sql):
    with pytest.raises(ValueError): validate_sql(sql)


def test_select_join_cte_and_logical_operators(db):
    result=db.query("WITH x AS (SELECT * FROM rides WHERE status='Completed' AND fare_inr>0) SELECT COUNT(*) AS n FROM x")
    assert result['rows']==[[940]]
    assert db.query('SELECT COUNT(*) FROM rides')['rows']==[[1200]]


def test_database_remains_read_only_even_if_parser_is_bypassed(db,monkeypatch):
    monkeypatch.setattr('ola_agent.database.validate_sql',lambda sql,dialect:sql)
    with pytest.raises(sqlite3.DatabaseError): db.query('DELETE FROM rides')
    assert db.query('SELECT COUNT(*) FROM rides')['rows']==[[1200]]


def test_row_limit_and_missing_column(db):
    result=db.query('SELECT ride_id FROM rides ORDER BY ride_id',limit=10)
    assert len(result['rows'])==10 and result['truncated']
    with pytest.raises(sqlite3.OperationalError):db.query('SELECT invented_column FROM rides')


def test_atomic_filter_and_no_model_paths(workspace):
    tools=ETLTools(workspace)
    with pytest.raises(ValueError):
        tools.execute(ETLAction(action='filter',filters=[{'column':'status','operator':'eq','value':'Completed'},{'column':'made_up','operator':'eq','value':'x'}]))
    assert len(tools.frame)==1200
    with pytest.raises(ValidationError): ETLAction(action='export',output_path='/tmp/unsafe.csv')
    with pytest.raises(ValidationError): ETLAction(action='exec',message='print(1)')
    with pytest.raises(ValidationError): ETLAction(action='extract',source='http://127.0.0.1')


def test_exports_stay_in_workspace_and_escape_formulas(workspace):
    tools=ETLTools(workspace); tools.frame.loc[0,'city']='=1+1'
    result=tools.execute(ETLAction(action='export'))
    path=workspace/'exports'/result['exports'][0]
    assert path.is_file() and path.parent==workspace/'exports'
    assert "'=1+1" in path.read_text()
